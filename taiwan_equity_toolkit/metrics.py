"""
Metrics — derived financial ratios and growth rates.

Every metric carries its source dataset(s) and as-of date, enabling direct
citation in memos. Metrics return None (not 0, not NaN) when underlying data
is missing — this is deliberate. Silent zeros hide problems.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd

from taiwan_equity_toolkit.parsers import (
    BalanceSheet,
    CashFlow,
    IncomeStatement,
    latest,
    ttm,
)


def _sum_required(records: list[object], attr: str) -> Optional[float]:
    """Sum an attribute across records, but surface missing inputs as None."""
    values: list[float] = []
    for record in records:
        value = getattr(record, attr, None)
        if value is None:
            return None
        values.append(float(value))
    return sum(values)


@dataclass
class Metric:
    """A single metric value with provenance."""
    name: str
    value: Optional[float]
    unit: str                    # e.g., "%", "x", "ratio", "NT$", "qtrs"
    as_of: Optional[str]         # date of source data
    source: str                  # FinMind dataset name(s)
    note: str = ""               # caveats, staleness, missing-data notes

    def __repr__(self) -> str:
        v = f"{self.value:.2f}" if self.value is not None else "n/a"
        return f"{self.name}={v}{self.unit} ({self.source}, {self.as_of}){' — ' + self.note if self.note else ''}"

    def cite(self) -> str:
        """Short citation string for inline use in memos."""
        if self.value is None:
            return f"{self.name}: n/a ({self.source}, {self.as_of or 'no data'})"
        v = f"{self.value:.2f}{self.unit}"
        return f"{self.name}={v} ({self.source}, {self.as_of})"


# ──────────────────────────────────────────────────────────────────────────
# Operating quality (3A)
# ──────────────────────────────────────────────────────────────────────────

def cfo_to_ni_ratio(income: list[IncomeStatement], cash: list[CashFlow], n_qtrs: int = 4) -> Metric:
    """Trailing-n-quarter CFO/NI ratio. Healthy ≥ 0.8."""
    inc_ttm = ttm(income, n_qtrs)
    cf_ttm = ttm(cash, n_qtrs)

    if not inc_ttm or not cf_ttm:
        return Metric("CFO/NI", None, "x", None, "TaiwanStockFinancialStatements + TaiwanStockCashFlowsStatement", "insufficient data")

    ni_sum = _sum_required(inc_ttm, "net_income")
    cfo_sum = _sum_required(cf_ttm, "cfo")
    if ni_sum is None or cfo_sum is None:
        return Metric(
            "CFO/NI",
            None,
            "x",
            inc_ttm[-1].date,
            "TaiwanStockFinancialStatements + TaiwanStockCashFlowsStatement",
            "missing quarter in trailing window",
        )

    if ni_sum == 0:
        return Metric("CFO/NI", None, "x", inc_ttm[-1].date, "TaiwanStockFinancialStatements + TaiwanStockCashFlowsStatement", "NI sum is zero")

    ratio = cfo_sum / ni_sum
    return Metric("CFO/NI", ratio, "x", inc_ttm[-1].date, "TaiwanStockFinancialStatements + TaiwanStockCashFlowsStatement", f"trailing {n_qtrs}Q")


def revenue_growth_yoy(monthly_rev_df: pd.DataFrame) -> Metric:
    """YoY growth of most recent monthly revenue."""
    if monthly_rev_df.empty or "revenue" not in monthly_rev_df.columns:
        return Metric("Revenue YoY", None, "%", None, "TaiwanStockMonthRevenue", "empty data")

    df = monthly_rev_df.sort_values("date").copy()
    if len(df) < 13:
        return Metric("Revenue YoY", None, "%", df.iloc[-1]["date"] if len(df) else None, "TaiwanStockMonthRevenue", "need 13+ months")

    latest_rev = df.iloc[-1]["revenue"]
    year_ago_rev = df.iloc[-13]["revenue"]
    if not year_ago_rev or year_ago_rev == 0:
        return Metric("Revenue YoY", None, "%", df.iloc[-1]["date"], "TaiwanStockMonthRevenue", "year-ago zero")

    yoy = (latest_rev - year_ago_rev) / year_ago_rev * 100
    return Metric("Revenue YoY", yoy, "%", df.iloc[-1]["date"], "TaiwanStockMonthRevenue")


def revenue_ttm_trend(monthly_rev_df: pd.DataFrame) -> Metric:
    """TTM revenue vs. prior TTM — broader-trend growth."""
    if monthly_rev_df.empty or "revenue" not in monthly_rev_df.columns:
        return Metric("Revenue TTM growth", None, "%", None, "TaiwanStockMonthRevenue", "empty data")

    df = monthly_rev_df.sort_values("date").copy()
    if len(df) < 24:
        return Metric("Revenue TTM growth", None, "%", df.iloc[-1]["date"] if len(df) else None, "TaiwanStockMonthRevenue", "need 24+ months")

    current_ttm = df.iloc[-12:]["revenue"].sum()
    prior_ttm = df.iloc[-24:-12]["revenue"].sum()
    if prior_ttm == 0:
        return Metric("Revenue TTM growth", None, "%", df.iloc[-1]["date"], "TaiwanStockMonthRevenue", "prior TTM zero")

    growth = (current_ttm - prior_ttm) / prior_ttm * 100
    return Metric("Revenue TTM growth", growth, "%", df.iloc[-1]["date"], "TaiwanStockMonthRevenue")


def gross_margin_latest(income: list[IncomeStatement]) -> Metric:
    rec = latest(income)
    if not rec or rec.gross_margin is None:
        return Metric("Gross margin", None, "%", rec.date if rec else None, "TaiwanStockFinancialStatements", "missing revenue or GP")
    return Metric("Gross margin", rec.gross_margin * 100, "%", rec.date, "TaiwanStockFinancialStatements")


def operating_margin_latest(income: list[IncomeStatement]) -> Metric:
    rec = latest(income)
    if not rec or rec.operating_margin is None:
        return Metric("Operating margin", None, "%", rec.date if rec else None, "TaiwanStockFinancialStatements", "missing data")
    return Metric("Operating margin", rec.operating_margin * 100, "%", rec.date, "TaiwanStockFinancialStatements")


def roe_proxy(income: list[IncomeStatement], balance: list[BalanceSheet]) -> Metric:
    """ROE proxy: trailing 4Q net income / latest equity."""
    inc_ttm = ttm(income, 4)
    bs = latest(balance)
    if not inc_ttm or not bs or bs.equity is None:
        return Metric("ROE (proxy)", None, "%", bs.date if bs else None, "TaiwanStockFinancialStatements + TaiwanStockBalanceSheet", "missing data")
    ni_sum = _sum_required(inc_ttm, "net_income")
    if ni_sum is None:
        return Metric("ROE (proxy)", None, "%", bs.date, "TaiwanStockFinancialStatements + TaiwanStockBalanceSheet", "missing quarter in trailing window")
    if bs.equity == 0:
        return Metric("ROE (proxy)", None, "%", bs.date, "TaiwanStockFinancialStatements + TaiwanStockBalanceSheet", "equity zero")
    return Metric("ROE (proxy)", ni_sum / bs.equity * 100, "%", bs.date, "TaiwanStockFinancialStatements + TaiwanStockBalanceSheet", "trailing 4Q NI / latest equity")


# ──────────────────────────────────────────────────────────────────────────
# Balance sheet & cash survival (3B)
# ──────────────────────────────────────────────────────────────────────────

def net_debt_to_ebitda(balance: list[BalanceSheet], income: list[IncomeStatement]) -> Metric:
    """Net debt / trailing-4Q EBITDA (EBIT + D&A approximation)."""
    bs = latest(balance)
    inc_ttm = ttm(income, 4)
    if not bs or not inc_ttm:
        return Metric("Net debt / EBITDA", None, "x", bs.date if bs else None, "TaiwanStockBalanceSheet + TaiwanStockFinancialStatements", "missing data")

    nd = bs.net_debt
    if nd is None:
        return Metric("Net debt / EBITDA", None, "x", bs.date, "TaiwanStockBalanceSheet + TaiwanStockFinancialStatements", "net debt unavailable")

    ebit_sum = _sum_required(inc_ttm, "operating_income")
    dna_sum = _sum_required(inc_ttm, "depreciation")
    if ebit_sum is None or dna_sum is None:
        return Metric("Net debt / EBITDA", None, "x", bs.date, "TaiwanStockBalanceSheet + TaiwanStockFinancialStatements", "missing quarter in trailing window")
    ebitda = ebit_sum + dna_sum
    if ebitda <= 0:
        return Metric("Net debt / EBITDA", None, "x", bs.date, "TaiwanStockBalanceSheet + TaiwanStockFinancialStatements", "EBITDA non-positive")

    return Metric("Net debt / EBITDA", nd / ebitda, "x", bs.date, "TaiwanStockBalanceSheet + TaiwanStockFinancialStatements", "trailing 4Q EBITDA")


def interest_coverage(income: list[IncomeStatement], n_qtrs: int = 4) -> Metric:
    """EBIT / interest expense, trailing-n-quarter."""
    inc_ttm = ttm(income, n_qtrs)
    if not inc_ttm:
        return Metric("Interest coverage", None, "x", None, "TaiwanStockFinancialStatements", "no data")

    ebit = _sum_required(inc_ttm, "operating_income")
    ie = _sum_required(inc_ttm, "interest_expense")
    if ebit is None or ie is None:
        return Metric("Interest coverage", None, "x", inc_ttm[-1].date, "TaiwanStockFinancialStatements", "missing quarter in trailing window")
    if ie == 0:
        return Metric("Interest coverage", None, "x", inc_ttm[-1].date, "TaiwanStockFinancialStatements", "interest expense zero or missing")
    return Metric("Interest coverage", ebit / abs(ie), "x", inc_ttm[-1].date, "TaiwanStockFinancialStatements", f"trailing {n_qtrs}Q")


def current_ratio_latest(balance: list[BalanceSheet]) -> Metric:
    bs = latest(balance)
    if not bs or bs.current_ratio is None:
        return Metric("Current ratio", None, "x", bs.date if bs else None, "TaiwanStockBalanceSheet", "missing data")
    return Metric("Current ratio", bs.current_ratio, "x", bs.date, "TaiwanStockBalanceSheet")


def cash_to_short_term_debt(balance: list[BalanceSheet]) -> Metric:
    bs = latest(balance)
    if not bs:
        return Metric("Cash / ST debt", None, "x", None, "TaiwanStockBalanceSheet", "no data")
    if bs.cash_and_equivalents is None or bs.short_term_borrowings is None:
        return Metric("Cash / ST debt", None, "x", bs.date, "TaiwanStockBalanceSheet", "missing cash or ST debt")
    if bs.short_term_borrowings == 0:
        return Metric("Cash / ST debt", float("inf"), "x", bs.date, "TaiwanStockBalanceSheet", "no short-term debt")
    return Metric("Cash / ST debt", bs.cash_and_equivalents / bs.short_term_borrowings, "x", bs.date, "TaiwanStockBalanceSheet")


def free_cash_flow_margin(cash: list[CashFlow], income: list[IncomeStatement], n_qtrs: int = 4) -> Metric:
    """FCF margin: trailing-n-Q FCF / trailing-n-Q revenue."""
    cf_ttm = ttm(cash, n_qtrs)
    inc_ttm = ttm(income, n_qtrs)
    if not cf_ttm or not inc_ttm:
        return Metric("FCF margin", None, "%", None, "TaiwanStockCashFlowsStatement + TaiwanStockFinancialStatements", "insufficient data")

    fcf_values = [r.free_cash_flow for r in cf_ttm]
    if any(v is None for v in fcf_values):
        return Metric("FCF margin", None, "%", cf_ttm[-1].date, "TaiwanStockCashFlowsStatement + TaiwanStockFinancialStatements", "missing quarter in trailing window")
    fcf_sum = sum(float(v) for v in fcf_values if v is not None)
    rev_sum = _sum_required(inc_ttm, "revenue")
    if rev_sum is None:
        return Metric("FCF margin", None, "%", cf_ttm[-1].date, "TaiwanStockCashFlowsStatement + TaiwanStockFinancialStatements", "missing quarter in trailing window")
    if rev_sum == 0:
        return Metric("FCF margin", None, "%", cf_ttm[-1].date, "TaiwanStockCashFlowsStatement + TaiwanStockFinancialStatements", "revenue zero")
    return Metric("FCF margin", fcf_sum / rev_sum * 100, "%", cf_ttm[-1].date, "TaiwanStockCashFlowsStatement + TaiwanStockFinancialStatements", f"trailing {n_qtrs}Q")


# ──────────────────────────────────────────────────────────────────────────
# Price / liquidity
# ──────────────────────────────────────────────────────────────────────────

def adv_ntd(price_df: pd.DataFrame, lookback: int = 20) -> Metric:
    """Average daily dollar volume in NT$, most recent N days."""
    if price_df.empty or "Trading_money" not in price_df.columns:
        return Metric("ADV", None, " NT$", None, "TaiwanStockPrice", "no data")

    recent = price_df.sort_values("date").tail(lookback)
    if recent.empty:
        return Metric("ADV", None, " NT$", None, "TaiwanStockPrice", "no recent data")

    avg = recent["Trading_money"].mean()
    return Metric("ADV", avg, " NT$", recent.iloc[-1]["date"], "TaiwanStockPrice", f"{lookback}-day mean")


def realized_vol(price_adj_df: pd.DataFrame, lookback: int = 30) -> Metric:
    """Annualized realized volatility from adjusted closes."""
    if price_adj_df.empty or "close" not in price_adj_df.columns:
        return Metric(f"Realized vol {lookback}d", None, "%", None, "TaiwanStockPriceAdj", "no data")

    df = price_adj_df.sort_values("date").tail(lookback + 1).copy()
    if len(df) < lookback + 1:
        return Metric(f"Realized vol {lookback}d", None, "%", df.iloc[-1]["date"] if len(df) else None, "TaiwanStockPriceAdj", "insufficient history")

    df["ret"] = df["close"].pct_change()
    vol = df["ret"].std() * (252 ** 0.5) * 100
    return Metric(f"Realized vol {lookback}d", vol, "%", df.iloc[-1]["date"], "TaiwanStockPriceAdj", "annualized")


def correlation_to_series(primary_df: pd.DataFrame, other_df: pd.DataFrame, lookback: int = 90) -> Metric:
    """Return correlation of two adjusted price series over lookback days."""
    if primary_df.empty or other_df.empty:
        return Metric("Correlation", None, "", None, "TaiwanStockPriceAdj", "empty series")

    p = primary_df[["date", "close"]].rename(columns={"close": "a"}).copy()
    o = other_df[["date", "close"]].rename(columns={"close": "b"}).copy()
    merged = p.merge(o, on="date").sort_values("date").tail(lookback + 1)
    if len(merged) < lookback + 1:
        return Metric("Correlation", None, "", None, "TaiwanStockPriceAdj", "insufficient overlap")

    merged["ra"] = merged["a"].pct_change()
    merged["rb"] = merged["b"].pct_change()
    corr = merged["ra"].corr(merged["rb"])
    return Metric("Correlation", corr, "", merged.iloc[-1]["date"], "TaiwanStockPriceAdj", f"{lookback}d returns")


# ──────────────────────────────────────────────────────────────────────────
# Institutional flow (3C)
# ──────────────────────────────────────────────────────────────────────────

# ──────────────────────────────────────────────────────────────────────────
# Reverse-DCF sanity check (6.5A)
# ──────────────────────────────────────────────────────────────────────────

def reverse_dcf_implied_growth(
    market_cap: float,
    ttm_fcf: float,
    discount_rate: float = 0.09,
    terminal_growth: float = 0.025,
    explicit_years: int = 10,
) -> Metric:
    """
    Solve for the explicit-period FCF growth rate implied by the current market cap.

    Uses a 2-stage DCF: grow FCF at g for `explicit_years`, then terminal growth forever.
    Returns the g that makes present value == market_cap.

    Args:
        market_cap: Current market cap (NT$)
        ttm_fcf: Trailing-12-month free cash flow (NT$)
        discount_rate: Required return / WACC
        terminal_growth: Steady-state perpetual growth
        explicit_years: Length of explicit forecast horizon

    Returns:
        Metric with value = implied annual growth rate (%).
        Positive: market expects growth
        Negative: market expects decline
        If ttm_fcf <= 0, returns None with note.
    """
    if ttm_fcf <= 0:
        return Metric("Reverse-DCF implied g", None, "%", None,
                     "derived",
                     "FCF non-positive — reverse DCF undefined")
    if market_cap <= 0:
        return Metric("Reverse-DCF implied g", None, "%", None, "derived", "market cap non-positive")

    def pv_at_growth(g: float) -> float:
        """Present value of explicit + terminal given growth rate g."""
        pv = 0.0
        fcf = ttm_fcf
        for year in range(1, explicit_years + 1):
            fcf *= (1 + g)
            pv += fcf / ((1 + discount_rate) ** year)
        # Terminal value at end of explicit period
        terminal_fcf = fcf * (1 + terminal_growth)
        if discount_rate <= terminal_growth:
            return float("inf")
        terminal_value = terminal_fcf / (discount_rate - terminal_growth)
        pv += terminal_value / ((1 + discount_rate) ** explicit_years)
        return pv

    # Bisection search for g that matches market cap
    lo, hi = -0.20, 0.50  # search between -20% and +50% annual growth
    for _ in range(60):
        mid = (lo + hi) / 2
        pv = pv_at_growth(mid)
        if pv < market_cap:
            lo = mid
        else:
            hi = mid
        if abs(hi - lo) < 0.0001:
            break

    g = (lo + hi) / 2
    note = f"discount={discount_rate*100:.1f}%, terminal={terminal_growth*100:.1f}%, explicit={explicit_years}y"
    return Metric("Reverse-DCF implied g", g * 100, "%", None, "derived", note)


# ──────────────────────────────────────────────────────────────────────────
# Institutional flow (3C)
# ──────────────────────────────────────────────────────────────────────────

def institutional_net_flow(flow_df: pd.DataFrame, lookback_days: int = 60) -> dict[str, Metric]:
    """
    Net buy/sell by investor type (Foreign_Investor, Investment_Trust, Dealer)
    over the most recent lookback days.
    """
    out: dict[str, Metric] = {}
    if flow_df.empty:
        for k in ("Foreign_Investor", "Investment_Trust", "Dealer"):
            out[k] = Metric(f"{k} net flow", None, " shares", None, "TaiwanStockInstitutionalInvestorsBuySell", "no data")
        return out

    df = flow_df.copy()
    # FinMind returns 'name' = investor type, 'buy' / 'sell' counts.
    df["net"] = df["buy"] - df["sell"]
    # Keep most recent lookback by date.
    df["date"] = pd.to_datetime(df["date"])
    cutoff = df["date"].max() - pd.Timedelta(days=lookback_days)
    df = df[df["date"] >= cutoff]

    for investor_type in ("Foreign_Investor", "Investment_Trust", "Dealer"):
        sub = df[df["name"].str.contains(investor_type.replace("_", ""), case=False, na=False) |
                 df["name"].str.contains(investor_type, case=False, na=False)]
        if sub.empty:
            out[investor_type] = Metric(f"{investor_type} net flow", None, " shares", None, "TaiwanStockInstitutionalInvestorsBuySell", "no match")
        else:
            net = sub["net"].sum()
            as_of = sub["date"].max().strftime("%Y-%m-%d")
            out[investor_type] = Metric(f"{investor_type} net flow", net, " shares", as_of, "TaiwanStockInstitutionalInvestorsBuySell", f"last {lookback_days}d sum")
    return out
