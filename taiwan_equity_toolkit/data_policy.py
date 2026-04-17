"""
Dataset-tier rules, score normalization, and validation policy for the V2 rebuild.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from taiwan_equity_toolkit.models import AssessmentStatus, CheckResult, ManualRequirement


class DatasetTier(str):
    FREE = "free"
    BACKER = "backer"
    SPONSOR = "sponsor"
    UNKNOWN = "unknown"


DATASET_TIER_MAP: dict[str, str] = {
    "TaiwanStockInfo": DatasetTier.FREE,
    "TaiwanStockPrice": DatasetTier.FREE,
    "TaiwanStockPriceAdj": DatasetTier.FREE,
    "TaiwanStockPER": DatasetTier.FREE,
    "TaiwanStockMarginPurchaseShortSale": DatasetTier.FREE,
    "TaiwanStockInstitutionalInvestorsBuySell": DatasetTier.FREE,
    "TaiwanStockShareholding": DatasetTier.FREE,
    "TaiwanStockSecuritiesLending": DatasetTier.FREE,
    "TaiwanDailyShortSaleBalances": DatasetTier.FREE,
    "TaiwanStockMarginShortSaleSuspension": DatasetTier.FREE,
    "TaiwanStockFinancialStatements": DatasetTier.FREE,
    "TaiwanStockBalanceSheet": DatasetTier.FREE,
    "TaiwanStockCashFlowsStatement": DatasetTier.FREE,
    "TaiwanStockDividend": DatasetTier.FREE,
    "TaiwanStockDividendResult": DatasetTier.FREE,
    "TaiwanStockMonthRevenue": DatasetTier.FREE,
    "TaiwanStockCapitalReductionReferencePrice": DatasetTier.FREE,
    "TaiwanStockDelisting": DatasetTier.FREE,
    "TaiwanStockSplitPrice": DatasetTier.FREE,
    "TaiwanStockParValueChange": DatasetTier.FREE,
    "TaiwanFutOptDailyInfo": DatasetTier.FREE,
    "TaiwanFuturesDaily": DatasetTier.FREE,
    "TaiwanOptionDaily": DatasetTier.FREE,
    "TaiwanFuturesInstitutionalInvestors": DatasetTier.FREE,
    "TaiwanOptionInstitutionalInvestors": DatasetTier.FREE,
    "TaiwanFuturesDealerTradingVolumeDaily": DatasetTier.FREE,
    "TaiwanOptionDealerTradingVolumeDaily": DatasetTier.FREE,
    "TaiwanFutOptTickInfo": DatasetTier.FREE,
    "TaiwanStockNews": DatasetTier.FREE,
    "TaiwanExchangeRate": DatasetTier.FREE,
    "InterestRate": DatasetTier.FREE,
    "GovernmentBondsYield": DatasetTier.FREE,
    "GoldPrice": DatasetTier.FREE,
    "CrudeOilPrices": DatasetTier.FREE,
    "TaiwanStockIndustryChain": DatasetTier.BACKER,
    "TaiwanBusinessIndicator": DatasetTier.BACKER,
    "TaiwanStockMarketValue": DatasetTier.BACKER,
    "TaiwanStockMarketValueWeight": DatasetTier.BACKER,
    "TaiwanStockHoldingSharesPer": DatasetTier.BACKER,
    "TaiwanStockDispositionSecuritiesPeriod": DatasetTier.BACKER,
    "TaiwanStockSuspended": DatasetTier.BACKER,
    "TaiwanStockDayTradingSuspension": DatasetTier.BACKER,
    "TaiwanTotalExchangeMarginMaintenance": DatasetTier.BACKER,
    "TaiwanStockConvertibleBondInfo": DatasetTier.BACKER,
    "TaiwanStockConvertibleBondDaily": DatasetTier.BACKER,
    "TaiwanStockConvertibleBondInstitutionalInvestors": DatasetTier.BACKER,
    "TaiwanStockConvertibleBondDailyOverview": DatasetTier.BACKER,
    "TaiwanStockTradingDailyReport": DatasetTier.SPONSOR,
    "TaiwanStockTradingDailyReportSecIdAgg": DatasetTier.SPONSOR,
    "TaiwanstockGovernmentBankBuySell": DatasetTier.SPONSOR,
    "taiwan_stock_tick_snapshot": DatasetTier.SPONSOR,
    "TaiwanStockPriceTick": DatasetTier.BACKER,
    "TaiwanStockKBar": DatasetTier.SPONSOR,
}


REMOVED_OR_DOWNGRADED_SIGNALS: dict[str, dict[str, str]] = {
    "broker_branch_fendian": {
        "reason": "Sponsor-only branch data is unavailable on the free tier and too noisy for default scoring.",
        "default_path": "removed_from_default_scoring",
        "implementation_mode": "optional adapter",
        "fallback_behavior": "not_assessed",
    },
    "convertible_bond_overlay": {
        "reason": "Convertible-bond datasets are Backer/Sponsor-only and must not be spoofed in the free-tier path.",
        "default_path": "manual_overlay_only",
        "implementation_mode": "optional adapter",
        "fallback_behavior": "manual_review_required",
    },
    "business_indicator_timing": {
        "reason": "The business-indicator signal is downgraded to backdrop only and removed from default timing logic.",
        "default_path": "context_only",
        "implementation_mode": "automate",
        "fallback_behavior": "not_assessed",
    },
    "tick_snapshot_timing": {
        "reason": "Real-time and tick datasets are Sponsor-only; the free-tier path uses daily data instead.",
        "default_path": "daily_data_proxy",
        "implementation_mode": "automate",
        "fallback_behavior": "not_assessed",
    },
    "correlation_hard_reject_085": {
        "reason": "The fixed 0.85 reject threshold is removed in V2 and replaced by documentation-plus-justification above 0.70.",
        "default_path": "dashboard_and_justify",
        "implementation_mode": "automate",
        "fallback_behavior": "warn-and-continue",
    },
}


POINT_IN_TIME_POLICY = (
    "Use announcement/as-of dates only. In historical analysis, reject any record with a missing "
    "as-of date or an as-of date later than the decision date."
)

TAIWAN_TRANSACTION_COSTS = {
    "standard_sell_tax": 0.003,
    "day_trading_sell_tax_until_2027_12_31": 0.0015,
}


@dataclass
class ScoreSummary:
    earned: float
    available_weight: float
    normalized_score: Optional[float]


def dataset_tier(dataset: str) -> str:
    return DATASET_TIER_MAP.get(dataset, DatasetTier.UNKNOWN)


def is_free_tier_dataset(dataset: str) -> bool:
    return dataset_tier(dataset) == DatasetTier.FREE


def calculate_score(checks: list[CheckResult]) -> ScoreSummary:
    available_weight = sum(check.effective_weight for check in checks)
    earned = sum(check.effective_earned for check in checks)
    normalized = round((earned / available_weight) * 100, 2) if available_weight > 0 else None
    return ScoreSummary(earned=earned, available_weight=available_weight, normalized_score=normalized)


def aggregate_status(
    checks: list[CheckResult],
    manual_requirements: list[ManualRequirement] | None = None,
) -> AssessmentStatus:
    manual_requirements = manual_requirements or []
    if any(check.status == AssessmentStatus.FAILED for check in checks):
        return AssessmentStatus.FAILED
    if manual_requirements or any(
        check.status == AssessmentStatus.MANUAL_REVIEW_REQUIRED and check.weight > 0
        for check in checks
    ):
        return AssessmentStatus.MANUAL_REVIEW_REQUIRED
    if any(
        check.status == AssessmentStatus.NOT_ASSESSED and check.weight > 0
        for check in checks
    ):
        return AssessmentStatus.NOT_ASSESSED
    return AssessmentStatus.PASSED


def ensure_point_in_time(as_of_date: Optional[str], decision_date: Optional[str]) -> None:
    if decision_date is None:
        return
    if not as_of_date:
        raise ValueError("Point-in-time policy violation: missing as-of date")

    as_of = datetime.strptime(str(as_of_date)[:10], "%Y-%m-%d")
    decision = datetime.strptime(str(decision_date)[:10], "%Y-%m-%d")
    if as_of > decision:
        raise ValueError(
            f"Point-in-time policy violation: as-of date {as_of_date} is later than decision date {decision_date}"
        )


def removed_signal_entries() -> list[dict[str, str]]:
    entries = []
    for signal_key, payload in REMOVED_OR_DOWNGRADED_SIGNALS.items():
        row = {"signal_key": signal_key}
        row.update(payload)
        entries.append(row)
    return entries
