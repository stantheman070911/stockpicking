"""
Top-200 TAIEX Full Funnel Screen (Free-Tier Compatible)
=========================================================
Pipeline:
  Step 0: Universe — embedded TAIEX Top ~200 by market cap (verified Apr 2026 order)
  Step 1: Gate 1+2 — industry directional filter (semi/server/financials favored;
          shipping/steel/cement excluded)
  Step 2: Mass Triage — parallel, cuts illiquid/suspended/collapsing names
  Step 3: Gate 3 — Forensic Quality (100-pt scorecard) on triage passers
  Step 4: Gate 4 — Peer validation on Gate 3 survivors
  Step 5: Gate 5 — Value-chain positioning on Gate 4 survivors
  Step 6: Gate 6.5 — Entry Architecture (valuation, vol, liquidity)
  Output: Ranked final list → top 10 with Gate 7 thesis stubs
"""

import os
import sys
import json
import time
import logging
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import StringIO
from typing import Optional

import pandas as pd
import requests

sys.path.insert(0, os.path.dirname(__file__))
from taiwan_equity_toolkit.client import FinMindClient
from taiwan_equity_toolkit import triage, gate3, gate65, peers, value_chain
from taiwan_equity_toolkit.config import INDUSTRY_ANCHORS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
log = logging.getLogger("screen")

# ── Tokens — primary + backup failover ────────────────────────────────────────
TOKEN_PRIMARY = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoic3RhbnRoZW1hbjkxMSIsImVtYWlsIjoibGV0c3RhbmxleWNvb2s5MTFAZ21haWwuY29tIn0.iVbgBEQp5UzBSwGHPaSRXCqrhPTImxA_0QD6goxrnUI"
TOKEN_BACKUP  = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoic3RhbmludmVzdCIsImVtYWlsIjoibGFteWx1MDgxMUBnbWFpbC5jb20ifQ.gktNshv39_O-CRQC1OiigXJt-BEdFPSd3gt3N0-Vbt0"
# Active token — starts with primary, auto-falls-over to backup on 402
TOKEN = TOKEN_PRIMARY
ACTIVE_TOKEN_LABEL = "PRIMARY"

def get_active_token() -> str:
    """Return the current active token. Falls over to backup if primary is exhausted."""
    global TOKEN, ACTIVE_TOKEN_LABEL
    client = FinMindClient(token=TOKEN)
    try:
        usage = client.usage()
        if usage.remaining <= 30:  # switch before hitting the wall
            if TOKEN == TOKEN_PRIMARY:
                TOKEN = TOKEN_BACKUP
                ACTIVE_TOKEN_LABEL = "BACKUP"
                log.info("Token failover: switching to BACKUP token (primary at %d/%d)",
                         usage.user_count, usage.api_request_limit)
    except Exception:
        pass
    return TOKEN

INTENDED_POSITION_NTD = 5_000_000
TRIAGE_WORKERS = 8
GATE3_WORKERS  = 4
TODAY = datetime.today()
RESULTS_PATH = os.path.join(os.path.dirname(__file__), "screen_results.json")
TAIFEX_TAIEX_URL = "https://www.taifex.com.tw/cht/9/futuresQADetail"
UNIVERSE_SIZE = 200
SNAPSHOT_PATH = os.path.join(os.path.dirname(__file__), "data", "taiex_top200_snapshot.json")


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

# ── Gate 1 industry context ───────────────────────────────────────────────────
# Apr 2026 macro read:
# - Taiwan Business Indicator monitoring signal: YELLOW (caution zone but not recession)
# - AI server capex cycle: intact — accelerating CoWoS, HBM, advanced packaging demand
# - USD/TWD: ~32.5 (TWD weakening mildly — export sector tailwind for FX-sensitive names)
# - US tariff rhetoric: elevated but TSMC/OSAT exempt for now (national security carve-out)
# - Domestic: soft consumer spending; financials stable on NIM recovery
# - Shipping: freight rates normalizing post-Red Sea premium; overcapacity rebuilding

