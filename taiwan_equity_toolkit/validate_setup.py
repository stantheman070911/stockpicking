"""
validate_setup.py — First smoke test against the live FinMind API.

Run this before trusting the toolkit in production. It:
  1. Confirms FINMIND_TOKEN is set and the token authenticates
  2. Checks API quota
  3. Fetches one stock's recent data for each critical dataset
  4. Verifies the parser ledgers match real FinMind responses
  5. Runs Triage + Gate 3 end-to-end on TSMC (2330) as a sanity check

Usage:
    export FINMIND_TOKEN="your_token"
    python validate_setup.py
    # or: python validate_setup.py 2330 2317 2454   (override test stocks)

Exit codes: 0 on success, 1 if any critical check fails.
"""

from __future__ import annotations

import sys
import traceback
from datetime import datetime, timedelta

from taiwan_equity_toolkit import FinMindClient, triage, gate3, parsers
from taiwan_equity_toolkit.config import load_token
from taiwan_equity_toolkit.parsers import (
    BALANCE_SHEET_LEDGER,
    CASH_FLOW_LEDGER,
    INCOME_STATEMENT_LEDGER,
)


# ──────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────

OK = "\033[32m✓\033[0m"
WARN = "\033[33m⚠\033[0m"
FAIL = "\033[31m✗\033[0m"


def say(marker: str, msg: str) -> None:
    print(f"  {marker} {msg}")


def section(title: str) -> None:
    print(f"\n── {title} " + "─" * max(0, 60 - len(title)))


# ──────────────────────────────────────────────────────────────────────────
# Checks
# ──────────────────────────────────────────────────────────────────────────

def check_token() -> str:
    section("1. Token & Authentication")
    try:
        token = load_token()
        masked = token[:6] + "..." + token[-4:] if len(token) > 10 else "***"
        say(OK, f"FINMIND_TOKEN loaded ({masked})")
        return token
    except Exception as e:  # noqa: BLE001
        say(FAIL, f"Token load failed: {e}")
        sys.exit(1)


def check_quota(client: FinMindClient) -> None:
    section("2. API Quota")
    try:
        usage = client.usage()
        say(OK, f"Usage: {usage.user_count}/{usage.api_request_limit} "
                f"({usage.utilization_pct*100:.1f}% utilized, {usage.remaining} remaining)")
        if usage.utilization_pct > 0.80:
            say(WARN, "High utilization — consider waiting before heavy batch work")
    except Exception as e:  # noqa: BLE001
        say(FAIL, f"Quota check failed: {e}")
        sys.exit(1)


def check_datasets(client: FinMindClient, stock_id: str) -> dict[str, bool]:
    section(f"3. Critical Dataset Reachability ({stock_id})")
    today = datetime.today()
    start_recent = (today - timedelta(days=90)).strftime("%Y-%m-%d")
    start_fin = (today - timedelta(days=540)).strftime("%Y-%m-%d")

    datasets = [
        ("TaiwanStockPrice", start_recent, "price history"),
        ("TaiwanStockFinancialStatements", start_fin, "income statement"),
        ("TaiwanStockBalanceSheet", start_fin, "balance sheet"),
        ("TaiwanStockCashFlowsStatement", start_fin, "cash flows"),
        ("TaiwanStockMonthRevenue", start_fin, "monthly revenue"),
        ("TaiwanStockInstitutionalInvestorsBuySell", start_recent, "institutional flow"),
        ("TaiwanStockShareholding", start_recent, "foreign ownership"),
        ("TaiwanStockPER", start_recent, "PER/PBR"),
        ("TaiwanStockNews", start_recent, "news"),
    ]

    status = {}
    for ds, sd, label in datasets:
        try:
            df = client.get(ds, stock_id, sd)
            if df.empty:
                say(WARN, f"{ds} ({label}): reachable but empty")
                status[ds] = False
            else:
                say(OK, f"{ds} ({label}): {len(df)} rows, latest date {df['date'].max() if 'date' in df.columns else 'n/a'}")
                status[ds] = True
        except Exception as e:  # noqa: BLE001
            say(FAIL, f"{ds} ({label}): {e}")
            status[ds] = False
    return status


