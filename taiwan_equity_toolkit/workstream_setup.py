"""
Workstream C — Setup / Entry / Portfolio Fit.
"""

from __future__ import annotations

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
from taiwan_equity_toolkit.sizing import build_sizing_band


def _per_history(per_df: pd.DataFrame) -> Optional[pd.Series]:
    if per_df.empty or "PER" not in per_df.columns:
        return None
    df = per_df.sort_values("date").copy()
    df["PER"] = pd.to_numeric(df["PER"], errors="coerce")
    return df.set_index("date")["PER"].dropna()


def _ttm_fcf_ntd(cash: list[parsers.CashFlow]) -> Optional[float]:
    cf_ttm = parsers.ttm(cash, 4)
    if not cf_ttm:
        return None
    values = [record.free_cash_flow for record in cf_ttm]
    if any(value is None for value in values):
        return None
    return float(sum(values))


def _valuation_check(
    price_df: pd.DataFrame,
    per_df: pd.DataFrame,
    shareholding_df: pd.DataFrame,
    cash: list[parsers.CashFlow],
    strategy_mode: StrategyMode,
) -> CheckResult:
    per_series = _per_history(per_df)
    market_cap = metrics.market_cap_proxy_ntd(price_df, shareholding_df)
    ttm_fcf = _ttm_fcf_ntd(cash)
    reverse_dcf = None
    if market_cap.value is not None and ttm_fcf is not None:
        reverse_dcf = metrics.reverse_dcf_implied_growth(market_cap.value, ttm_fcf)

    if per_series is None or len(per_series) < 252:
        detail = "Insufficient PER history"
        if reverse_dcf and reverse_dcf.value is not None:
            detail += f"; {reverse_dcf.cite()}"
        return CheckResult(
            name="Valuation / expectation gap",
            status=AssessmentStatus.NOT_ASSESSED,
            detail=detail,
            weight=25,
            earned=0,
            source="TaiwanStockPER + TaiwanStockPrice + TaiwanStockShareholding + TaiwanStockCashFlowsStatement",
            signal_key="valuation_setup",
            fallback_behavior="not_assessed",
        )

    latest_per = float(per_series.iloc[-1])
    pct_rank = float((per_series <= latest_per).mean())
    reverse_detail = reverse_dcf.cite() if reverse_dcf else "Reverse-DCF unavailable"

    if pct_rank >= 0.80:
        status = AssessmentStatus.MANUAL_REVIEW_REQUIRED if strategy_mode == StrategyMode.TACTICAL_LONG_SHORT else AssessmentStatus.PASSED
        earned = 4 if status == AssessmentStatus.MANUAL_REVIEW_REQUIRED else 10
        detail = f"PER {latest_per:.1f}x at {pct_rank*100:.0f}th percentile; {reverse_detail}"
    elif pct_rank <= 0.20:
        status = AssessmentStatus.PASSED
        earned = 25
        detail = f"PER {latest_per:.1f}x at {pct_rank*100:.0f}th percentile; {reverse_detail}"
    else:
        status = AssessmentStatus.PASSED
        earned = 16
        detail = f"PER {latest_per:.1f}x at {pct_rank*100:.0f}th percentile; {reverse_detail}"

    return CheckResult(
        name="Valuation / expectation gap",
        status=status,
        detail=detail,
        weight=25,
        earned=earned,
        source="TaiwanStockPER + TaiwanStockPrice + TaiwanStockShareholding + TaiwanStockCashFlowsStatement",
        signal_key="valuation_setup",
        fallback_behavior="manual_review_required" if status == AssessmentStatus.MANUAL_REVIEW_REQUIRED else "warn-and-continue",
    )