G1_EXCLUSION_BUCKETS = [
    (
        "Shipping — freight rates normalizing and overcapacity rebuilding",
        {"2603", "2609", "2615", "2618", "2610"},
    ),
    (
        "Steel/cement/basic materials — China demand drag and weak cycle support",
        {"2002", "2006", "2014", "2027", "1101", "1102", "1802"},
    ),
    (
        "Petrochemical/plastics — margin compression and China supply glut",
        {"1301", "1303", "1326", "6505", "1314", "5009"},
    ),
    (
        "Biotech pre-revenue profile — no dated catalyst anchor",
        {"6547", "6446"},
    ),
    (
        "Legacy consumer electronics structural decline",
        {"2498", "2323"},
    ),
    (
        "Rubber/solar cycles outside current Gate 1 posture",
        {"2105", "6443"},
    ),
    (
        "Out-of-favor small/illiquid tail names for this deterministic batch funnel",
        {
            "3703", "3059", "2340", "3149", "2548", "6541",
            "2353", "4919", "2404", "2048", "1710", "2820",
            "3019", "4967", "3682", "3306", "6277", "2396",
            "3673", "6271", "1560", "4961",
        },
    ),
]
G1_REJECT_REASONS = {
    stock_id: reason
    for reason, stock_ids in G1_EXCLUSION_BUCKETS
    for stock_id in stock_ids
}

# Specifically favored (Gate 1 positive) — AI/semi supply chain, financials
G1_FAVOR_IDS = {
    "2330", "3711", "2308", "2303", "6488", "6239", "3529", "3443",  # semi
    "3034", "2379", "2337", "6415", "5274", "8299", "6533", "6416",  # IC design
    "2382", "4938", "2356", "3231", "2324", "6669",                   # server/ODM
    "3037", "8046", "4958", "6282", "3189",                           # advanced PCB
    "3017", "6121",                                                    # thermal/battery
    "2395", "2360",                                                    # industrial/test
    "2881", "2882", "2884", "2886", "2891", "5871", "5880",           # financials
    "2395", "1590",                                                    # industrial automation
    "3661",                                                            # Alchip — ASIC design
    "5269",                                                            # ASMedia USB4/PCIe
    "2327",                                                            # Yageo (passive components)
    "2492",                                                            # Walsin Tech (passive)
    "9910",                                                            # Feng Tay (Nike supplier)
}


def guess_peers(client: FinMindClient, stock_id: str, max_peers: int = 3) -> list[str]:
    """Best-effort peer list from seeded anchors, then industry-chain peers."""
    for members in INDUSTRY_ANCHORS.values():
        if stock_id in members:
            return [member for member in members if member != stock_id][:max_peers]

    chain_position = value_chain.locate(client, stock_id)
    return [member for member in chain_position.peers_in_chain if member != stock_id][:max_peers]


