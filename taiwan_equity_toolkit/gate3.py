"""
Gate 3 — Forensic Quality.

Implements the 5-sublayer scorecard (3A–3E), 100-point scoring, and the
seven Hard-Fail Overrides.

One function: `run(client, stock_id)` → Gate3Result. The agent reads the
structured result and composes the memo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from taiwan_equity_toolkit.client import FinMindClient
from taiwan_equity_toolkit.config import DEFAULT_CONFIG, Gate3Thresholds, Gate3Weights
from taiwan_equity_toolkit import metrics, parsers


@dataclass
class SubLayerScore:
    layer: str                  # "3A", "3B", ...
    name: str                   # full name
    score: float                # earned points
    max_score: int              # weight cap
    components: list[dict] = field(default_factory=list)  # per-check details

    def as_line(self) -> str:
        return f"{self.layer} {self.name}: {self.score:.1f} / {self.max_score}"


@dataclass
class HardFailFinding:
    name: str
    triggered: bool
    detail: str


@dataclass
class Gate3Result:
    stock_id: str
    total_score: float
    verdict: str                # "Pass" | "Conditional Watchlist" | "Fail"
    sub_layers: list[SubLayerScore] = field(default_factory=list)
    hard_fails: list[HardFailFinding] = field(default_factory=list)
    hard_fail_triggered: bool = False
    headline_metrics: list[metrics.Metric] = field(default_factory=list)
    thesis_bullets: list[str] = field(default_factory=list)
    risk_bullets: list[str] = field(default_factory=list)
    data_gaps: list[str] = field(default_factory=list)

    def memo(self) -> str:
        lines = [
            f"# Gate 3 — Forensic Quality: {self.stock_id}",
            f"Score: {self.total_score:.1f} / 100 → {self.verdict}",
        ]
        if self.hard_fail_triggered:
            lines.append("⚠ Hard-Fail Override TRIGGERED — automatic rejection regardless of score")
        lines.append("")

        lines.append("## Sub-layer scores")
        for s in self.sub_layers:
            lines.append(f"- {s.as_line()}")
        lines.append("")

        lines.append("## Headline metrics")
        for m in self.headline_metrics:
            lines.append(f"- {m.cite()}")
        lines.append("")

        if self.hard_fails:
            lines.append("## Hard-Fail Overrides")
            for hf in self.hard_fails:
                mark = "⚠" if hf.triggered else "✓"
                lines.append(f"- {mark} {hf.name}: {hf.detail}")
            lines.append("")

        if self.thesis_bullets:
            lines.append("## Thesis (forensic-quality perspective)")
            for b in self.thesis_bullets:
                lines.append(f"- {b}")
            lines.append("")

        if self.risk_bullets:
            lines.append("## Risks")
            for b in self.risk_bullets:
                lines.append(f"- {b}")
            lines.append("")

        if self.data_gaps:
            lines.append("## Data gaps / staleness")
            for g in self.data_gaps:
                lines.append(f"- {g}")

        return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────
# Scoring helpers
# ──────────────────────────────────────────────────────────────────────────

def _score_3a_operating(
    income: list[parsers.IncomeStatement],
    cash: list[parsers.CashFlow],
    balance: list[parsers.BalanceSheet],
    rev_df,
    weight: int,
    th: Gate3Thresholds,
) -> SubLayerScore:
    """
    Operating Quality — 25 pts.
    Sub-components: revenue growth (7), margin direction (6), earnings quality (CFO/NI) (7), ROE (5).
    """
    components = []
    earned = 0.0

    # Revenue growth (7 pts)
    rev_yoy = metrics.revenue_growth_yoy(rev_df)
    rev_ttm = metrics.revenue_ttm_trend(rev_df)
    rev_pts = 0.0
    if rev_yoy.value is not None:
        if rev_yoy.value > 10:
            rev_pts += 4
        elif rev_yoy.value > 0:
            rev_pts += 2
        elif rev_yoy.value > -10:
            rev_pts += 1
    if rev_ttm.value is not None:
        if rev_ttm.value > 10:
            rev_pts += 3
        elif rev_ttm.value > 0:
            rev_pts += 2
        elif rev_ttm.value > -5:
            rev_pts += 1
    components.append({"check": "Revenue growth", "points": rev_pts, "max": 7, "detail": f"YoY {rev_yoy.value}, TTM {rev_ttm.value}"})
    earned += rev_pts

    # Margin direction (6 pts)
    gm_pts = 0.0
    if len(income) >= 4:
        recent = sorted(income, key=lambda r: r.date)[-4:]
        gm_series = [r.gross_margin for r in recent if r.gross_margin is not None]
        if len(gm_series) >= 2:
            if gm_series[-1] >= gm_series[0]:
                gm_pts += 3
            else:
                gm_pts += 1
        om_series = [r.operating_margin for r in recent if r.operating_margin is not None]
        if len(om_series) >= 2:
            if om_series[-1] >= om_series[0]:
                gm_pts += 3
            else:
                gm_pts += 1
    components.append({"check": "Margin direction", "points": gm_pts, "max": 6, "detail": "4Q GM + OM trend"})
    earned += gm_pts

    # Earnings quality — CFO/NI (7 pts)
    cfo_ni = metrics.cfo_to_ni_ratio(income, cash, n_qtrs=4)
    eq_pts = 0.0
    if cfo_ni.value is not None:
        if cfo_ni.value >= th.cfo_to_ni_healthy:
            eq_pts = 7
        elif cfo_ni.value >= 0.6:
            eq_pts = 4
        elif cfo_ni.value >= th.cfo_to_ni_warning:
            eq_pts = 2
        else:
            eq_pts = 0
    components.append({"check": "CFO/NI", "points": eq_pts, "max": 7, "detail": cfo_ni.cite()})
    earned += eq_pts

    # ROE (5 pts)
    roe = metrics.roe_proxy(income, balance)
    roe_pts = 0.0
    if roe.value is not None:
        if roe.value >= 15:
            roe_pts = 5
        elif roe.value >= 10:
            roe_pts = 3
        elif roe.value >= 5:
            roe_pts = 2
        elif roe.value >= 0:
            roe_pts = 1
    components.append({"check": "ROE (proxy)", "points": roe_pts, "max": 5, "detail": roe.cite()})
    earned += roe_pts

    return SubLayerScore("3A", "Operating Quality", earned, weight, components)


def _score_3b_balance_sheet(
    income: list[parsers.IncomeStatement],
    cash: list[parsers.CashFlow],
    balance: list[parsers.BalanceSheet],
    weight: int,
    th: Gate3Thresholds,
) -> SubLayerScore:
    """
    Balance Sheet & Cash Survival — 35 pts.
    Leverage (10), liquidity (8), interest coverage (7), FCF integrity (10).
    """
    components = []
    earned = 0.0

    # Leverage — net debt / EBITDA (10 pts)
    nd_ebitda = metrics.net_debt_to_ebitda(balance, income)
    lev_pts = 0.0
    if nd_ebitda.value is not None:
        v = nd_ebitda.value
        if v <= 0:
            lev_pts = 10  # net cash
        elif v <= 1.5:
            lev_pts = 9
        elif v <= th.net_debt_to_ebitda_warning:
            lev_pts = 7
        elif v <= 4.0:
            lev_pts = 4
        elif v <= th.net_debt_to_ebitda_hardfail:
            lev_pts = 2
        else:
            lev_pts = 0
    components.append({"check": "Net debt / EBITDA", "points": lev_pts, "max": 10, "detail": nd_ebitda.cite()})
    earned += lev_pts

    # Liquidity — current ratio (4) + cash/ST debt (4) = 8 pts
    cr = metrics.current_ratio_latest(balance)
    cash_st = metrics.cash_to_short_term_debt(balance)
    liq_pts = 0.0
    if cr.value is not None:
        if cr.value >= 1.5:
            liq_pts += 4
        elif cr.value >= th.current_ratio_min:
            liq_pts += 2
    if cash_st.value is not None:
        if cash_st.value >= 2.0:
            liq_pts += 4
        elif cash_st.value >= th.cash_to_short_term_debt_min:
            liq_pts += 2
    components.append({"check": "Liquidity", "points": liq_pts, "max": 8, "detail": f"{cr.cite()}; {cash_st.cite()}"})
    earned += liq_pts

    # Interest coverage (7 pts)
    ic = metrics.interest_coverage(income, 4)
    ic_pts = 0.0
    if ic.value is not None:
        if ic.value >= 10:
            ic_pts = 7
        elif ic.value >= 5:
            ic_pts = 5
        elif ic.value >= th.interest_coverage_min:
            ic_pts = 3
        else:
            ic_pts = 0
    else:
        # May be missing because no interest expense (debt-free); partial credit
        bs = parsers.latest(balance)
        if bs and (bs.total_debt or 0) == 0:
            ic_pts = 7  # debt-free
            ic.note = "Debt-free — no interest expense"
    components.append({"check": "Interest coverage", "points": ic_pts, "max": 7, "detail": ic.cite()})
    earned += ic_pts

    # FCF integrity (10 pts)
    fcf_margin = metrics.free_cash_flow_margin(cash, income, 4)
    fcf_pts = 0.0
    if fcf_margin.value is not None:
        if fcf_margin.value >= 15:
            fcf_pts = 10
        elif fcf_margin.value >= 5:
            fcf_pts = 7
        elif fcf_margin.value >= 0:
            fcf_pts = 4
        else:
            fcf_pts = 0
    components.append({"check": "FCF margin", "points": fcf_pts, "max": 10, "detail": fcf_margin.cite()})
    earned += fcf_pts

    return SubLayerScore("3B", "Balance Sheet & Cash Survival", earned, weight, components)


def _score_3c_ownership(
    flow_df,
    ownership_df,
    margin_df,
    weight: int,
) -> SubLayerScore:
    """
    Ownership & Market Structure — 20 pts.
    Institutional net flow (10), foreign ownership trend (5), margin structure (5).
    """
    components = []
    earned = 0.0

    # Institutional flow (10 pts)
    flows = metrics.institutional_net_flow(flow_df, lookback_days=60)
    pos_directions = 0
    neg_directions = 0
    for k, m in flows.items():
        if m.value is None:
            continue
        if m.value > 0:
            pos_directions += 1
        elif m.value < 0:
            neg_directions += 1

    if pos_directions >= 2:
        flow_pts = 10  # broad sponsorship
    elif pos_directions == 1 and neg_directions == 0:
        flow_pts = 6
    elif pos_directions == neg_directions:
        flow_pts = 4
    elif neg_directions >= 2:
        flow_pts = 0
    else:
        flow_pts = 3
    components.append({
        "check": "Institutional flow (60d net)",
        "points": flow_pts, "max": 10,
        "detail": "; ".join([m.cite() for m in flows.values()])
    })
    earned += flow_pts

    # Foreign ownership trend (5 pts)
    fo_pts = 0.0
    fo_detail = "no data"
    try:
        if not ownership_df.empty and "ForeignInvestmentSharesRatio" in ownership_df.columns:
            df = ownership_df.sort_values("date").copy()
            if len(df) >= 2:
                first = df.iloc[0]["ForeignInvestmentSharesRatio"]
                last = df.iloc[-1]["ForeignInvestmentSharesRatio"]
                if first is not None and last is not None:
                    if last > first:
                        fo_pts = 5
                        fo_detail = f"Foreign holdings rising: {first:.1f}% → {last:.1f}%"
                    elif last == first:
                        fo_pts = 3
                        fo_detail = f"Foreign holdings flat at ~{last:.1f}%"
                    else:
                        fo_pts = 1
                        fo_detail = f"Foreign holdings declining: {first:.1f}% → {last:.1f}%"
    except Exception:
        pass
    components.append({"check": "Foreign ownership trend", "points": fo_pts, "max": 5, "detail": fo_detail})
    earned += fo_pts

    # Margin/short structure (5 pts)
    m_pts = 0.0
    m_detail = "no data"
    try:
        if not margin_df.empty and "MarginPurchaseTodayBalance" in margin_df.columns:
            df = margin_df.sort_values("date").copy()
            if len(df) >= 20:
                recent = df.tail(20)
                margin_change = recent.iloc[-1]["MarginPurchaseTodayBalance"] - recent.iloc[0]["MarginPurchaseTodayBalance"]
                short_change = recent.iloc[-1]["ShortSaleTodayBalance"] - recent.iloc[0]["ShortSaleTodayBalance"]
                # Retail margin declining + short covering = healthy
                if margin_change < 0 and short_change <= 0:
                    m_pts = 5
                    m_detail = "Retail margin declining or flat, shorts covering — clean"
                elif margin_change < 0:
                    m_pts = 4
                    m_detail = "Retail margin declining"
                elif short_change < 0:
                    m_pts = 3
                    m_detail = "Shorts covering but margin rising — mixed"
                elif margin_change > 0 and short_change > 0:
                    m_pts = 2
                    m_detail = "Margin and short both rising — battleground"
                else:
                    m_pts = 2
                    m_detail = "Elevated retail margin"
    except Exception:
        pass
    components.append({"check": "Margin/short structure", "points": m_pts, "max": 5, "detail": m_detail})
    earned += m_pts

    return SubLayerScore("3C", "Ownership & Market Structure", earned, weight, components)


def _score_3d_derivatives(client: FinMindClient, stock_id: str, weight: int) -> SubLayerScore:
    """
    Derivatives & Capital Structure — 10 pts.
    CB existence & pricing (5), single-stock futures/options presence (5).
    Tier-dependent; partial if data unavailable.
    """
    components = []
    earned = 0.0
    today = datetime.today()
    cb_start = (today - timedelta(days=180)).strftime("%Y-%m-%d")

    # CB check (5 pts)
    cb_pts = 0.0
    cb_detail = "no CB outstanding (default pass)"
    try:
        cb_info = client.get("TaiwanStockConvertibleBondInfo")
        if not cb_info.empty:
            # Filter for this underlying if schema supports it
            # Schema: cb_id often encodes underlying; match manually if needed
            # Conservative: if underlying appears in cb_id or cb_name, check further
            matching = cb_info[cb_info["cb_id"].astype(str).str.startswith(stock_id, na=False)]
            if matching.empty:
                cb_pts = 5
                cb_detail = "No outstanding CB for this underlying — no dilution risk from CB"
            else:
                cb_pts = 3  # CB exists, need deeper look
                cb_detail = f"{len(matching)} CB(s) outstanding — review required"
    except Exception as e:  # noqa: BLE001
        cb_detail = f"CB data unavailable: {e}"
    components.append({"check": "Convertible bond check", "points": cb_pts, "max": 5, "detail": cb_detail})
    earned += cb_pts

    # Single-stock futures/options presence (5 pts) — simplified: presence of derivatives = liquid, confirmable
    fut_pts = 0.0
    fut_detail = "data not fetched at this tier"
    try:
        fut_info = client.get("TaiwanFutOptDailyInfo")
        if not fut_info.empty:
            matches = fut_info[fut_info["code"].astype(str).str.contains(stock_id, na=False)]
            if not matches.empty:
                fut_pts = 5
                fut_detail = f"{len(matches)} single-stock derivative(s) listed — market structure deep"
            else:
                fut_pts = 3
                fut_detail = "No single-stock derivatives — can't cross-confirm via futures/options"
    except Exception as e:  # noqa: BLE001
        fut_detail = f"Futures info unavailable: {e}"
        fut_pts = 2  # partial credit for data gap, not the company's fault
    components.append({"check": "Single-stock derivatives presence", "points": fut_pts, "max": 5, "detail": fut_detail})
    earned += fut_pts

    return SubLayerScore("3D", "Derivatives & Capital Structure", earned, weight, components)


def _score_3e_data_integrity(
    client: FinMindClient,
    stock_id: str,
    rev_df,
    income: list[parsers.IncomeStatement],
    weight: int,
) -> SubLayerScore:
    """
    Data Integrity & Event Audit — 10 pts.
    Monthly vs quarterly revenue consistency (5), news/governance red flags (5).
    """
    components = []
    earned = 0.0
    today = datetime.today()

    # Monthly vs quarterly revenue consistency (5 pts)
    consistency_pts = 0.0
    consistency_detail = "insufficient data for check"
    try:
        if not rev_df.empty and income and "revenue" in rev_df.columns:
            # Take latest quarter revenue from income statements
            recent_q = sorted(income, key=lambda r: r.date)[-1]
            q_rev = recent_q.revenue
            q_date = recent_q.date[:7]  # YYYY-MM
            # Sum monthly revenue for the quarter
            import pandas as pd
            rev_df_copy = rev_df.copy()
            rev_df_copy["date"] = pd.to_datetime(rev_df_copy["date"])
            q_start = pd.to_datetime(q_date + "-01") - pd.DateOffset(months=2)
            q_end = pd.to_datetime(q_date + "-01") + pd.DateOffset(months=1)
            q_monthly = rev_df_copy[(rev_df_copy["date"] >= q_start) & (rev_df_copy["date"] < q_end)]
            m_sum = q_monthly["revenue"].sum()
            if q_rev and m_sum and abs(m_sum - q_rev) / q_rev < 0.05:
                consistency_pts = 5
                consistency_detail = f"Monthly sum vs quarterly report reconcile (Δ < 5%)"
            elif q_rev:
                consistency_pts = 2
                consistency_detail = f"Monthly sum {m_sum:,.0f} vs quarterly {q_rev:,.0f} — investigate"
    except Exception as e:  # noqa: BLE001
        consistency_detail = f"Check errored: {e}"
    components.append({"check": "Monthly↔Quarterly revenue consistency", "points": consistency_pts, "max": 5, "detail": consistency_detail})
    earned += consistency_pts

    # News red-flag scan (5 pts) — default positive unless we find trouble keywords
    news_pts = 5.0  # default pass
    news_detail = "no red-flag keywords found"
    red_flag_keywords = [
        "auditor", "會計師更換", "辭任", "董事請辭",
        "掏空", "財報重編", "restatement", "going concern",
        "關係人交易", "解任", "停牌",
    ]
    try:
        news_df = client.news(stock_id, (today - timedelta(days=90)).strftime("%Y-%m-%d"))
        if not news_df.empty and "title" in news_df.columns:
            hits = []
            for kw in red_flag_keywords:
                matching = news_df[news_df["title"].str.contains(kw, na=False)]
                if not matching.empty:
                    hits.append(f"{kw} ({len(matching)})")
            if hits:
                news_pts = 1.0
                news_detail = "Red-flag keywords in news: " + "; ".join(hits)
    except Exception as e:  # noqa: BLE001
        news_detail = f"News check errored: {e}"
    components.append({"check": "Governance/news red-flag scan", "points": news_pts, "max": 5, "detail": news_detail})
    earned += news_pts

    return SubLayerScore("3E", "Data Integrity & Event Audit", earned, weight, components)


# ──────────────────────────────────────────────────────────────────────────
# Hard-fail overrides
# ──────────────────────────────────────────────────────────────────────────

def _check_persistent_cfo_ni_divergence(
    income: list[parsers.IncomeStatement],
    cash: list[parsers.CashFlow],
    th: Gate3Thresholds,
) -> tuple[bool, str]:
    """Return whether CFO/NI weakness persists for the configured consecutive-quarter window."""
    income_by_date = {record.date: record for record in income}
    cash_by_date = {record.date: record for record in cash}
    dates = sorted(set(income_by_date) | set(cash_by_date))

    streak = 0
    max_streak = 0
    computable_quarters = 0
    detail_parts: list[str] = []

    for date in dates:
        inc = income_by_date.get(date)
        cf = cash_by_date.get(date)

        ratio: Optional[float] = None
        if inc is not None and cf is not None and inc.net_income not in (None, 0) and cf.cfo is not None:
            ratio = cf.cfo / inc.net_income
            computable_quarters += 1
            if ratio < th.cfo_to_ni_warning:
                streak += 1
                max_streak = max(max_streak, streak)
            else:
                streak = 0
        else:
            streak = 0

        rendered = "n/a" if ratio is None else f"{ratio:.2f}x"
        detail_parts.append(f"{date}: {rendered}")

    recent_detail = "; ".join(detail_parts[-max(th.cfo_to_ni_warning_qtrs + 2, 4):])
    if computable_quarters < th.cfo_to_ni_warning_qtrs:
        return (
            False,
            "unverifiable: only "
            f"{computable_quarters} computable quarter(s) for CFO/NI persistence test "
            f"(need {th.cfo_to_ni_warning_qtrs}); recent series: {recent_detail}",
        )

    if max_streak >= th.cfo_to_ni_warning_qtrs:
        return (
            True,
            f"{max_streak} consecutive quarters below {th.cfo_to_ni_warning:.2f}x; recent series: {recent_detail}",
        )

    return (
        False,
        f"max weak streak {max_streak}/{th.cfo_to_ni_warning_qtrs}; recent series: {recent_detail}",
    )


def _check_hard_fails(
    income: list[parsers.IncomeStatement],
    cash: list[parsers.CashFlow],
    balance: list[parsers.BalanceSheet],
    sub_3c: SubLayerScore,
    sub_3e: SubLayerScore,
    th: Gate3Thresholds,
) -> list[HardFailFinding]:
    findings: list[HardFailFinding] = []

    # 1. Refinancing wall + weak coverage
    bs = parsers.latest(balance)
    ic = metrics.interest_coverage(income, 4)
    cash_st = metrics.cash_to_short_term_debt(balance)
    triggered_1 = False
    detail_1 = "not triggered"
    if bs and bs.short_term_borrowings and bs.short_term_borrowings > 0:
        weak_cov = ic.value is not None and ic.value < th.interest_coverage_hardfail
        weak_cash = cash_st.value is not None and cash_st.value < th.cash_to_short_term_debt_min
        if weak_cov and weak_cash:
            triggered_1 = True
            detail_1 = f"ST debt present, coverage {ic.value:.1f}x < {th.interest_coverage_hardfail}, cash/ST {cash_st.value:.2f} < 1.0"
    findings.append(HardFailFinding("Refinancing wall + weak coverage", triggered_1, detail_1))

    # 2. Persistent CFO/NI divergence
    triggered_2, detail_2 = _check_persistent_cfo_ni_divergence(income, cash, th)
    findings.append(HardFailFinding("Persistent CFO/NI divergence", triggered_2, detail_2))

    # 3. Governance red flags (pulled from 3E score)
    news_comp = next((c for c in sub_3e.components if "red-flag" in c["check"]), None)
    triggered_3 = news_comp is not None and news_comp["points"] <= 1.0
    detail_3 = news_comp["detail"] if news_comp else "check skipped"
    findings.append(HardFailFinding("Governance red flags", triggered_3, detail_3))

    # 4. Ownership/derivatives conflict with fundamentals
    # Conservative proxy: 3C score < 6 (net outflow + weak margin structure) + fundamentals OK
    triggered_4 = False
    detail_4 = "not triggered"
    if sub_3c.score < 6:
        triggered_4 = True
        detail_4 = f"Ownership structure weak (3C score {sub_3c.score:.1f}/20) — check for unresolved conflict"
    findings.append(HardFailFinding("Unresolved cross-data conflict", triggered_4, detail_4))

    # 5. Extreme leverage
    nd_ebitda = metrics.net_debt_to_ebitda(balance, income)
    triggered_5 = nd_ebitda.value is not None and nd_ebitda.value > th.net_debt_to_ebitda_hardfail
    detail_5 = nd_ebitda.cite()
    findings.append(HardFailFinding("Extreme leverage", triggered_5, detail_5))

    # 6. Placeholder for repeat dilution — requires corporate-action history (caller can supply)
    findings.append(HardFailFinding("Repeated dilution without repair",
                                    False, "manual check — review TaiwanStockCapitalReductionReferencePrice history"))

    # 7. Data gap hard-fail if too many missing
    missing = 0
    for rec in income + cash + balance:
        missing += len(rec.missing_fields)
    total_fields = len(income) * 12 + len(cash) * 6 + len(balance) * 11
    gap_ratio = missing / max(total_fields, 1)
    triggered_7 = gap_ratio > 0.5
    findings.append(HardFailFinding("Excessive data gaps", triggered_7, f"{gap_ratio*100:.0f}% of fields missing"))

    return findings


# ──────────────────────────────────────────────────────────────────────────
# Main entry
# ──────────────────────────────────────────────────────────────────────────

def run(
    client: FinMindClient,
    stock_id: str,
    weights: Optional[Gate3Weights] = None,
    thresholds: Optional[Gate3Thresholds] = None,
) -> Gate3Result:
    """Run Gate 3 — Forensic Quality on a single stock."""
    weights = weights or DEFAULT_CONFIG.gate3_weights
    thresholds = thresholds or DEFAULT_CONFIG.gate3_thresholds

    today = datetime.today()
    fs_start = (today - timedelta(days=730)).strftime("%Y-%m-%d")  # 2y history
    rev_start = (today - timedelta(days=730)).strftime("%Y-%m-%d")
    flow_start = (today - timedelta(days=90)).strftime("%Y-%m-%d")
    ownership_start = (today - timedelta(days=180)).strftime("%Y-%m-%d")

    # Fetch primary data
    fs_df = client.financial_statements(stock_id, fs_start)
    bs_df = client.balance_sheet(stock_id, fs_start)
    cf_df = client.cash_flow(stock_id, fs_start)
    rev_df = client.monthly_revenue(stock_id, rev_start)
    flow_df = client.institutional_flow(stock_id, flow_start)
    own_df = client.foreign_ownership(stock_id, ownership_start)
    mgn_df = client.margin_short(stock_id, flow_start)

    income = parsers.parse_income_statements(fs_df)
    balance = parsers.parse_balance_sheets(bs_df)
    cash = parsers.parse_cash_flows(cf_df)

    # Score each sub-layer
    s_3a = _score_3a_operating(income, cash, balance, rev_df, weights.operating_quality, thresholds)
    s_3b = _score_3b_balance_sheet(income, cash, balance, weights.balance_sheet_survival, thresholds)
    s_3c = _score_3c_ownership(flow_df, own_df, mgn_df, weights.ownership_market_structure)
    s_3d = _score_3d_derivatives(client, stock_id, weights.derivatives_capital_structure)
    s_3e = _score_3e_data_integrity(client, stock_id, rev_df, income, weights.data_integrity)

    sub_layers = [s_3a, s_3b, s_3c, s_3d, s_3e]
    total = sum(s.score for s in sub_layers)

    # Hard fails
    hard_fails = _check_hard_fails(income, cash, balance, s_3c, s_3e, thresholds)
    hard_fail_triggered = any(hf.triggered for hf in hard_fails)

    # Verdict
    if hard_fail_triggered:
        verdict = "Fail (Hard-Fail Override)"
    elif total >= thresholds.pass_threshold:
        verdict = "Pass"
    elif total >= thresholds.conditional_threshold:
        verdict = "Conditional Watchlist"
    else:
        verdict = "Fail"

    # Headline metrics
    headline = [
        metrics.revenue_growth_yoy(rev_df),
        metrics.gross_margin_latest(income),
        metrics.operating_margin_latest(income),
        metrics.cfo_to_ni_ratio(income, cash, 4),
        metrics.net_debt_to_ebitda(balance, income),
        metrics.interest_coverage(income, 4),
        metrics.free_cash_flow_margin(cash, income, 4),
        metrics.roe_proxy(income, balance),
    ]

    # Data gaps summary
    gaps: list[str] = []
    for rec in [parsers.latest(income), parsers.latest(balance), parsers.latest(cash)]:
        if rec and rec.missing_fields:
            gaps.append(f"{type(rec).__name__} @ {rec.date}: missing {', '.join(rec.missing_fields[:5])}" +
                        (f" and {len(rec.missing_fields)-5} more" if len(rec.missing_fields) > 5 else ""))

    return Gate3Result(
        stock_id=stock_id,
        total_score=total,
        verdict=verdict,
        sub_layers=sub_layers,
        hard_fails=hard_fails,
        hard_fail_triggered=hard_fail_triggered,
        headline_metrics=headline,
        data_gaps=gaps,
    )
