"""
Top-200 TAIEX V2 screen.

Default path:
- free-tier-compatible
- three parallel workstreams per stock
- synthesis checkpoint instead of sequential gate stops
- explicit passed / failed / not_assessed / manual_review_required states
"""

from __future__ import annotations

import json
import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from io import StringIO
from typing import Optional

import pandas as pd
import requests

sys.path.insert(0, os.path.dirname(__file__))

from taiwan_equity_toolkit.client import FinMindClient
from taiwan_equity_toolkit.data_policy import POINT_IN_TIME_POLICY, TAIWAN_TRANSACTION_COSTS, removed_signal_entries
from taiwan_equity_toolkit.models import (
    AssessmentStatus,
    CandidateAssessment,
    ScreenResultsV2,
    StrategyMode,
    WorkstreamResult,
)
from taiwan_equity_toolkit.synthesis import SynthesisInputs, primary_reason, synthesize_candidate
from taiwan_equity_toolkit.workstream_company import run as run_company_workstream
from taiwan_equity_toolkit.workstream_industry import run as run_industry_workstream
from taiwan_equity_toolkit.workstream_setup import run as run_setup_workstream


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
log = logging.getLogger("screen_v2")

# Tokens are documented in Finmind.md and kept here to preserve the existing
# one-command screen workflow.
TOKEN_PRIMARY = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoic3RhbnRoZW1hbjkxMSIsImVtYWlsIjoibGV0c3RhbmxleWNvb2s5MTFAZ21haWwuY29tIn0.iVbgBEQp5UzBSwGHPaSRXCqrhPTImxA_0QD6goxrnUI"
TOKEN_BACKUP = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoic3RhbmludmVzdCIsImVtYWlsIjoibGFteWx1MDgxMUBnbWFpbC5jb20ifQ.gktNshv39_O-CRQC1OiigXJt-BEdFPSd3gt3N0-Vbt0"
TOKEN = TOKEN_PRIMARY
ACTIVE_TOKEN_LABEL = "PRIMARY"

RESULTS_PATH = os.path.join(os.path.dirname(__file__), "screen_results.json")
TAIFEX_TAIEX_URL = "https://www.taifex.com.tw/cht/9/futuresQADetail"
SNAPSHOT_PATH = os.path.join(os.path.dirname(__file__), "data", "taiex_top200_snapshot.json")
UNIVERSE_SIZE = 200
DEFAULT_STRATEGY_MODE = StrategyMode.TACTICAL_LONG_SHORT
OUTER_WORKERS = 6


def get_active_token() -> str:
    global TOKEN, ACTIVE_TOKEN_LABEL
    client = FinMindClient(token=TOKEN)
    try:
        usage = client.usage()
        if usage.remaining < 100 and TOKEN == TOKEN_PRIMARY:
            TOKEN = TOKEN_BACKUP
            ACTIVE_TOKEN_LABEL = "BACKUP"
            log.info("Token failover: switched to backup token.")
    except Exception as exc:  # noqa: BLE001
        log.warning("Token usage check unavailable: %s", exc)
    return TOKEN


def _normalize_stock_ids(raw_values: list[object]) -> list[str]:
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


def _parse_taifex_top200_from_table(table: pd.DataFrame, expected_size: int = UNIVERSE_SIZE) -> list[str]:
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


def fetch_live_universe(url: str = TAIFEX_TAIEX_URL, timeout_sec: int = 20) -> tuple[list[str], dict[str, str]]:
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
    return stock_ids, {
        "universe_source": "snapshot_fallback",
        "universe_as_of": as_of,
        "source_url": str(payload.get("source_url", "")).strip(),
    }