def _evaluate_gate4_comparison(comparison) -> tuple[bool, str]:
    rankings = getattr(comparison, "candidate_rankings", {}) or {}
    populated = {
        metric: (rank, total)
        for metric, (rank, total) in rankings.items()
        if rank and total and total >= 2
    }
    if len(populated) < 2:
        return False, "Insufficient populated peer metrics for Gate 4"

    top_half = [
        metric
        for metric, (rank, total) in populated.items()
        if rank <= ((total + 1) // 2)
    ]
    bottom_ranked = [
        metric
        for metric, (rank, total) in populated.items()
        if rank == total
    ]

    if not top_half:
        return False, f"No top-half peer rankings across {len(populated)} populated metric(s)"
    if len(bottom_ranked) >= 2:
        return False, "Bottom-ranked on multiple peer metrics: " + ", ".join(bottom_ranked)

    return True, "Validated on populated peer metrics; top-half on " + ", ".join(top_half)


def apply_gate1(universe: list[str]) -> tuple[list[str], dict[str, dict[str, str]]]:
    """Gate 1 — deterministic directional industry filter with auditable rejects."""
    passers: list[str] = []
    rejects: dict[str, dict[str, str]] = {}
    for stock_id in universe:
        reason = G1_REJECT_REASONS.get(stock_id)
        if reason:
            rejects[stock_id] = {
                "gate": "Gate 1",
                "reason": reason,
            }
            continue
        passers.append(stock_id)

    log.info("Gate 1: %d pass, %d excluded", len(passers), len(rejects))
    return passers, rejects


def run_triage_single(args):
    client_token, stock_id = args
    client = FinMindClient(token=client_token)
    try:
        result = triage.run(client, stock_id, intended_position_ntd=INTENDED_POSITION_NTD)
        return stock_id, result
    except Exception as e:
        log.warning(f"Triage error {stock_id}: {e}")
        return stock_id, None


def run_mass_triage(stock_ids: list) -> tuple[list, dict]:
    log.info(f"Triage — {len(stock_ids)} names, {TRIAGE_WORKERS} workers...")
    triage_results = {}
    args = [(get_active_token(), sid) for sid in stock_ids]
    with ThreadPoolExecutor(max_workers=TRIAGE_WORKERS) as executor:
        futures = {executor.submit(run_triage_single, arg): arg[1] for arg in args}
        done = 0
        for future in as_completed(futures):
            sid = futures[future]
            try:
                stock_id, result = future.result()
                triage_results[stock_id] = result
                done += 1
                status = "PASS" if (result and result.passed) else "FAIL"
                if result and not result.passed:
                    failures_str = ", ".join(f"{c.name}: {c.detail}" for c in result.failures())
                    log.warning(f"  {stock_id} TRIAGE FAIL: {failures_str}")
                
                if done % 10 == 0 or done <= 5:
                    log.info(f"  [{done}/{len(stock_ids)}] {stock_id}: {status}")
            except Exception as e:
                log.warning(f"Triage future error {sid}: {e}")

    passers = [sid for sid, r in triage_results.items() if r and r.passed]
    log.info(f"Triage result: {len(passers)} pass / {len(stock_ids) - len(passers)} fail")
    return passers, triage_results


def run_gate3_single(args):
    client_token, stock_id = args
    client = FinMindClient(token=client_token)
    try:
        result = gate3.run(client, stock_id)
        return stock_id, result
    except Exception as e:
        log.warning(f"Gate 3 error {stock_id}: {e}")
        return stock_id, None


def run_gate3_batch(stock_ids: list) -> tuple[list, dict]:
    log.info(f"Gate 3 — Forensic Quality on {len(stock_ids)} names ({GATE3_WORKERS} workers)...")
    g3_results = {}
    args = [(get_active_token(), sid) for sid in stock_ids]
    with ThreadPoolExecutor(max_workers=GATE3_WORKERS) as executor:
        futures = {executor.submit(run_gate3_single, arg): arg[1] for arg in args}
        done = 0
        for future in as_completed(futures):
            sid = futures[future]
            try:
                stock_id, result = future.result()
                g3_results[stock_id] = result
                done += 1
                score = getattr(result, "total_score", "N/A") if result else "ERR"
                verdict = getattr(result, "verdict", "ERR") if result else "ERR"
                hf = getattr(result, "hard_fail_triggered", "?") if result else "?"
                log.info(f"  [{done}/{len(stock_ids)}] {stock_id}: score={score}, verdict={verdict}, hf={hf}")
            except Exception as e:
                log.warning(f"Gate 3 future error {sid}: {e}")

    passers, conditional = classify_gate3_results(g3_results)
    log.info(
        "Gate 3: %d Pass, %d Conditional Watchlist, %d Fail/Error",
        len(passers),
        len(conditional),
        len(g3_results) - len(passers) - len(conditional),
    )
    return passers, g3_results


def classify_gate3_results(g3_results: dict) -> tuple[list[str], list[str]]:
    passers = [
        sid for sid, r in g3_results.items()
        if r
        and not getattr(r, "hard_fail_triggered", True)
        and getattr(r, "verdict", "") == "Pass"
    ]
    conditional = [
        sid for sid, r in g3_results.items()
        if r
        and not getattr(r, "hard_fail_triggered", True)
        and getattr(r, "verdict", "") == "Conditional Watchlist"
    ]
    return passers, conditional


def run_gate65_single(args):
    client_token, stock_id, existing_book = args
    client = FinMindClient(token=client_token)
    try:
        result = gate65.run(client, stock_id,
                            existing_book=existing_book,
                            intended_position_ntd=INTENDED_POSITION_NTD)
        return stock_id, result
    except Exception as e:
        log.warning(f"Gate 6.5 error {stock_id}: {e}")
        return stock_id, None


def run_gate65_batch(stock_ids: list) -> tuple[list, dict]:
    existing_book: list[str] = []  # fresh portfolio
    log.info(f"Gate 6.5 — Entry Architecture on {len(stock_ids)} names...")
    g65_results = {}
    args = [(get_active_token(), sid, existing_book) for sid in stock_ids]
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(run_gate65_single, arg): arg[1] for arg in args}
        for future in as_completed(futures):
            sid = futures[future]
            try:
                stock_id, result = future.result()
                g65_results[stock_id] = result
                verdict = getattr(result, "verdict", "N/A") if result else "ERR"
                log.info(f"  Gate 6.5 {stock_id}: {verdict}")
            except Exception as e:
                log.warning(f"Gate 6.5 future error {sid}: {e}")

    passers = [
        sid for sid, r in g65_results.items()
        if r and getattr(r, "verdict", "") != "Reject for Book Fit"
    ]
    log.info(f"Gate 6.5: {len(passers)} pass, {len(stock_ids) - len(passers)} reject")
    return passers, g65_results


