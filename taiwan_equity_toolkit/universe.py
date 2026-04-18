"""
Universe — TAIEX top-200 builder with live-TAIFEX / snapshot-fallback.

Moved out of run_top200_screen.py so the V2 orchestrator can own universe
construction independently of the legacy gate pipeline. Public API:

    build_universe()              -> (stock_ids, metadata)
    apply_sector_tilt(universe)   -> (tilted_universe, tilt_notes)

`apply_sector_tilt` replaces the legacy Gate 1 hard exclusion. Per V2 Matrix
row A2, sector direction is a parallel input (annotative), not a hard gate —
so even when a tilt is configured the returned universe is always the full
set. Consumers use `tilt_notes` for analyst context (favor / caution buckets).
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from io import StringIO
from typing import Optional

import pandas as pd
import requests

log = logging.getLogger(__name__)

TAIFEX_TAIEX_URL = "https://www.taifex.com.tw/cht/9/futuresQADetail"
UNIVERSE_SIZE = 200
SNAPSHOT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "taiex_top200_snapshot.json",
)


# ──────────────────────────────────────────────────────────────────────────
# Universe construction
# ──────────────────────────────────────────────────────────────────────────


def _normalize_stock_ids(raw_values: list) -> list[str]:
    normalized: list[str] = []
    for value in raw_values:
        text = str(value).strip()
        if text.isdigit() and len(text) == 4:
            normalized.append(text)
    return normalized


def _validate_universe(stock_ids: list[str], expected_size: int = UNIVERSE_SIZE) -> list[str]:
    normalized = _normalize_stock_ids(stock_ids)
    if len(normalized) != expected_size:
        raise ValueError(f"Expected {expected_size} stock IDs, got {len(normalized)}")
    if len(set(normalized)) != expected_size:
        raise ValueError("Universe contains duplicate stock IDs")
    return normalized


def _parse_taifex_top200_from_table(
    table: pd.DataFrame, expected_size: int = UNIVERSE_SIZE
) -> list[str]:
    expected_ranks = list(range(1, expected_size + 1))
    for idx in range(len(table.columns) - 1):
        ranks = pd.to_numeric(table.iloc[:, idx], errors="coerce")
        codes = table.iloc[:, idx + 1].astype(str).str.extract(r"(\d{4})", expand=False)
        candidate = pd.DataFrame({"rank": ranks, "stock_id": codes}).dropna()
        if candidate.empty:
            continue

        candidate["rank"] = candidate["rank"].astype(int)
        top = candidate[candidate["rank"].between(1, expected_size)].sort_values("rank")
        if top["rank"].tolist() == expected_ranks:
            return _validate_universe(top["stock_id"].tolist(), expected_size=expected_size)

    raise ValueError("Could not locate a rank/code column pair covering ranks 1-200")


def fetch_live_universe(
    url: str = TAIFEX_TAIEX_URL,
    timeout_sec: int = 20,
) -> tuple[list[str], dict[str, str]]:
    response = requests.get(url, timeout=timeout_sec)
    response.raise_for_status()

    tables = pd.read_html(StringIO(response.text))
    last_parse_error: Optional[Exception] = None
    for table in tables:
        try:
            stock_ids = _parse_taifex_top200_from_table(table)
            return stock_ids, {
                "universe_source": "live",
                "universe_as_of": datetime.today().strftime("%Y-%m-%d"),
                "source_url": url,
            }
        except ValueError as exc:
            last_parse_error = exc
            continue

    raise RuntimeError(
        "TAIFEX page fetched successfully, but the top-200 table could not be parsed"
        + (f": {last_parse_error}" if last_parse_error else "")
    )


def load_snapshot_universe(path: Optional[str] = None) -> tuple[list[str], dict[str, str]]:
    snapshot_path = path or SNAPSHOT_PATH
    with open(snapshot_path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)

    stock_ids = _validate_universe(payload.get("stock_ids", []))
    as_of = str(payload.get("as_of", "")).strip()
    if not as_of:
        raise ValueError("Snapshot is missing `as_of` metadata")

    metadata = {
        "universe_source": "snapshot_fallback",
        "universe_as_of": as_of,
        "source_url": str(payload.get("source_url", "")).strip(),
    }
    return stock_ids, metadata


def build_universe() -> tuple[list[str], dict[str, str]]:
    """Return the live TAIFEX top-200 universe, or a checked-in fallback snapshot."""
    live_error: Optional[Exception] = None

    try:
        stock_ids, metadata = fetch_live_universe()
        log.info("Universe built from live TAIFEX source: %d stock IDs", len(stock_ids))
        return stock_ids, metadata
    except Exception as exc:  # noqa: BLE001
        live_error = exc
        log.warning("Live TAIFEX universe fetch failed: %s", exc)

    try:
        stock_ids, metadata = load_snapshot_universe()
        metadata["fallback_reason"] = str(live_error) if live_error else "live fetch unavailable"
        log.warning(
            "Universe loaded from snapshot fallback (%s): %d stock IDs",
            metadata["universe_as_of"],
            len(stock_ids),
        )
        return stock_ids, metadata
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            f"Failed to build the top-200 universe from both live TAIFEX and snapshot sources: "
            f"live_error={live_error}; snapshot_error={exc}"
        ) from exc


# ──────────────────────────────────────────────────────────────────────────
# Sector tilt — analyst-facing annotation (never a hard gate in V2)
# ──────────────────────────────────────────────────────────────────────────


@dataclass
class SectorTiltConfig:
    """Optional tilt overlay — annotative, not exclusionary (report §A2).

    Each bucket is `{reason: [stock_id, ...]}`. Analysts configure this to
    capture directional views without hard-rejecting names. The legacy G1
    exclusion buckets + favor IDs live in run_top200_screen.py-style config;
    the V2 default is an empty tilt (pure passthrough).
    """
    enabled: bool = False
    caution_buckets: dict[str, list[str]] = field(default_factory=dict)
    favor_ids: list[str] = field(default_factory=list)
    favor_reason: str = ""


def apply_sector_tilt(
    universe: list[str],
    tilt: Optional[SectorTiltConfig] = None,
) -> tuple[list[str], dict[str, dict]]:
    """Return universe unchanged plus a per-stock annotation dict.

    V2 never excludes on sector view — it annotates. `tilt_notes` maps
    stock_id → {"tilt": "caution"|"favor", "reason": str}. Stocks absent
    from the dict are neutral.
    """
    if tilt is None or not tilt.enabled:
        return list(universe), {}

    caution_by_id: dict[str, str] = {}
    for reason, ids in tilt.caution_buckets.items():
        for sid in ids:
            caution_by_id.setdefault(sid, reason)

    favor_set = set(tilt.favor_ids)

    tilt_notes: dict[str, dict] = {}
    for sid in universe:
        if sid in caution_by_id:
            tilt_notes[sid] = {"tilt": "caution", "reason": caution_by_id[sid]}
        elif sid in favor_set:
            tilt_notes[sid] = {"tilt": "favor", "reason": tilt.favor_reason or "sector tailwind"}

    return list(universe), tilt_notes