def build_universe() -> tuple[list[str], dict[str, str]]:
    live_error: Optional[Exception] = None
    try:
        stock_ids, metadata = fetch_live_universe()
        log.info("Universe built from live TAIFEX source: %d stock IDs", len(stock_ids))
        return stock_ids, metadata
    except Exception as exc:  # noqa: BLE001
        live_error = exc
        log.warning("Live TAIFEX universe fetch failed: %s", exc)

    stock_ids, metadata = load_snapshot_universe()
    metadata["fallback_reason"] = str(live_error) if live_error else "live fetch unavailable"
    log.warning("Universe loaded from snapshot fallback (%s)", metadata["universe_as_of"])
    return stock_ids, metadata


def apply_gate1(stock_ids: list[str]) -> tuple[list[str], dict[str, dict[str, str]]]:
    return list(stock_ids), {}


def _status_priority(status: AssessmentStatus) -> int:
    order = {
        AssessmentStatus.PASSED: 0,
        AssessmentStatus.MANUAL_REVIEW_REQUIRED: 1,
        AssessmentStatus.NOT_ASSESSED: 2,
        AssessmentStatus.FAILED: 3,
    }
    return order[status]


def _assessment_row(assessment: CandidateAssessment) -> dict[str, object]:
    entry_verdict = assessment.setup.metadata.get("entry_verdict")
    return {
        "stock_id": assessment.stock_id,
        "status": assessment.status.value,
        "composite_score": assessment.composite_score,
        "thesis_stub": assessment.thesis_stub,
        "primary_reason": primary_reason(assessment),
        "industry_status": assessment.industry.status.value,
        "company_status": assessment.company.status.value,
        "setup_status": assessment.setup.status.value,
        "industry_score": assessment.industry.score,
        "company_score": assessment.company.score,
        "setup_score": assessment.setup.score,
        "entry_verdict": entry_verdict,
        "manual_requirement_count": len(assessment.manual_requirements),
        "sizing_band": assessment.sizing_band.to_dict() if assessment.sizing_band else None,
    }


def _error_workstream(name: str, detail: str) -> WorkstreamResult:
    return WorkstreamResult(
        name=name,
        status=AssessmentStatus.FAILED,
        notes=[detail],
        metadata={"error": detail},
    )


def _error_assessment(stock_id: str, strategy_mode: StrategyMode, detail: str) -> CandidateAssessment:
    industry = _error_workstream("Industry/Macro", detail)
    company = _error_workstream("Company Quality", detail)
    setup = _error_workstream("Setup/Entry", detail)
    assessment = synthesize_candidate(
        stock_id=stock_id,
        strategy_mode=strategy_mode,
        industry=industry,
        company=company,
        setup=setup,
        inputs=SynthesisInputs(thesis=f"{stock_id}: screening errored"),
    )
    assessment.status = AssessmentStatus.FAILED
    assessment.composite_score = 0.0
    assessment.metadata["primary_reason"] = detail
    return assessment


def _screen_single_stock(
    token: str,
    stock_id: str,
    strategy_mode: StrategyMode,
    stock_info_df: pd.DataFrame,
    macro_context: Optional[dict] = None,
    existing_book: Optional[list[str]] = None,
) -> CandidateAssessment:
    client = FinMindClient(token=token)
    try:
        with ThreadPoolExecutor(max_workers=3) as pool:
            industry_future = pool.submit(
                run_industry_workstream,
                client,
                stock_id,
                strategy_mode,
                stock_info_df,
                macro_context,
            )
            company_future = pool.submit(
                run_company_workstream,
                client,
                stock_id,
                strategy_mode,
            )
            setup_future = pool.submit(
                run_setup_workstream,
                client,
                stock_id,
                strategy_mode,
                existing_book or [],
            )

            industry = industry_future.result()
            company = company_future.result()
            setup, extras = setup_future.result()

        return synthesize_candidate(
            stock_id=stock_id,
            strategy_mode=strategy_mode,
            industry=industry,
            company=company,
            setup=setup,
            inputs=SynthesisInputs(),
            sizing_band=extras.get("sizing_band"),
        )
    except Exception as exc:  # noqa: BLE001
        log.exception("Screen failed for %s", stock_id)
        return _error_assessment(stock_id, strategy_mode, f"screening error: {exc}")