def run_gate4_single(args):
    client_token, stock_id = args
    client = FinMindClient(token=client_token)
    try:
        peer_ids = guess_peers(client, stock_id)
        if not peer_ids:
            return stock_id, {
                "passed": False,
                "peer_ids": [],
                "comparison": None,
                "reason": "No peer set identified for Gate 4",
            }

        comparison = peers.compare(client, candidate=stock_id, peers=peer_ids)
        passed, reason = _evaluate_gate4_comparison(comparison)
        return stock_id, {
            "passed": passed,
            "peer_ids": peer_ids,
            "comparison": comparison,
            "reason": reason,
        }
    except Exception as e:
        log.warning(f"Gate 4 error {stock_id}: {e}")
        return stock_id, {
            "passed": False,
            "peer_ids": [],
            "comparison": None,
            "reason": f"Gate 4 errored: {e}",
        }


def run_gate4_batch(stock_ids: list[str]) -> tuple[list[str], dict[str, dict]]:
    log.info(f"Gate 4 — Peer Validation on {len(stock_ids)} names...")
    gate4_results: dict[str, dict] = {}
    args = [(get_active_token(), sid) for sid in stock_ids]
    with ThreadPoolExecutor(max_workers=min(4, max(1, len(stock_ids)))) as executor:
        futures = {executor.submit(run_gate4_single, arg): arg[1] for arg in args}
        for future in as_completed(futures):
            sid = futures[future]
            try:
                stock_id, result = future.result()
                gate4_results[stock_id] = result
                status = "PASS" if result["passed"] else "FAIL"
                log.info(
                    "  Gate 4 %s: %s (%s)",
                    stock_id,
                    status,
                    result["reason"],
                )
            except Exception as e:
                log.warning(f"Gate 4 future error {sid}: {e}")

    passers = [sid for sid, result in gate4_results.items() if result.get("passed")]
    log.info(f"Gate 4: {len(passers)} pass, {len(stock_ids) - len(passers)} stop")
    return passers, gate4_results


def run_gate5_single(args):
    client_token, stock_id = args
    client = FinMindClient(token=client_token)
    try:
        report = value_chain.analyze(client, stock_id)
        has_position = bool(report.position.industries or report.position.sub_industries)
        usable_signal_count = sum(
            1 for signal in report.upstream_signals if value_chain.has_usable_signal(signal)
        )
        passed = has_position and usable_signal_count > 0
        if passed:
            reason = f"Value chain mapped with {usable_signal_count} usable upstream signal(s)"
        elif has_position:
            reason = "Value-chain position mapped, but usable upstream/downstream signals were unavailable"
        else:
            reason = "No value-chain context available"
        return stock_id, {
            "passed": passed,
            "report": report,
            "reason": reason,
        }
    except Exception as e:
        log.warning(f"Gate 5 error {stock_id}: {e}")
        return stock_id, {
            "passed": False,
            "report": None,
            "reason": f"Gate 5 errored: {e}",
        }


def run_gate5_batch(stock_ids: list[str]) -> tuple[list[str], dict[str, dict]]:
    log.info(f"Gate 5 — Value Chain on {len(stock_ids)} names...")
    gate5_results: dict[str, dict] = {}
    args = [(get_active_token(), sid) for sid in stock_ids]
    with ThreadPoolExecutor(max_workers=min(4, max(1, len(stock_ids)))) as executor:
        futures = {executor.submit(run_gate5_single, arg): arg[1] for arg in args}
        for future in as_completed(futures):
            sid = futures[future]
            try:
                stock_id, result = future.result()
                gate5_results[stock_id] = result
                status = "PASS" if result["passed"] else "FAIL"
                log.info(
                    "  Gate 5 %s: %s (%s)",
                    stock_id,
                    status,
                    result["reason"],
                )
            except Exception as e:
                log.warning(f"Gate 5 future error {sid}: {e}")

    passers = [sid for sid, result in gate5_results.items() if result.get("passed")]
    log.info(f"Gate 5: {len(passers)} pass, {len(stock_ids) - len(passers)} stop")
    return passers, gate5_results