def _volatility_check(price_adj_df: pd.DataFrame) -> CheckResult:
    vol_30 = metrics.realized_vol(price_adj_df, lookback=30)
    vol_90 = metrics.realized_vol(price_adj_df, lookback=90)
    if vol_30.value is None:
        return CheckResult(
            name="Volatility",
            status=AssessmentStatus.NOT_ASSESSED,
            detail=vol_30.note or "Realized vol unavailable",
            weight=20,
            earned=0,
            source=vol_30.source,
            as_of=vol_30.as_of,
            signal_key="volatility",
            fallback_behavior="not_assessed",
        )

    if vol_30.value > 80:
        return CheckResult(
            name="Volatility",
            status=AssessmentStatus.FAILED,
            detail=f"30d realized vol {vol_30.value:.1f}% is unmanageably high; 90d {vol_90.value:.1f}%" if vol_90.value is not None else f"30d realized vol {vol_30.value:.1f}%",
            weight=20,
            earned=0,
            source=vol_30.source,
            as_of=vol_30.as_of,
            signal_key="volatility",
        )
    if vol_30.value > 60:
        return CheckResult(
            name="Volatility",
            status=AssessmentStatus.MANUAL_REVIEW_REQUIRED,
            detail=f"30d realized vol {vol_30.value:.1f}% is elevated; 90d {vol_90.value:.1f}%" if vol_90.value is not None else f"30d realized vol {vol_30.value:.1f}%",
            weight=20,
            earned=6,
            source=vol_30.source,
            as_of=vol_30.as_of,
            signal_key="volatility",
            fallback_behavior="manual_review_required",
        )

    earned = 20 if vol_30.value < 40 else 12
    return CheckResult(
        name="Volatility",
        status=AssessmentStatus.PASSED,
        detail=f"30d realized vol {vol_30.value:.1f}% | 90d {vol_90.value:.1f}%" if vol_90.value is not None else f"30d realized vol {vol_30.value:.1f}%",
        weight=20,
        earned=earned,
        source=vol_30.source,
        as_of=vol_30.as_of,
        signal_key="volatility",
    )


def _liquidity_check(raw_price_df: pd.DataFrame) -> CheckResult:
    adv = metrics.adv_ntd(raw_price_df, lookback=20)
    if adv.value is None:
        return CheckResult(
            name="Liquidity / execution",
            status=AssessmentStatus.NOT_ASSESSED,
            detail=adv.note or "ADV unavailable",
            weight=20,
            earned=0,
            source=adv.source,
            as_of=adv.as_of,
            signal_key="liquidity_execution",
            fallback_behavior="not_assessed",
        )
    if adv.value < 20_000_000:
        return CheckResult(
            name="Liquidity / execution",
            status=AssessmentStatus.FAILED,
            detail=f"ADV NT${adv.value:,.0f} is too low for the default screen",
            weight=20,
            earned=0,
            source=adv.source,
            as_of=adv.as_of,
            signal_key="liquidity_execution",
        )
    if adv.value < 50_000_000:
        return CheckResult(
            name="Liquidity / execution",
            status=AssessmentStatus.MANUAL_REVIEW_REQUIRED,
            detail=f"ADV NT${adv.value:,.0f} is thin; require staggered execution",
            weight=20,
            earned=5,
            source=adv.source,
            as_of=adv.as_of,
            signal_key="liquidity_execution",
            fallback_behavior="manual_review_required",
        )
    earned = 20 if adv.value >= 200_000_000 else 12
    return CheckResult(
        name="Liquidity / execution",
        status=AssessmentStatus.PASSED,
        detail=f"ADV NT${adv.value:,.0f}",
        weight=20,
        earned=earned,
        source=adv.source,
        as_of=adv.as_of,
        signal_key="liquidity_execution",
    )


def _book_overlap_check(price_adj_df: pd.DataFrame, book_prices: dict[str, pd.DataFrame]) -> tuple[CheckResult, Optional[float], Optional[str]]:
    if not book_prices:
        return (
            CheckResult(
                name="Portfolio overlap",
                status=AssessmentStatus.NOT_ASSESSED,
                detail="No existing book provided",
                weight=15,
                earned=0,
                source="TaiwanStockPriceAdj",
                signal_key="portfolio_overlap",
                fallback_behavior="not_assessed",
            ),
            None,
            None,
        )

    max_corr = None
    max_sid = None
    for sid, df in book_prices.items():
        corr = metrics.correlation_to_series(price_adj_df, df, lookback=90)
        if corr.value is None:
            continue
        if max_corr is None or abs(corr.value) > abs(max_corr):
            max_corr = float(corr.value)
            max_sid = sid

    if max_corr is None:
        return (
            CheckResult(
                name="Portfolio overlap",
                status=AssessmentStatus.NOT_ASSESSED,
                detail="Could not compute correlations to current book",
                weight=15,
                earned=0,
                source="TaiwanStockPriceAdj",
                signal_key="portfolio_overlap",
                fallback_behavior="not_assessed",
            ),
            None,
            None,
        )

    if abs(max_corr) > 0.70:
        return (
            CheckResult(
                name="Portfolio overlap",
                status=AssessmentStatus.MANUAL_REVIEW_REQUIRED,
                detail=f"Max 90d correlation {max_corr:+.2f} vs {max_sid}; justify overlap above 0.70",
                weight=15,
                earned=4,
                source="TaiwanStockPriceAdj",
                signal_key="portfolio_overlap",
                fallback_behavior="manual_review_required",
            ),
            max_corr,
            max_sid,
        )

    return (
        CheckResult(
            name="Portfolio overlap",
            status=AssessmentStatus.PASSED,
            detail=f"Max 90d correlation {max_corr:+.2f} vs {max_sid}",
            weight=15,
            earned=15,
            source="TaiwanStockPriceAdj",
            signal_key="portfolio_overlap",
        ),
        max_corr,
        max_sid,
    )


