"""
Workstream B — Company Quality.

Free-tier default path:
- compact red-flag screen
- conditional full-forensic expansion when flags accumulate
- broker-branch and CB data removed from default scoring
- management forensic and channel checks preserved as explicit protocols
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

from taiwan_equity_toolkit import metrics, parsers
from taiwan_equity_toolkit.client import FinMindClient
from taiwan_equity_toolkit.data_policy import aggregate_status, calculate_score, removed_signal_entries
from taiwan_equity_toolkit.models import (
    AssessmentStatus,
    CheckResult,
    ManualRequirement,
    StrategyMode,
    WorkstreamResult,
)


RED_FLAG_ESCALATION_THRESHOLD = 2
CRITICAL_RED_FLAGS = {"Balance-sheet stress", "Governance / news red flags"}


@dataclass
class CompanyDataBundle:
    price_df: pd.DataFrame
    fs_df: pd.DataFrame
    bs_df: pd.DataFrame
    cf_df: pd.DataFrame
    rev_df: pd.DataFrame
    flow_df: pd.DataFrame
    own_df: pd.DataFrame
    margin_df: pd.DataFrame
    sbl_df: pd.DataFrame
    news_df: pd.DataFrame
    capital_reduction_df: pd.DataFrame


def _fetch_bundle(client: FinMindClient, stock_id: str) -> CompanyDataBundle:
    today = datetime.today()
    fs_start = (today - timedelta(days=730)).strftime("%Y-%m-%d")
    rev_start = (today - timedelta(days=730)).strftime("%Y-%m-%d")
    price_start = (today - timedelta(days=90)).strftime("%Y-%m-%d")
    flow_start = (today - timedelta(days=120)).strftime("%Y-%m-%d")
    news_start = (today - timedelta(days=120)).strftime("%Y-%m-%d")

    return CompanyDataBundle(
        price_df=client.price(stock_id, price_start),
        fs_df=client.financial_statements(stock_id, fs_start),
        bs_df=client.balance_sheet(stock_id, fs_start),
        cf_df=client.cash_flow(stock_id, fs_start),
        rev_df=client.monthly_revenue(stock_id, rev_start),
        flow_df=client.institutional_flow(stock_id, flow_start),
        own_df=client.foreign_ownership(stock_id, flow_start),
        margin_df=client.margin_short(stock_id, flow_start),
        sbl_df=client.get("TaiwanDailyShortSaleBalances", stock_id, flow_start),
        news_df=client.news(stock_id, news_start),
        capital_reduction_df=client.get("TaiwanStockCapitalReductionReferencePrice", stock_id, fs_start),
    )


def _manual_overlay_protocols() -> list[ManualRequirement]:
    return [
        ManualRequirement(
            title="Management forensic",
            detail="Review management incentives, capital allocation, candor, and Taiwan governance materials outside FinMind.",
            category="management_forensic",
        ),
        ManualRequirement(
            title="Share-pledging review",
            detail="Review director/supervisor share-pledging disclosures from MOPS or another public source.",
            category="taiwan_governance",
        ),
        ManualRequirement(
            title="Channel-check protocol",
            detail="Run customer / supplier / former-employee checks under the documented MNPI-safe workflow.",
            category="scuttlebutt",
        ),
    ]


def _financial_freshness_check(income: list[parsers.IncomeStatement]) -> CheckResult:
    latest_income = parsers.latest(income)
    if latest_income is None:
        return CheckResult(
            name="Financial freshness",
            status=AssessmentStatus.FAILED,
            detail="No income-statement data",
            weight=10,
            earned=0,
            source="TaiwanStockFinancialStatements",
            signal_key="financial_freshness",
        )

    latest_dt = datetime.strptime(latest_income.date[:10], "%Y-%m-%d")
    days_stale = (datetime.today() - latest_dt).days
    if days_stale > 135:
        return CheckResult(
            name="Financial freshness",
            status=AssessmentStatus.FAILED,
            detail=f"Latest filing is {days_stale} days old",
            weight=10,
            earned=0,
            source="TaiwanStockFinancialStatements",
            as_of=latest_income.date,
            signal_key="financial_freshness",
        )
    return CheckResult(
        name="Financial freshness",
        status=AssessmentStatus.PASSED,
        detail=f"Latest filing {latest_income.date} ({days_stale} days stale)",
        weight=10,
        earned=10,
        source="TaiwanStockFinancialStatements",
        as_of=latest_income.date,
        signal_key="financial_freshness",
    )


def _tradability_check(price_df: pd.DataFrame) -> CheckResult:
    adv = metrics.adv_ntd(price_df, lookback=20)
    if adv.value is None:
        return CheckResult(
            name="Tradability",
            status=AssessmentStatus.NOT_ASSESSED,
            detail="ADV unavailable",
            weight=10,
            earned=0,
            source=adv.source,
            as_of=adv.as_of,
            signal_key="tradability",
            fallback_behavior="not_assessed",
        )
    if adv.value < 50_000_000:
        return CheckResult(
            name="Tradability",
            status=AssessmentStatus.FAILED,
            detail=f"ADV NT${adv.value:,.0f} below NT$50M floor",
            weight=10,
            earned=0,
            source=adv.source,
            as_of=adv.as_of,
            signal_key="tradability",
        )
    return CheckResult(
        name="Tradability",
        status=AssessmentStatus.PASSED,
        detail=f"ADV NT${adv.value:,.0f}",
        weight=10,
        earned=10,
        source=adv.source,
        as_of=adv.as_of,
        signal_key="tradability",
    )


def _revenue_trajectory_check(rev_df: pd.DataFrame) -> CheckResult:
    rev_yoy = metrics.revenue_growth_yoy(rev_df)
    rev_ttm = metrics.revenue_ttm_trend(rev_df)
    if rev_yoy.value is None:
        return CheckResult(
            name="Monthly revenue trajectory",
            status=AssessmentStatus.NOT_ASSESSED,
            detail=rev_yoy.note or "Monthly revenue YoY unavailable",
            weight=10,
            earned=0,
            source=rev_yoy.source,
            as_of=rev_yoy.as_of,
            signal_key="revenue_trajectory",
            fallback_behavior="not_assessed",
        )
    if rev_yoy.value < -30:
        return CheckResult(
            name="Monthly revenue trajectory",
            status=AssessmentStatus.FAILED,
            detail=f"Revenue YoY {rev_yoy.value:.1f}% below collapse threshold",
            weight=10,
            earned=0,
            source=rev_yoy.source,
            as_of=rev_yoy.as_of,
            signal_key="revenue_trajectory",
        )

    earned = 10 if (rev_yoy.value > 0 and (rev_ttm.value or 0) >= 0) else 6
    return CheckResult(
        name="Monthly revenue trajectory",
        status=AssessmentStatus.PASSED,
        detail=f"Revenue YoY {rev_yoy.value:.1f}% | TTM {rev_ttm.value:.1f}%"
        if rev_ttm.value is not None
        else f"Revenue YoY {rev_yoy.value:.1f}%",
        weight=10,
        earned=earned,
        source=rev_yoy.source,
        as_of=rev_yoy.as_of,
        signal_key="revenue_trajectory",
    )


def _cfo_to_ni_check(income: list[parsers.IncomeStatement], cash: list[parsers.CashFlow]) -> CheckResult:
    cfo_ni = metrics.cfo_to_ni_ratio(income, cash, n_qtrs=4)
    if cfo_ni.value is None:
        return CheckResult(
            name="CFO/NI quality",
            status=AssessmentStatus.NOT_ASSESSED,
            detail=cfo_ni.note or "CFO/NI unavailable",
            weight=10,
            earned=0,
            source=cfo_ni.source,
            as_of=cfo_ni.as_of,
            signal_key="cfo_to_ni",
            fallback_behavior="not_assessed",
        )
    if cfo_ni.value < 0.5:
        return CheckResult(
            name="CFO/NI quality",
            status=AssessmentStatus.MANUAL_REVIEW_REQUIRED,
            detail=f"CFO/NI {cfo_ni.value:.2f}x below 0.50x red-flag threshold",
            weight=10,
            earned=0,
            source=cfo_ni.source,
            as_of=cfo_ni.as_of,
            signal_key="cfo_to_ni",
            fallback_behavior="manual_review_required",
        )
    if cfo_ni.value < 0.8:
        return CheckResult(
            name="CFO/NI quality",
            status=AssessmentStatus.PASSED,
            detail=f"CFO/NI {cfo_ni.value:.2f}x is below preferred 0.80x but not an auto-reject",
            weight=10,
            earned=5,
            source=cfo_ni.source,
            as_of=cfo_ni.as_of,
            signal_key="cfo_to_ni",
        )
    return CheckResult(
        name="CFO/NI quality",
        status=AssessmentStatus.PASSED,
        detail=f"CFO/NI {cfo_ni.value:.2f}x",
        weight=10,
        earned=10,
        source=cfo_ni.source,
        as_of=cfo_ni.as_of,
        signal_key="cfo_to_ni",
    )


def _balance_sheet_check(
    income: list[parsers.IncomeStatement],
    balance: list[parsers.BalanceSheet],
    cash: list[parsers.CashFlow],
) -> CheckResult:
    nd = metrics.net_debt_to_ebitda(balance, income)
    cash_st = metrics.cash_to_short_term_debt(balance)
    interest = metrics.interest_coverage(income, 4)
    fcf = metrics.free_cash_flow_margin(cash, income, 4)

    if nd.value is None and cash_st.value is None and interest.value is None:
        return CheckResult(
            name="Balance-sheet stress",
            status=AssessmentStatus.NOT_ASSESSED,
            detail="Core balance-sheet metrics unavailable",
            weight=15,
            earned=0,
            source="TaiwanStockBalanceSheet + TaiwanStockFinancialStatements + TaiwanStockCashFlowsStatement",
            signal_key="balance_sheet_stress",
            fallback_behavior="not_assessed",
        )

    details = [metric.cite() for metric in [nd, cash_st, interest, fcf] if metric.value is not None]
    if nd.value is not None and nd.value > 5:
        return CheckResult(
            name="Balance-sheet stress",
            status=AssessmentStatus.FAILED,
            detail=" ; ".join(details) or "Extreme leverage",
            weight=15,
            earned=0,
            source=nd.source,
            as_of=nd.as_of,
            signal_key="balance_sheet_stress",
        )
    if (
        cash_st.value is not None and cash_st.value < 1
        and interest.value is not None and interest.value < 2
    ):
        return CheckResult(
            name="Balance-sheet stress",
            status=AssessmentStatus.FAILED,
            detail="Weak cash coverage and weak interest coverage: " + " ; ".join(details),
            weight=15,
            earned=0,
            source="TaiwanStockBalanceSheet + TaiwanStockFinancialStatements + TaiwanStockCashFlowsStatement",
            signal_key="balance_sheet_stress",
        )

    if (
        (nd.value is not None and nd.value > 3)
        or (cash_st.value is not None and cash_st.value < 1.5)
        or (interest.value is not None and interest.value < 4)
    ):
        return CheckResult(
            name="Balance-sheet stress",
            status=AssessmentStatus.MANUAL_REVIEW_REQUIRED,
            detail="Needs deeper balance-sheet review: " + " ; ".join(details),
            weight=15,
            earned=5,
            source="TaiwanStockBalanceSheet + TaiwanStockFinancialStatements + TaiwanStockCashFlowsStatement",
            signal_key="balance_sheet_stress",
            fallback_behavior="manual_review_required",
        )

    return CheckResult(
        name="Balance-sheet stress",
        status=AssessmentStatus.PASSED,
        detail=" ; ".join(details) if details else "Balance-sheet metrics healthy",
        weight=15,
        earned=15,
        source="TaiwanStockBalanceSheet + TaiwanStockFinancialStatements + TaiwanStockCashFlowsStatement",
        signal_key="balance_sheet_stress",
    )


def _governance_check(news_df: pd.DataFrame) -> CheckResult:
    red_flag_keywords = [
        "auditor",
        "會計師更換",
        "辭任",
        "董事請辭",
        "掏空",
        "財報重編",
        "restatement",
        "going concern",
        "關係人交易",
        "解任",
        "停牌",
    ]
    if news_df.empty or "title" not in news_df.columns:
        return CheckResult(
            name="Governance / news red flags",
            status=AssessmentStatus.NOT_ASSESSED,
            detail="News scan unavailable",
            weight=15,
            earned=0,
            source="TaiwanStockNews",
            signal_key="governance_news",
            fallback_behavior="not_assessed",
        )

    hits = []
    for keyword in red_flag_keywords:
        matching = news_df[news_df["title"].astype(str).str.contains(keyword, na=False)]
        if not matching.empty:
            hits.append(f"{keyword} ({len(matching)})")

    if hits:
        return CheckResult(
            name="Governance / news red flags",
            status=AssessmentStatus.FAILED,
            detail="Red-flag keywords: " + ", ".join(hits),
            weight=15,
            earned=0,
            source="TaiwanStockNews",
            as_of=str(news_df.sort_values("date").iloc[-1].get("date")),
            signal_key="governance_news",
        )

    return CheckResult(
        name="Governance / news red flags",
        status=AssessmentStatus.PASSED,
        detail="No red-flag keywords in recent news",
        weight=15,
        earned=15,
        source="TaiwanStockNews",
        as_of=str(news_df.sort_values("date").iloc[-1].get("date")),
        signal_key="governance_news",
    )


def _capital_action_check(capital_reduction_df: pd.DataFrame) -> CheckResult:
    if capital_reduction_df.empty:
        return CheckResult(
            name="Capital-action history",
            status=AssessmentStatus.PASSED,
            detail="No capital-reduction history in the review window",
            weight=10,
            earned=10,
            source="TaiwanStockCapitalReductionReferencePrice",
            signal_key="capital_actions",
        )

    if len(capital_reduction_df) >= 2:
        return CheckResult(
            name="Capital-action history",
            status=AssessmentStatus.MANUAL_REVIEW_REQUIRED,
            detail=f"{len(capital_reduction_df)} capital-reduction event(s) in history window",
            weight=10,
            earned=2,
            source="TaiwanStockCapitalReductionReferencePrice",
            as_of=str(capital_reduction_df.sort_values("date").iloc[-1].get("date")),
            signal_key="capital_actions",
            fallback_behavior="manual_review_required",
        )

    return CheckResult(
        name="Capital-action history",
        status=AssessmentStatus.PASSED,
        detail="Single historical capital-reduction event noted",
        weight=10,
        earned=6,
        source="TaiwanStockCapitalReductionReferencePrice",
        as_of=str(capital_reduction_df.sort_values("date").iloc[-1].get("date")),
        signal_key="capital_actions",
    )


def _ownership_check(
    flow_df: pd.DataFrame,
    own_df: pd.DataFrame,
    margin_df: pd.DataFrame,
    sbl_df: pd.DataFrame,
) -> CheckResult:
    flows = metrics.institutional_net_flow(flow_df, lookback_days=60)
    positive = 0
    negative = 0
    for metric in flows.values():
        if metric.value is None:
            continue
        if metric.value > 0:
            positive += 1
        elif metric.value < 0:
            negative += 1

    own_trend = None
    if not own_df.empty and "ForeignInvestmentSharesRatio" in own_df.columns:
        sorted_df = own_df.sort_values("date")
        if len(sorted_df) >= 2:
            start = pd.to_numeric(sorted_df.iloc[0].get("ForeignInvestmentSharesRatio"), errors="coerce")
            end = pd.to_numeric(sorted_df.iloc[-1].get("ForeignInvestmentSharesRatio"), errors="coerce")
            if pd.notna(start) and pd.notna(end):
                own_trend = float(end - start)

    sbl_pressure = None
    if not sbl_df.empty and "SBLShortSalesCurrentDayBalance" in sbl_df.columns:
        sorted_sbl = sbl_df.sort_values("date")
        first = pd.to_numeric(sorted_sbl.iloc[0].get("SBLShortSalesCurrentDayBalance"), errors="coerce")
        last = pd.to_numeric(sorted_sbl.iloc[-1].get("SBLShortSalesCurrentDayBalance"), errors="coerce")
        if pd.notna(first) and pd.notna(last):
            sbl_pressure = float(last - first)

    detail_parts = []
    if positive or negative:
        detail_parts.append(f"institutional breadth +{positive}/-{negative}")
    if own_trend is not None:
        detail_parts.append(f"foreign-holding trend {own_trend:+.2f}pp")
    if sbl_pressure is not None:
        detail_parts.append(f"SBL balance change {sbl_pressure:+,.0f}")

    if negative >= 2 and (sbl_pressure is not None and sbl_pressure > 0):
        return CheckResult(
            name="Ownership / sponsorship",
            status=AssessmentStatus.FAILED,
            detail="Negative sponsorship with rising SBL pressure; " + " ; ".join(detail_parts),
            weight=10,
            earned=0,
            source="TaiwanStockInstitutionalInvestorsBuySell + TaiwanStockShareholding + TaiwanDailyShortSaleBalances",
            signal_key="ownership_sponsorship",
        )

    if negative >= positive:
        return CheckResult(
            name="Ownership / sponsorship",
            status=AssessmentStatus.MANUAL_REVIEW_REQUIRED,
            detail="Mixed sponsorship; " + " ; ".join(detail_parts),
            weight=10,
            earned=4,
            source="TaiwanStockInstitutionalInvestorsBuySell + TaiwanStockShareholding + TaiwanDailyShortSaleBalances",
            signal_key="ownership_sponsorship",
            fallback_behavior="manual_review_required",
        )

    return CheckResult(
        name="Ownership / sponsorship",
        status=AssessmentStatus.PASSED,
        detail="Healthy sponsorship; " + " ; ".join(detail_parts) if detail_parts else "Healthy sponsorship",
        weight=10,
        earned=10,
        source="TaiwanStockInstitutionalInvestorsBuySell + TaiwanStockShareholding + TaiwanDailyShortSaleBalances",
        signal_key="ownership_sponsorship",
    )


def _consistency_check(rev_df: pd.DataFrame, income: list[parsers.IncomeStatement]) -> CheckResult:
    if rev_df.empty or not income or "revenue" not in rev_df.columns:
        return CheckResult(
            name="Monthly / quarterly consistency",
            status=AssessmentStatus.NOT_ASSESSED,
            detail="Insufficient data to reconcile monthly and quarterly revenue",
            weight=10,
            earned=0,
            source="TaiwanStockMonthRevenue + TaiwanStockFinancialStatements",
            signal_key="monthly_quarterly_consistency",
            fallback_behavior="not_assessed",
        )

    latest_income = sorted(income, key=lambda item: item.date)[-1]
    if latest_income.revenue in (None, 0):
        return CheckResult(
            name="Monthly / quarterly consistency",
            status=AssessmentStatus.NOT_ASSESSED,
            detail="Latest quarterly revenue unavailable",
            weight=10,
            earned=0,
            source="TaiwanStockMonthRevenue + TaiwanStockFinancialStatements",
            signal_key="monthly_quarterly_consistency",
            fallback_behavior="not_assessed",
        )

    rev_copy = rev_df.copy()
    rev_copy["date"] = pd.to_datetime(rev_copy["date"])
    q_end = pd.to_datetime(latest_income.date[:10])
    q_start = (q_end.replace(day=1) - pd.DateOffset(months=2)).normalize()
    quarter_sum = rev_copy[(rev_copy["date"] >= q_start) & (rev_copy["date"] <= q_end)]["revenue"].sum()
    delta = abs(float(quarter_sum) - float(latest_income.revenue)) / float(latest_income.revenue)

    if delta > 0.20:
        return CheckResult(
            name="Monthly / quarterly consistency",
            status=AssessmentStatus.FAILED,
            detail=f"Revenue mismatch {delta*100:.1f}% between monthly sum and quarterly filing",
            weight=10,
            earned=0,
            source="TaiwanStockMonthRevenue + TaiwanStockFinancialStatements",
            as_of=latest_income.date,
            signal_key="monthly_quarterly_consistency",
        )
    if delta > 0.10:
        return CheckResult(
            name="Monthly / quarterly consistency",
            status=AssessmentStatus.MANUAL_REVIEW_REQUIRED,
            detail=f"Revenue mismatch {delta*100:.1f}% between monthly sum and quarterly filing",
            weight=10,
            earned=3,
            source="TaiwanStockMonthRevenue + TaiwanStockFinancialStatements",
            as_of=latest_income.date,
            signal_key="monthly_quarterly_consistency",
            fallback_behavior="manual_review_required",
        )
    return CheckResult(
        name="Monthly / quarterly consistency",
        status=AssessmentStatus.PASSED,
        detail=f"Monthly sum reconciles within {delta*100:.1f}%",
        weight=10,
        earned=10,
        source="TaiwanStockMonthRevenue + TaiwanStockFinancialStatements",
        as_of=latest_income.date,
        signal_key="monthly_quarterly_consistency",
    )


def _full_forensic_checks(
    income: list[parsers.IncomeStatement],
    balance: list[parsers.BalanceSheet],
    cash: list[parsers.CashFlow],
    flow_df: pd.DataFrame,
    own_df: pd.DataFrame,
    margin_df: pd.DataFrame,
    consistency_check: CheckResult,
) -> list[CheckResult]:
    checks: list[CheckResult] = []

    gm = metrics.gross_margin_latest(income)
    om = metrics.operating_margin_latest(income)
    roe = metrics.roe_proxy(income, balance)
    operating_values = [metric.value for metric in [gm, om, roe] if metric.value is not None]
    if operating_values:
        earned = 15 if (gm.value or 0) > 25 and (om.value or 0) > 10 else 8
        checks.append(
            CheckResult(
                name="Full forensic — operating quality",
                status=AssessmentStatus.PASSED,
                detail=" ; ".join(metric.cite() for metric in [gm, om, roe] if metric.value is not None),
                weight=15,
                earned=earned,
                source="TaiwanStockFinancialStatements + TaiwanStockBalanceSheet",
                signal_key="full_forensic_operating",
            )
        )
    else:
        checks.append(
            CheckResult(
                name="Full forensic — operating quality",
                status=AssessmentStatus.NOT_ASSESSED,
                detail="Operating quality metrics unavailable",
                weight=15,
                earned=0,
                source="TaiwanStockFinancialStatements + TaiwanStockBalanceSheet",
                signal_key="full_forensic_operating",
                fallback_behavior="not_assessed",
            )
        )

    fcf = metrics.free_cash_flow_margin(cash, income, 4)
    if fcf.value is not None:
        checks.append(
            CheckResult(
                name="Full forensic — cash conversion",
                status=AssessmentStatus.PASSED if fcf.value >= 0 else AssessmentStatus.MANUAL_REVIEW_REQUIRED,
                detail=fcf.cite(),
                weight=10,
                earned=10 if fcf.value >= 5 else 4,
                source=fcf.source,
                as_of=fcf.as_of,
                signal_key="full_forensic_cash_conversion",
                fallback_behavior="manual_review_required" if fcf.value < 0 else "warn-and-continue",
            )
        )
    else:
        checks.append(
            CheckResult(
                name="Full forensic — cash conversion",
                status=AssessmentStatus.NOT_ASSESSED,
                detail=fcf.note or "FCF margin unavailable",
                weight=10,
                earned=0,
                source=fcf.source,
                as_of=fcf.as_of,
                signal_key="full_forensic_cash_conversion",
                fallback_behavior="not_assessed",
            )
        )

    foreign_trend = "unavailable"
    if not own_df.empty and "ForeignInvestmentSharesRatio" in own_df.columns:
        sorted_df = own_df.sort_values("date")
        if len(sorted_df) >= 2:
            first = pd.to_numeric(sorted_df.iloc[0].get("ForeignInvestmentSharesRatio"), errors="coerce")
            last = pd.to_numeric(sorted_df.iloc[-1].get("ForeignInvestmentSharesRatio"), errors="coerce")
            if pd.notna(first) and pd.notna(last):
                foreign_trend = f"{float(last - first):+.2f}pp"

    flows = metrics.institutional_net_flow(flow_df, lookback_days=60)
    flow_detail = "; ".join(metric.cite() for metric in flows.values() if metric.value is not None) or "no flow data"
    checks.append(
        CheckResult(
            name="Full forensic — ownership quality",
            status=AssessmentStatus.PASSED,
            detail=f"{flow_detail}; foreign-holding trend {foreign_trend}",
            weight=10,
            earned=10 if "no flow data" not in flow_detail else 4,
            source="TaiwanStockInstitutionalInvestorsBuySell + TaiwanStockShareholding + TaiwanStockMarginPurchaseShortSale",
            signal_key="full_forensic_ownership",
        )
    )

    checks.append(
        CheckResult(
            name="Full forensic — integrity composite",
            status=consistency_check.status,
            detail=consistency_check.detail,
            weight=5,
            earned=5 if consistency_check.status == AssessmentStatus.PASSED else 0,
            source=consistency_check.source,
            as_of=consistency_check.as_of,
            signal_key="full_forensic_integrity",
            fallback_behavior=consistency_check.fallback_behavior,
        )
    )
    return checks


def run(
    client: FinMindClient,
    stock_id: str,
    strategy_mode: StrategyMode = StrategyMode.TACTICAL_LONG_SHORT,
    include_manual_overlay_protocols: bool = False,
) -> WorkstreamResult:
    bundle = _fetch_bundle(client, stock_id)
    income = parsers.parse_income_statements(bundle.fs_df)
    balance = parsers.parse_balance_sheets(bundle.bs_df)
    cash = parsers.parse_cash_flows(bundle.cf_df)

    checks: list[CheckResult] = [
        _tradability_check(bundle.price_df),
        _financial_freshness_check(income),
        _revenue_trajectory_check(bundle.rev_df),
        _cfo_to_ni_check(income, cash),
    ]

    balance_check = _balance_sheet_check(income, balance, cash)
    governance_check = _governance_check(bundle.news_df)
    capital_action_check = _capital_action_check(bundle.capital_reduction_df)
    ownership_check = _ownership_check(bundle.flow_df, bundle.own_df, bundle.margin_df, bundle.sbl_df)
    consistency_check = _consistency_check(bundle.rev_df, income)

    checks.extend([
        balance_check,
        governance_check,
        capital_action_check,
        ownership_check,
        consistency_check,
    ])

    red_flag_count = len([
        check for check in checks
        if check.status in {AssessmentStatus.FAILED, AssessmentStatus.MANUAL_REVIEW_REQUIRED}
    ])
    critical_red_flag = any(
        check.name in CRITICAL_RED_FLAGS and check.status in {AssessmentStatus.FAILED, AssessmentStatus.MANUAL_REVIEW_REQUIRED}
        for check in checks
    )

    notes = [
        f"strategy_mode={strategy_mode.value}",
        f"red_flag_count={red_flag_count}",
        "Broker-branch and CB datasets are excluded from default scoring.",
    ]

    if red_flag_count >= RED_FLAG_ESCALATION_THRESHOLD or critical_red_flag:
        checks.extend(
            _full_forensic_checks(
                income=income,
                balance=balance,
                cash=cash,
                flow_df=bundle.flow_df,
                own_df=bundle.own_df,
                margin_df=bundle.margin_df,
                consistency_check=consistency_check,
            )
        )
        notes.append("Full forensic triggered by red-flag threshold.")
    else:
        notes.append("Full forensic not triggered; compact red-flag screen sufficient.")

    score_summary = calculate_score(checks)
    manual_requirements: list[ManualRequirement] = []
    if include_manual_overlay_protocols:
        manual_requirements.extend(_manual_overlay_protocols())

    status = aggregate_status(checks, manual_requirements)
    if red_flag_count >= 4:
        status = AssessmentStatus.FAILED
    elif status == AssessmentStatus.PASSED and score_summary.normalized_score is not None and score_summary.normalized_score < 55:
        status = AssessmentStatus.MANUAL_REVIEW_REQUIRED

    return WorkstreamResult(
        name="Company Quality",
        status=status,
        checks=checks,
        score=score_summary.normalized_score,
        available_weight=score_summary.available_weight,
        manual_requirements=manual_requirements,
        notes=notes,
        removed_or_downgraded_signals=[
            entry for entry in removed_signal_entries()
            if entry["signal_key"] in {"broker_branch_fendian", "convertible_bond_overlay"}
        ],
        metadata={
            "red_flag_count": red_flag_count,
            "full_forensic_triggered": red_flag_count >= RED_FLAG_ESCALATION_THRESHOLD or critical_red_flag,
        },
    )