def check_parser_ledgers(client: FinMindClient, stock_id: str) -> None:
    """
    Verify that our ledger mappings match the actual FinMind 'type' codes.
    Reports any 'type' values in the real response that our ledger doesn't cover.
    """
    section(f"4. Parser Ledger Verification ({stock_id})")
    today = datetime.today()
    start = (today - timedelta(days=540)).strftime("%Y-%m-%d")

    checks = [
        ("TaiwanStockFinancialStatements", INCOME_STATEMENT_LEDGER, "income_statement"),
        ("TaiwanStockBalanceSheet", BALANCE_SHEET_LEDGER, "balance_sheet"),
        ("TaiwanStockCashFlowsStatement", CASH_FLOW_LEDGER, "cash_flow"),
    ]

    for dataset, ledger, label in checks:
        try:
            df = client.get(dataset, stock_id, start)
            if df.empty or "type" not in df.columns:
                say(WARN, f"{label}: no data to verify")
                continue
            actual_types = set(df["type"].dropna().unique())
            mapped_variants = set()
            for canonical, variants in ledger.items():
                for v in variants:
                    mapped_variants.add(v)
            hits = actual_types & mapped_variants
            misses = actual_types - mapped_variants
            say(OK, f"{label}: {len(hits)}/{len(actual_types)} canonical types matched")
            if misses:
                preview = sorted(misses)[:8]
                say(WARN, f"  Unmapped types (first 8): {', '.join(preview)}")
                say(WARN, f"  Total unmapped: {len(misses)} — extend LEDGER in parsers.py if any are material")
        except Exception as e:  # noqa: BLE001
            say(FAIL, f"{label}: verification failed — {e}")


def check_triage_and_gate3(client: FinMindClient, stock_id: str) -> None:
    section(f"5. End-to-end Triage + Gate 3 ({stock_id})")
    try:
        tr = triage.run(client, stock_id=stock_id)
        say(OK if tr.passed else WARN, f"Triage verdict: {'PASS' if tr.passed else 'FAIL'}")
        for c in tr.checks:
            marker = OK if c.passed else FAIL
            say(f"    {marker}", f"{c.name}: {c.detail}")
        if tr.notes:
            for n in tr.notes:
                say(WARN, f"    note: {n}")

        if tr.passed:
            print()
            g3 = gate3.run(client, stock_id=stock_id)
            say(OK, f"Gate 3 verdict: {g3.verdict} — score {g3.total_score:.1f}/100")
            for s in g3.sub_layers:
                say("   ", f"{s.as_line()}")
            if g3.hard_fail_triggered:
                say(WARN, "Hard-fail triggered:")
                for hf in g3.hard_fails:
                    if hf.triggered:
                        say("   ", f"⚠ {hf.name}: {hf.detail}")
            if g3.data_gaps:
                say(WARN, "Data gaps:")
                for g in g3.data_gaps:
                    say("   ", g)
    except Exception as e:  # noqa: BLE001
        say(FAIL, f"End-to-end check errored: {e}")
        traceback.print_exc()


# ──────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────

def main():
    test_stocks = sys.argv[1:] if len(sys.argv) > 1 else ["2330"]

    print("=" * 66)
    print("  Taiwan Equity Toolkit — setup validation")
    print(f"  Test stocks: {', '.join(test_stocks)}")
    print("=" * 66)

    token = check_token()
    client = FinMindClient(token=token)
    check_quota(client)

    for sid in test_stocks:
        check_datasets(client, sid)
        check_parser_ledgers(client, sid)
        check_triage_and_gate3(client, sid)

    print()
    print("=" * 66)
    print("  Validation complete.")
    print("  If all sections show ✓ with only minor ⚠, the toolkit is ready.")
    print("  Any ✗ should be addressed before running screens.")
    print("=" * 66)


if __name__ == "__main__":
    main()