def _crowding_check(margin_df: pd.DataFrame) -> CheckResult:
    if margin_df.empty or "MarginPurchaseTodayBalance" not in margin_df.columns:
        return CheckResult(
            name="Crowding / setup",
            status=AssessmentStatus.NOT_ASSESSED,
            detail="Margin-balance crowding context unavailable",
            weight=20,
            earned=0,
            source="TaiwanStockMarginPurchaseShortSale",
            signal_key="crowding_setup",
            fallback_behavior="not_assessed",
        )

    sorted_df = margin_df.sort_values("date")
    if len(sorted_df) < 20:
        return CheckResult(
            name="Crowding / setup",
            status=AssessmentStatus.NOT_ASSESSED,
            detail="Insufficient margin history",
            weight=20,
            earned=0,
            source="TaiwanStockMarginPurchaseShortSale",
            signal_key="crowding_setup",
            fallback_behavior="not_assessed",
        )

    first = pd.to_numeric(sorted_df.iloc[0].get("MarginPurchaseTodayBalance"), errors="coerce")
    last = pd.to_numeric(sorted_df.iloc[-1].get("MarginPurchaseTodayBalance"), errors="coerce")
    if pd.isna(first) or pd.isna(last) or first == 0:
        return CheckResult(
            name="Crowding / setup",
            status=AssessmentStatus.NOT_ASSESSED,
            detail="Could not compute margin-balance change",
            weight=20,
            earned=0,
            source="TaiwanStockMarginPurchaseShortSale",
            signal_key="crowding_setup",
            fallback_behavior="not_assessed",
        )

    change_pct = (float(last) - float(first)) / float(first) * 100
    if change_pct > 30:
        return CheckResult(
            name="Crowding / setup",
            status=AssessmentStatus.MANUAL_REVIEW_REQUIRED,
            detail=f"Margin balance +{change_pct:.1f}% over the review window",
            weight=20,
            earned=5,
            source="TaiwanStockMarginPurchaseShortSale",
            signal_key="crowding_setup",
            fallback_behavior="manual_review_required",
        )
    if change_pct < -10:
        earned = 20
    else:
        earned = 12
    return CheckResult(
        name="Crowding / setup",
        status=AssessmentStatus.PASSED,
        detail=f"Margin balance {change_pct:+.1f}% over the review window",
        weight=20,
        earned=earned,
        source="TaiwanStockMarginPurchaseShortSale",
        signal_key="crowding_setup",
    )


