"""
Validate that the free-tier default path is runnable and that overlay-only
datasets are treated explicitly rather than implicitly required.
"""

from __future__ import annotations

import sys
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from taiwan_equity_toolkit import FinMindClient
from taiwan_equity_toolkit.config import load_token
from taiwan_equity_toolkit.data_policy import (
    POINT_IN_TIME_POLICY,
    TAIWAN_TRANSACTION_COSTS,
    dataset_tier,
)
from taiwan_equity_toolkit.models import StrategyMode
from taiwan_equity_toolkit.synthesis import synthesize_candidate
from taiwan_equity_toolkit.workstream_company import run as run_company_workstream
from taiwan_equity_toolkit.workstream_industry import run as run_industry_workstream
from taiwan_equity_toolkit.workstream_setup import run as run_setup_workstream


OK = "\033[32m✓\033[0m"
WARN = "\033[33m⚠\033[0m"
FAIL = "\033[31m✗\033[0m"

FREE_TIER_DATASETS = [
    "TaiwanStockInfo",
    "TaiwanStockPrice",
    "TaiwanStockPriceAdj",
    "TaiwanStockPER",
    "TaiwanStockFinancialStatements",
    "TaiwanStockBalanceSheet",
    "TaiwanStockCashFlowsStatement",
    "TaiwanStockMonthRevenue",
    "TaiwanStockInstitutionalInvestorsBuySell",
    "TaiwanStockShareholding",
    "TaiwanStockMarginPurchaseShortSale",
]

OVERLAY_DATASETS = [
    "TaiwanStockIndustryChain",
    "TaiwanBusinessIndicator",
    "TaiwanStockConvertibleBondInfo",
    "TaiwanStockTradingDailyReport",
]


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
    except Exception as exc:  # noqa: BLE001
        say(FAIL, f"Token load failed: {exc}")
        raise RuntimeError(f"Token load failed: {exc}") from exc


def check_quota(client: FinMindClient, status: ValidationStatus) -> None:
    section("2. API Quota")
    try:
        usage = client.usage()
        say(
            OK,
            f"Usage: {usage.user_count}/{usage.api_request_limit} "
            f"({usage.utilization_pct*100:.1f}% utilized, {usage.remaining} remaining)",
        )
        if usage.remaining < 100:
            status.add_warning("Remaining quota is below 100 requests.")
            say(WARN, "Remaining quota is below 100 requests.")
    except Exception as exc:  # noqa: BLE001
        say(FAIL, f"Quota check failed: {exc}")
        raise RuntimeError(f"Quota check failed: {exc}") from exc


def check_datasets(client: FinMindClient, stock_id: str, status: ValidationStatus) -> None:
    section(f"3. Free-tier dataset reachability ({stock_id})")
    today = datetime.today()
    start_recent = (today - timedelta(days=120)).strftime("%Y-%m-%d")
    start_fin = (today - timedelta(days=730)).strftime("%Y-%m-%d")

    dataset_windows = {
        "TaiwanStockInfo": None,
        "TaiwanStockPrice": start_recent,
        "TaiwanStockPriceAdj": start_recent,
        "TaiwanStockPER": start_recent,
        "TaiwanStockFinancialStatements": start_fin,
        "TaiwanStockBalanceSheet": start_fin,
        "TaiwanStockCashFlowsStatement": start_fin,
        "TaiwanStockMonthRevenue": start_fin,
        "TaiwanStockInstitutionalInvestorsBuySell": start_recent,
        "TaiwanStockShareholding": start_recent,
        "TaiwanStockMarginPurchaseShortSale": start_recent,
    }

    for dataset in FREE_TIER_DATASETS:
        try:
            df = client.get(dataset, stock_id if dataset != "TaiwanStockInfo" else None, dataset_windows[dataset])
            if df.empty:
                say(FAIL, f"{dataset}: reachable but empty")
                status.add_fatal(f"{stock_id}: {dataset} reachable but empty")
            else:
                latest = df["date"].max() if "date" in df.columns else "n/a"
                say(OK, f"{dataset}: {len(df)} rows, latest {latest}")
        except Exception as exc:  # noqa: BLE001
            say(FAIL, f"{dataset}: {exc}")
            status.add_fatal(f"{stock_id}: {dataset}: {exc}")

    section(f"4. Overlay-only datasets are explicit ({stock_id})")
    for dataset in OVERLAY_DATASETS:
        say(WARN, f"{dataset}: tier={dataset_tier(dataset)} (overlay only in V2)")


def check_triage_and_gate3(client: FinMindClient, stock_id: str, status: ValidationStatus) -> None:
    section(f"5. Free-tier V2 path ({stock_id})")
    try:
        industry = run_industry_workstream(client, stock_id=stock_id, strategy_mode=StrategyMode.TACTICAL_LONG_SHORT)
        company = run_company_workstream(client, stock_id=stock_id, strategy_mode=StrategyMode.TACTICAL_LONG_SHORT)
        setup, extras = run_setup_workstream(
            client,
            stock_id=stock_id,
            strategy_mode=StrategyMode.TACTICAL_LONG_SHORT,
            existing_book=[],
        )
        assessment = synthesize_candidate(
            stock_id=stock_id,
            strategy_mode=StrategyMode.TACTICAL_LONG_SHORT,
            industry=industry,
            company=company,
            setup=setup,
            sizing_band=extras.get("sizing_band"),
        )
        say(OK, f"Industry/Macro: {industry.status.value} | score {industry.score}")
        say(OK, f"Company Quality: {company.status.value} | score {company.score}")
        say(OK, f"Setup/Entry: {setup.status.value} | score {setup.score}")
        say(OK, f"Synthesis: {assessment.status.value} | composite {assessment.composite_score}")
    except Exception as exc:  # noqa: BLE001
        say(FAIL, f"V2 path errored: {exc}")
        traceback.print_exc()
        status.add_fatal(f"{stock_id}: V2 path errored: {exc}")


def print_summary(status: ValidationStatus) -> None:
    print()
    print("=" * 66)
    print("  Point-in-time policy")
    print(f"  {POINT_IN_TIME_POLICY}")
    print("  Taiwan transaction costs")
    for key, value in TAIWAN_TRANSACTION_COSTS.items():
        print(f"  - {key}: {value}")
    print("=" * 66)
    if status.fatal_errors:
        print("  Validation failed.")
        print(f"  Fatal issues: {len(status.fatal_errors)}")
        print(f"  Warnings: {len(status.warnings)}")
    elif status.warnings:
        print("  Validation completed with warnings.")
        print(f"  Warnings: {len(status.warnings)}")
    else:
        print("  Validation completed cleanly.")
    print("=" * 66)


def main() -> int:
    test_stocks = sys.argv[1:] if len(sys.argv) > 1 else ["2330"]
    status = ValidationStatus()

    print("=" * 66)
    print("  Taiwan Equity Toolkit — V2 setup validation")
    print(f"  Test stocks: {', '.join(test_stocks)}")
    print("=" * 66)

    try:
        token = check_token()
        client = FinMindClient(token=token)
        check_quota(client, status)
        for stock_id in test_stocks:
            check_datasets(client, stock_id, status)
            check_triage_and_gate3(client, stock_id, status)
    except Exception as exc:  # noqa: BLE001
        status.add_fatal(str(exc))

    print_summary(status)
    return 1 if status.fatal_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