def compile_final(
    ranked_ids: list,
    g3_results: dict,
    g65_results: dict,
    triage_results: dict,
    gate4_results: Optional[dict] = None,
    gate5_results: Optional[dict] = None,
    include_rejected: bool = False,
) -> list[dict]:
    verdict_weight = {
        "Enter Now": 30,
        "Stagger / Scale In": 20,
        "Wait for Setup": 10,
        "Reject for Book Fit": 0,
    }
    records = []
    for sid in ranked_ids:
        g3 = g3_results.get(sid)
        g65 = g65_results.get(sid)
        tr = triage_results.get(sid)
        g3_score = getattr(g3, "total_score", 0) if g3 else 0
        g65_verdict = getattr(g65, "verdict", "N/A") if g65 else "N/A"
        if not include_rejected and g65_verdict == "Reject for Book Fit":
            continue
        gate4 = (gate4_results or {}).get(sid, {})
        gate5 = (gate5_results or {}).get(sid, {})
        # Favor bias for G1 favorites
        g1_bonus = 5 if sid in G1_FAVOR_IDS else 0
        records.append({
            "stock_id": sid,
            "gate3_score": g3_score,
            "gate3_verdict": getattr(g3, "verdict", "N/A") if g3 else "N/A",
            "gate3_hard_fail": getattr(g3, "hard_fail_triggered", True) if g3 else True,
            "gate65_verdict": g65_verdict,
            "adv_ntd": getattr(tr, "adv_ntd", None) if tr else None,
            "g1_favored": sid in G1_FAVOR_IDS,
            "gate4_passed": gate4.get("passed"),
            "gate4_peer_count": len(gate4.get("peer_ids", [])),
            "gate5_passed": gate5.get("passed"),
            "composite": g3_score + verdict_weight.get(g65_verdict, 0) + g1_bonus,
        })
    records.sort(key=lambda x: x["composite"], reverse=True)
    return records


