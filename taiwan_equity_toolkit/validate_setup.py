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
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from taiwan_equity_toolkit import FinMindClient, mass_triage, gate3
from taiwan_equity_toolkit.config import load_token
from taiwan_equity_toolkit.states import Status
from taiwan_equity_toolkit.parsers import (
    BALANCE_SHEET_LEDGER,
    CASH_FLOW_LEDGER,
    INCOME_STATEMENT_LEDGER,
)


OK = "\033[32m✓\033[0m"
WARN = "\033[33m⚠\033[0m"
FAIL = "\033[31m✗\033[0m"

REQUIRED_BASELINE_DATASETS = {
    "TaiwanStockPrice",
    "TaiwanStockFinancialStatements",
    "TaiwanStockBalanceSheet",
    "TaiwanStockCashFlowsStatement",
    "TaiwanStockMonthRevenue",
    "TaiwanStockInstitutionalInvestorsBuySell",
    "TaiwanStockShareholding",
}
WARNING_ONLY_DATASETS = {
    "TaiwanStockPER",
    "TaiwanStockNews",
}


@dataclass
class ValidationStatus:
    fatal_errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_fatal(self, message: str) -> None:
        self.fatal_errors.append(message)

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)


def say(marker: str, msg: str) -> None:
    print(f"  {marker} {msg}")


def section(title: str) -> None:
    print(f"\n── {title} " + "─" * max(0, 60 - len(title)))


def check_token() -> str:
    section("1. Token & Authentication")
    try:
        token = load_token()
        masked = token[:6] + "..." + token[-4:] if len(token) > 10 else "***"
        say(OK, f"FINMIND_TOKEN loaded ({masked})")
        return token
    except Exception as e:  # noqa: BLE001
        say(FAIL, f"Token load failed: {e}")
        raise RuntimeError(f"Token load failed: {e}") from e


def check_quota(client: FinMindClient, status: ValidationStatus) -> None:
    section("2. API Quota")
    try:
        usage = client.usage()
        say(
            OK,
            f"Usage: {usage.user_count}/{usage.api_request_limit} "
            f"({usage.utilization_pct*100:.1f}% utilized, {usage.remaining} remaining)",
        )
        if usage.utilization_pct > 0.80:
            message = "High utilization — consider waiting before heavy batch work"
            say(WARN, message)
            status.add_warning(message)
    except Exception as e:  # noqa: BLE001
        say(FAIL, f"Quota check failed: {e}")
        raise RuntimeError(f"Quota check failed: {e}") from e


def check_datasets(client: FinMindClient, stock_id: str, status: ValidationStatus) -> None:
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

    for dataset, start_date, label in datasets:
        is_required = dataset in REQUIRED_BASELINE_DATASETS
        try:
            df = client.get(dataset, stock_id, start_date)
            if df.empty:
                message = f"{dataset} ({label}): reachable but empty"
                if is_required:
                    say(FAIL, message)
                    status.add_fatal(f"{stock_id}: {message}")
                else:
                    say(WARN, message)
                    status.add_warning(f"{stock_id}: {message}")
                continue

            latest_date = df["date"].max() if "date" in df.columns else "n/a"
            say(OK, f"{dataset} ({label}): {len(df)} rows, latest date {latest_date}")
        except Exception as e:  # noqa: BLE001
            message = f"{dataset} ({label}): {e}"
            if is_required:
                say(FAIL, message)
                status.add_fatal(f"{stock_id}: {message}")
            else:
                say(WARN, message)
                status.add_warning(f"{stock_id}: {message}")