def run(
    client: FinMindClient,
    stock_id: str,
    strategy_mode: StrategyMode = StrategyMode.TACTICAL_LONG_SHORT,
    existing_book: Optional[list[str]] = None,
) -> tuple[WorkstreamResult, dict[str, object]]:
    existing_book = existing_book or []
    today = datetime.today()
    price_start = (today - timedelta(days=5 * 365)).strftime("%Y-%m-%d")
    raw_price_start = (today - timedelta(days=120)).strftime("%Y-%m-%d")
    per_start = (today - timedelta(days=5 * 365)).strftime("%Y-%m-%d")
    fs_start = (today - timedelta(days=730)).strftime("%Y-%m-%d")
    flow_start = (today - timedelta(days=120)).strftime("%Y-%m-%d")

    price_adj_df = client.price_adj(stock_id, price_start)
    raw_price_df = client.price(stock_id, raw_price_start)
    per_df = client.per(stock_id, per_start)
    shareholding_df = client.foreign_ownership(stock_id, flow_start)
    cash = parsers.parse_cash_flows(client.cash_flow(stock_id, fs_start))
    margin_df = client.margin_short(stock_id, flow_start)

    checks: list[CheckResult] = [
        _valuation_check(raw_price_df, per_df, shareholding_df, cash, strategy_mode),
        _volatility_check(price_adj_df),
        _liquidity_check(raw_price_df),
        _crowding_check(margin_df),
    ]

    manual_requirements: list[ManualRequirement] = []
    book_prices: dict[str, pd.DataFrame] = {}
    for sid in [item for item in existing_book if item != stock_id]:
        book_prices[sid] = client.price_adj(sid, price_start)

    overlap_check, max_corr, max_corr_id = _book_overlap_check(price_adj_df, book_prices)
    checks.append(overlap_check)
    if overlap_check.status == AssessmentStatus.MANUAL_REVIEW_REQUIRED:
        manual_requirements.append(
            ManualRequirement(
                title="Justify portfolio overlap",
                detail=f"Document why overlap with {max_corr_id} at {max_corr:+.2f} remains acceptable.",
                category="portfolio_fit",
            )
        )

    checks.append(
        CheckResult(
            name="Tick / snapshot overlay",
            status=AssessmentStatus.NOT_ASSESSED,
            detail="Sponsor-only tick and snapshot datasets are replaced by daily data in the free-tier path",
            weight=0,
            earned=0,
            source="taiwan_stock_tick_snapshot + TaiwanStockPriceTick",
            signal_key="tick_snapshot_timing",
            fallback_behavior="not_assessed",
        )
    )

    score_summary = calculate_score(checks)
    status = aggregate_status(checks, manual_requirements)
    liquidity_failed = any(check.name == "Liquidity / execution" and check.status == AssessmentStatus.FAILED for check in checks)
    if liquidity_failed:
        status = AssessmentStatus.FAILED

    red_count = len([check for check in checks if check.status == AssessmentStatus.FAILED])
    yellow_count = len([
        check for check in checks
        if check.status in {AssessmentStatus.MANUAL_REVIEW_REQUIRED, AssessmentStatus.NOT_ASSESSED}
    ])

    if liquidity_failed:
        entry_verdict = "Reject for Book Fit"
    elif red_count >= 2:
        entry_verdict = "Wait for Setup"
    elif any(check.name == "Portfolio overlap" and check.status == AssessmentStatus.MANUAL_REVIEW_REQUIRED for check in checks):
        entry_verdict = "Wait for Setup"
    elif yellow_count >= 2:
        entry_verdict = "Stagger / Scale In"
    else:
        entry_verdict = "Enter Now"

    adv_metric = metrics.adv_ntd(raw_price_df, lookback=20)
    vol_90_metric = metrics.realized_vol(price_adj_df, lookback=90)
    sizing_band = build_sizing_band(
        adv_ntd=adv_metric.value,
        vol_90=vol_90_metric.value,
        max_corr=max_corr,
        strategy_mode=strategy_mode,
    )

    result = WorkstreamResult(
        name="Setup/Entry",
        status=status,
        checks=checks,
        score=score_summary.normalized_score,
        available_weight=score_summary.available_weight,
        manual_requirements=manual_requirements,
        notes=[
            f"strategy_mode={strategy_mode.value}",
            "Scenario EV, catalyst path, and exit archetype are completed in synthesis/manual workflow.",
        ],
        removed_or_downgraded_signals=[
            entry for entry in removed_signal_entries()
            if entry["signal_key"] in {"tick_snapshot_timing", "correlation_hard_reject_085"}
        ],
        metadata={
            "entry_verdict": entry_verdict,
            "max_corr": max_corr,
            "max_corr_id": max_corr_id,
            "sizing_band": sizing_band.to_dict(),
        },
    )
    extras = {
        "entry_verdict": entry_verdict,
        "sizing_band": sizing_band,
        "max_corr": max_corr,
        "max_corr_id": max_corr_id,
    }
    return result, extras