def main():
    global TOKEN, ACTIVE_TOKEN_LABEL
    log.info("=" * 70)
    log.info("TAIEX TOP-200 FULL FUNNEL SCREEN | %s", TODAY.strftime("%Y-%m-%d %H:%M"))
    log.info("=" * 70)

    # ── Token selection — check both, use whichever has quota ─────────────────
    for label, tok in [("PRIMARY", TOKEN_PRIMARY), ("BACKUP", TOKEN_BACKUP)]:
        try:
            c = FinMindClient(token=tok)
            u = c.usage()
            log.info(f"  {label} token: {u.user_count}/{u.api_request_limit} used "
                     f"({u.utilization_pct*100:.1f}%) — remaining: {u.remaining}")
        except Exception as e:
            log.warning(f"  {label} token quota check failed: {e}")

    # Auto-select: if primary exhausted, switch to backup immediately
    try:
        c_primary = FinMindClient(token=TOKEN_PRIMARY)
        u_primary = c_primary.usage()
        if u_primary.remaining <= 10:
            TOKEN = TOKEN_BACKUP
            ACTIVE_TOKEN_LABEL = "BACKUP"
            log.info("Active token: BACKUP (primary exhausted)")
        else:
            TOKEN = TOKEN_PRIMARY
            ACTIVE_TOKEN_LABEL = "PRIMARY"
            log.info("Active token: PRIMARY")
    except Exception:
        TOKEN = TOKEN_BACKUP
        ACTIVE_TOKEN_LABEL = "BACKUP"
        log.info("Active token: BACKUP (primary check failed)")

    # ── Step 0: Build universe ─────────────────────────────────────────────
    universe, universe_meta = build_universe()

    # ── Step 1: Gate 1 — industry filter ──────────────────────────────────
    g1_passers, g1_rejects = apply_gate1(universe)
    log.info(f"After Gate 1: {len(g1_passers)} candidates for triage")

    # ── Step 2: Mass Triage ────────────────────────────────────────────────
    triage_passers, triage_results = run_mass_triage(g1_passers)
    if not triage_passers:
        log.error("No names cleared triage. Aborting.")
        sys.exit(1)

    # ── Step 3: Gate 3 ─────────────────────────────────────────────────────
    g3_passers, g3_results = run_gate3_batch(triage_passers)
    _, g3_conditional = classify_gate3_results(g3_results)
    ranked_ids = list(g3_passers)

    # ── Step 4: Gate 6.5 ───────────────────────────────────────────────────
    gate4_results: dict[str, dict] = {}
    gate5_results: dict[str, dict] = {}
    if ranked_ids:
        ranked_ids, gate4_results = run_gate4_batch(ranked_ids)
        if ranked_ids:
            ranked_ids, gate5_results = run_gate5_batch(ranked_ids)
        gate65_passers, g65_results = run_gate65_batch(ranked_ids) if ranked_ids else ([], {})
        ranked_ids = gate65_passers
        ranking_label = "Gate 6.5 Passes"
    else:
        log.warning("No Gate 3 passes — advancing Conditional Watchlist names through Gates 4, 5, and 6.5")
        ranked_ids = list(g3_conditional)
        ranked_ids, gate4_results = run_gate4_batch(ranked_ids)
        if ranked_ids:
            ranked_ids, gate5_results = run_gate5_batch(ranked_ids)
        gate65_passers, g65_results = run_gate65_batch(ranked_ids) if ranked_ids else ([], {})
        ranked_ids = gate65_passers
        ranking_label = "Gate 3 Conditional Watchlist"

    # ── Step 5: Compile & rank ─────────────────────────────────────────────
    final = compile_final(
        ranked_ids,
        g3_results,
        g65_results,
        triage_results,
        gate4_results=gate4_results,
        gate5_results=gate5_results,
    )

    # ── Output ─────────────────────────────────────────────────────────────
    log.info("\n" + "=" * 70)
    log.info("RANKED SCREEN OUTPUT — %s", ranking_label.upper())
    log.info("=" * 70)
    for i, rec in enumerate(final, 1):
        adv = rec["adv_ntd"]
        adv_str = "N/A" if adv is None else f"NT${adv/1e6:.1f}M"
        log.info(
            f"  #{i:3d} | {rec['stock_id']} | G3:{rec['gate3_score']:5.1f} "
            f"({rec['gate3_verdict']:12s}) | G6.5:{rec['gate65_verdict']:20s} "
            f"| ADV:{adv_str} | Composite:{rec['composite']:6.1f}"
        )

    log.info("\n— TOP 10 SELECTIONS —")
    for i, rec in enumerate(final[:10], 1):
        log.info(f"  #{i:2d} {rec['stock_id']} | G3:{rec['gate3_score']:.1f} | {rec['gate65_verdict']}")

    # Save
    output = {
        "run_date": TODAY.strftime("%Y-%m-%d %H:%M"),
        "universe_source": universe_meta["universe_source"],
        "universe_as_of": universe_meta["universe_as_of"],
        "funnel": {
            "universe": len(universe),
            "gate1_pass": len(g1_passers),
            "triage_pass": len(triage_passers),
            "gate3_pass": len(g3_passers),
            "gate3_conditional": len(g3_conditional),
            "gate4_pass": len([sid for sid, result in gate4_results.items() if result.get("passed")]),
            "gate5_pass": len([sid for sid, result in gate5_results.items() if result.get("passed")]),
            "gate65_pass": len(ranked_ids),
            "final": len(final),
        },
        "top10": final[:10],
        "all_ranked": final,
        "gate1_rejects": g1_rejects,
        "triage_failures": {
            sid: [{"name": c.name, "detail": c.detail} for c in r.failures()]
            for sid, r in triage_results.items()
            if r and not r.passed
        },
        "gate3_details": {
            sid: {
                "total_score": getattr(r, "total_score", None),
                "verdict": getattr(r, "verdict", None),
                "hard_fail": getattr(r, "hard_fail_triggered", None),
            }
            for sid, r in g3_results.items() if r
        },
        "gate4_failures": {
            sid: {
                "reason": result.get("reason"),
                "peer_ids": result.get("peer_ids", []),
            }
            for sid, result in gate4_results.items()
            if not result.get("passed")
        },
        "gate5_failures": {
            sid: {
                "reason": result.get("reason"),
            }
            for sid, result in gate5_results.items()
            if not result.get("passed")
        },
    }
    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)

    log.info(f"\nFull results saved → {RESULTS_PATH}")
    log.info(
        f"Funnel: {len(universe)} universe → G1:{len(g1_passers)} → "
        f"Triage:{len(triage_passers)} → G3 Pass:{len(g3_passers)} "
        f"/ Conditional:{len(g3_conditional)} → Final:{len(final)}"
    )
    return final


if __name__ == "__main__":
    results = main()