def run_screen(
    universe: list[str],
    metadata: dict[str, str],
    strategy_mode: StrategyMode = DEFAULT_STRATEGY_MODE,
    existing_book: Optional[list[str]] = None,
) -> ScreenResultsV2:
    token = get_active_token()
    usage_before = None
    usage_after = None
    stock_info_df = pd.DataFrame()

    try:
        bootstrap_client = FinMindClient(token=token)
        usage_before = bootstrap_client.usage()
        stock_info_df = bootstrap_client.stock_info()
    except Exception as exc:  # noqa: BLE001
        log.warning("Bootstrap context partially unavailable: %s", exc)

    assessments: list[CandidateAssessment] = []
    with ThreadPoolExecutor(max_workers=OUTER_WORKERS) as pool:
        future_map = {
            pool.submit(
                _screen_single_stock,
                token,
                stock_id,
                strategy_mode,
                stock_info_df,
                None,
                existing_book,
            ): stock_id
            for stock_id in universe
        }
        for future in as_completed(future_map):
            assessments.append(future.result())

    try:
        usage_after = FinMindClient(token=token).usage()
    except Exception as exc:  # noqa: BLE001
        log.warning("Final usage check unavailable: %s", exc)

    assessments.sort(key=lambda item: (_status_priority(item.status), -item.composite_score, item.stock_id))
    ranked_rows = [_assessment_row(assessment) for assessment in assessments]
    top10 = [row for row in ranked_rows if row["status"] != AssessmentStatus.FAILED.value][:10]

    funnel = {
        "started": len(universe),
        "industry_failed": len([item for item in assessments if item.industry.status == AssessmentStatus.FAILED]),
        "company_failed": len([item for item in assessments if item.company.status == AssessmentStatus.FAILED]),
        "setup_failed": len([item for item in assessments if item.setup.status == AssessmentStatus.FAILED]),
        "final_passed": len([item for item in assessments if item.status == AssessmentStatus.PASSED]),
        "final_manual_review_required": len([item for item in assessments if item.status == AssessmentStatus.MANUAL_REVIEW_REQUIRED]),
        "final_not_assessed": len([item for item in assessments if item.status == AssessmentStatus.NOT_ASSESSED]),
        "final_failed": len([item for item in assessments if item.status == AssessmentStatus.FAILED]),
        "ranked_non_failed": len([item for item in assessments if item.status != AssessmentStatus.FAILED]),
    }

    payload = ScreenResultsV2(
        run_date=datetime.today().strftime("%Y-%m-%d"),
        strategy_mode=strategy_mode,
        universe_source=metadata["universe_source"],
        universe_as_of=metadata["universe_as_of"],
        funnel=funnel,
        top10=top10,
        all_ranked=ranked_rows,
        removed_or_downgraded_signals=removed_signal_entries(),
        metadata={
            "source_url": metadata.get("source_url", ""),
            "fallback_reason": metadata.get("fallback_reason", ""),
            "active_token_label": ACTIVE_TOKEN_LABEL,
            "point_in_time_policy": POINT_IN_TIME_POLICY,
            "taiwan_transaction_costs": TAIWAN_TRANSACTION_COSTS,
            "token_usage_before": {
                "remaining": usage_before.remaining,
                "limit": usage_before.api_request_limit,
            } if usage_before else None,
            "token_usage_after": {
                "remaining": usage_after.remaining,
                "limit": usage_after.api_request_limit,
            } if usage_after else None,
        },
    )
    return payload


def main() -> list[dict[str, object]]:
    universe, metadata = build_universe()
    payload = run_screen(universe, metadata)
    with open(RESULTS_PATH, "w", encoding="utf-8") as handle:
        json.dump(payload.to_dict(), handle, ensure_ascii=False, indent=2)
    log.info("Wrote V2 results to %s", RESULTS_PATH)
    return payload.top10


if __name__ == "__main__":
    main()