def check_parser_ledgers(client: FinMindClient, stock_id: str, status: ValidationStatus) -> None:
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
                message = f"{label}: no data to verify"
                say(WARN, message)
                status.add_warning(f"{stock_id}: {message}")
                continue

            actual_types = set(df["type"].dropna().unique())
            mapped_variants = {
                variant
                for variants in ledger.values()
                for variant in variants
            }
            hits = actual_types & mapped_variants
            misses = actual_types - mapped_variants
            say(OK, f"{label}: {len(hits)}/{len(actual_types)} canonical types matched")
            if misses:
                preview = sorted(misses)[:8]
                say(WARN, f"  Unmapped types (first 8): {', '.join(preview)}")
                say(WARN, f"  Total unmapped: {len(misses)} — extend LEDGER in parsers.py if any are material")
                status.add_warning(f"{stock_id}: {label} has {len(misses)} unmapped type(s)")
        except Exception as e:  # noqa: BLE001
            say(FAIL, f"{label}: verification failed — {e}")
            status.add_fatal(f"{stock_id}: {label} verification failed — {e}")


def check_triage_and_gate3(client: FinMindClient, stock_id: str, status: ValidationStatus) -> None:
    section(f"5. End-to-end Triage + Gate 3 ({stock_id})")
    try:
        tr = mass_triage.run(client, stock_id=stock_id)
        triage_passed = tr.status != Status.FAILED
        say(OK if triage_passed else WARN, f"Triage verdict: {tr.status.value.upper()}")
        for check in tr.checks:
            if check.status == Status.NOT_ASSESSED:
                marker = WARN
            else:
                marker = OK if check.status == Status.PASSED else FAIL
            say(f"    {marker}", f"{check.name}: {check.detail}")
        if tr.notes:
            for note in tr.notes:
                say(WARN, f"    note: {note}")
                status.add_warning(f"{stock_id}: {note}")

        if not triage_passed:
            failure_names = ", ".join(check.name for check in tr.failures()) or "unknown reason"
            status.add_warning(f"{stock_id}: triage sanity run failed ({failure_names})")
            return

        print()
        g3 = gate3.run(client, stock_id=stock_id)
        say(OK, f"Gate 3 verdict: {g3.verdict} — score {g3.total_score:.1f}/100")
        for sub_layer in g3.sub_layers:
            say("   ", f"{sub_layer.as_line()}")
        if g3.hard_fail_triggered:
            say(WARN, "Hard-fail triggered:")
            status.add_warning(f"{stock_id}: Gate 3 hard-fail triggered during validation")
            for finding in g3.hard_fails:
                if finding.triggered:
                    say("   ", f"⚠ {finding.name}: {finding.detail}")
        if g3.data_gaps:
            say(WARN, "Data gaps:")
            for gap in g3.data_gaps:
                say("   ", gap)
                status.add_warning(f"{stock_id}: {gap}")
    except Exception as e:  # noqa: BLE001
        say(FAIL, f"End-to-end check errored: {e}")
        traceback.print_exc()
        status.add_fatal(f"{stock_id}: End-to-end check errored: {e}")


def print_summary(status: ValidationStatus) -> None:
    print()
    print("=" * 66)
    if status.fatal_errors:
        print("  Validation failed.")
        print(f"  Fatal issues: {len(status.fatal_errors)}")
        print(f"  Warnings: {len(status.warnings)}")
        print("  Address all ✗ items before running screens.")
    elif status.warnings:
        print("  Validation completed with warnings.")
        print(f"  Warnings: {len(status.warnings)}")
        print("  The toolkit is usable, but review the warnings before relying on all checks.")
    else:
        print("  Validation completed cleanly.")
        print("  All critical checks passed without warnings.")
    print("=" * 66)


def main() -> int:
    test_stocks = sys.argv[1:] if len(sys.argv) > 1 else ["2330"]
    status = ValidationStatus()

    print("=" * 66)
    print("  Taiwan Equity Toolkit — setup validation")
    print(f"  Test stocks: {', '.join(test_stocks)}")
    print("=" * 66)

    try:
        token = check_token()
        client = FinMindClient(token=token)
        check_quota(client, status)
    except RuntimeError as exc:
        status.add_fatal(str(exc))
        print_summary(status)
        return 1

    for stock_id in test_stocks:
        check_datasets(client, stock_id, status)
        check_parser_ledgers(client, stock_id, status)
        check_triage_and_gate3(client, stock_id, status)

    print_summary(status)
    return 1 if status.fatal_errors else 0


if __name__ == "__main__":
    sys.exit(main())
