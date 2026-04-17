"""
Triage Filter — cheap screens before Gate 3 forensic work.

Purpose: eliminate names that should never reach deep diligence. If a name
fails triage, Gate 3 is skipped.

One function: `run(client, stock_id)` → TriageResult.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from taiwan_equity_toolkit.client import FinMindClient
from taiwan_equity_toolkit.config import DEFAULT_CONFIG, TriageConfig
from taiwan_equity_toolkit import metrics, parsers


@dataclass
class TriageCheck:
    name: str
    passed: bool
    detail: str
    source: str = ""


@dataclass
class TriageResult:
    stock_id: str
    passed: bool
    checks: list[TriageCheck] = field(default_factory=list)
    adv_ntd: Optional[float] = None
    notes: list[str] = field(default_factory=list)

    def failures(self) -> list[TriageCheck]:
        return [c for c in self.checks if not c.passed]

    def summary(self) -> str:
        verdict = "PASS" if self.passed else "FAIL"
        lines = [f"Triage verdict: {verdict} ({self.stock_id})"]
        for c in self.checks:
            mark = "✓" if c.passed else "✗"
            lines.append(f"  {mark} {c.name}: {c.detail}")
        return "\n".join(lines)


def _fail_closed(result: TriageResult, name: str, detail: str, source: str) -> None:
    result.notes.append(detail)
    result.checks.append(TriageCheck(name, False, detail, source))
    result.passed = False


def run(
    client: FinMindClient,
    stock_id: str,
    cfg: Optional[TriageConfig] = None,
    intended_position_ntd: Optional[float] = None,
    short_thesis: bool = False,
) -> TriageResult:
    """
    Run the Triage Filter against a single stock.

    Args:
        client: Authenticated FinMindClient
        stock_id: 4-digit TW stock code
        cfg: Optional TriageConfig override
        intended_position_ntd: If provided, checks position ≤ 10% of ADV
        short_thesis: Relax the monthly-revenue-collapse rule if shorting

    Returns:
        TriageResult with .passed and per-check diagnostics.
    """
    cfg = cfg or DEFAULT_CONFIG.triage
    result = TriageResult(stock_id=stock_id, passed=True)

    today = datetime.today()
    price_start = (today - timedelta(days=60)).strftime("%Y-%m-%d")
    rev_start = (today - timedelta(days=730)).strftime("%Y-%m-%d")  # 2 years monthly
    fs_start = (today - timedelta(days=540)).strftime("%Y-%m-%d")   # ~6 quarters

    # ──────────────────────────────────────────────
    # 1. Disposition / suspension / delisting (hard)
    # ──────────────────────────────────────────────
    try:
        disp = client.get("TaiwanStockDispositionSecuritiesPeriod", stock_id,
                          (today - timedelta(days=180)).strftime("%Y-%m-%d"))
        if not disp.empty:
            # Check any period that is currently active
            current = disp[
                (disp["period_start"] <= today.strftime("%Y-%m-%d")) &
                (disp["period_end"] >= today.strftime("%Y-%m-%d"))
            ] if "period_start" in disp.columns else disp
            if not current.empty:
                result.checks.append(TriageCheck(
                    "Disposition status", False,
                    f"Currently on disposition list: {len(current)} active period(s)",
                    "TaiwanStockDispositionSecuritiesPeriod"
                ))
                result.passed = False
            else:
                result.checks.append(TriageCheck(
                    "Disposition status", True, "Not in an active disposition window",
                    "TaiwanStockDispositionSecuritiesPeriod"
                ))
        else:
            result.checks.append(TriageCheck(
                "Disposition status", True, "No disposition history in last 180 days",
                "TaiwanStockDispositionSecuritiesPeriod"
            ))
    except Exception as e:  # noqa: BLE001
        _fail_closed(
            result,
            "Disposition status",
            f"Disposition check unavailable: {e}",
            "TaiwanStockDispositionSecuritiesPeriod",
        )

    try:
        susp = client.get("TaiwanStockSuspended", stock_id,
                          (today - timedelta(days=30)).strftime("%Y-%m-%d"))
        if not susp.empty:
            # If resumption_date in future or missing, treat as currently suspended
            if "resumption_date" in susp.columns:
                resumption = susp["resumption_date"].fillna("").astype(str).str.strip()
                active = susp[
                    (resumption == "") |
                    (resumption > today.strftime("%Y-%m-%d"))
                ]
            else:
                active = susp
            if not active.empty:
                result.checks.append(TriageCheck(
                    "Trading suspension", False,
                    "Currently suspended",
                    "TaiwanStockSuspended"
                ))
                result.passed = False
            else:
                result.checks.append(TriageCheck("Trading suspension", True, "Not currently suspended", "TaiwanStockSuspended"))
        else:
            result.checks.append(TriageCheck("Trading suspension", True, "No suspension record", "TaiwanStockSuspended"))
    except Exception as e:  # noqa: BLE001
        _fail_closed(
            result,
            "Trading suspension",
            f"Suspension check unavailable: {e}",
            "TaiwanStockSuspended",
        )

    # ──────────────────────────────────────────────
    # 2. Liquidity floor
    # ──────────────────────────────────────────────
    try:
        price_df = client.price(stock_id, price_start)
        adv = metrics.adv_ntd(price_df, lookback=cfg.adv_lookback_days)
        result.adv_ntd = adv.value
        if adv.value is None:
            result.checks.append(TriageCheck("Liquidity (ADV)", False, "Could not compute ADV", "TaiwanStockPrice"))
            result.passed = False
        elif adv.value < cfg.min_adv_ntd:
            result.checks.append(TriageCheck(
                "Liquidity (ADV)", False,
                f"ADV NT${adv.value:,.0f} < floor NT${cfg.min_adv_ntd:,.0f}",
                "TaiwanStockPrice"
            ))
            result.passed = False
        else:
            result.checks.append(TriageCheck(
                "Liquidity (ADV)", True,
                f"ADV NT${adv.value:,.0f} ≥ floor",
                "TaiwanStockPrice"
            ))

        # Position-size check if intended_position_ntd supplied
        if intended_position_ntd is not None and adv.value:
            pct = intended_position_ntd / adv.value
            if pct > cfg.position_max_pct_of_adv:
                result.checks.append(TriageCheck(
                    "Position vs ADV", False,
                    f"Intended position {pct*100:.1f}% of ADV > {cfg.position_max_pct_of_adv*100:.0f}%",
                    "TaiwanStockPrice"
                ))
                result.passed = False
            else:
                result.checks.append(TriageCheck(
                    "Position vs ADV", True,
                    f"Intended position {pct*100:.1f}% of ADV",
                    "TaiwanStockPrice"
                ))
    except Exception as e:  # noqa: BLE001
        result.notes.append(f"Liquidity check unavailable: {e}")
        result.checks.append(TriageCheck("Liquidity (ADV)", False, f"Error: {e}", "TaiwanStockPrice"))
        result.passed = False

    # ──────────────────────────────────────────────
    # 3. Financial statement staleness
    # ──────────────────────────────────────────────
    try:
        fs_df = client.financial_statements(stock_id, fs_start)
        inc = parsers.parse_income_statements(fs_df)
        if not inc:
            result.checks.append(TriageCheck(
                "Financials present", False, "No income statement data",
                "TaiwanStockFinancialStatements"
            ))
            result.passed = False
        else:
            latest_date = inc[-1].date
            # Approximate staleness check: compare to today
            latest_dt = datetime.strptime(latest_date[:10], "%Y-%m-%d")
            days_stale = (today - latest_dt).days
            if days_stale > 135:  # ~1 quarter + reporting lag
                result.checks.append(TriageCheck(
                    "Financials freshness", False,
                    f"Latest FS is {days_stale} days old (> 1 quarter + lag)",
                    "TaiwanStockFinancialStatements"
                ))
                result.passed = False
            else:
                result.checks.append(TriageCheck(
                    "Financials freshness", True,
                    f"Latest FS: {latest_date} ({days_stale} days ago)",
                    "TaiwanStockFinancialStatements"
                ))
    except Exception as e:  # noqa: BLE001
        _fail_closed(
            result,
            "Financials freshness",
            f"Financial-statement check unavailable: {e}",
            "TaiwanStockFinancialStatements",
        )

    # ──────────────────────────────────────────────
    # 4. Monthly revenue collapse
    # ──────────────────────────────────────────────
    try:
        rev_df = client.monthly_revenue(stock_id, rev_start)
        yoy = metrics.revenue_growth_yoy(rev_df)
        if yoy.value is None:
            result.checks.append(TriageCheck(
                "Monthly revenue trend", False, "Could not compute YoY",
                "TaiwanStockMonthRevenue"
            ))
            result.passed = False
        elif yoy.value < cfg.monthly_revenue_collapse_yoy * 100 and not short_thesis:
            result.checks.append(TriageCheck(
                "Monthly revenue trend", False,
                f"Latest YoY {yoy.value:.1f}% < collapse threshold {cfg.monthly_revenue_collapse_yoy*100:.0f}%",
                "TaiwanStockMonthRevenue"
            ))
            result.passed = False
        else:
            result.checks.append(TriageCheck(
                "Monthly revenue trend", True,
                f"Latest YoY {yoy.value:.1f}%",
                "TaiwanStockMonthRevenue"
            ))
    except Exception as e:  # noqa: BLE001
        _fail_closed(
            result,
            "Monthly revenue trend",
            f"Monthly revenue check unavailable: {e}",
            "TaiwanStockMonthRevenue",
        )

    # ──────────────────────────────────────────────
    # 5. Recent corporate-action distortion flag
    # ──────────────────────────────────────────────
    try:
        ca_start = (today - timedelta(days=cfg.corporate_action_lookback_months * 30)).strftime("%Y-%m-%d")
        cr_df = client.get("TaiwanStockCapitalReductionReferencePrice", stock_id, ca_start)
        distortions: list[str] = []
        if not cr_df.empty:
            distortions.append(f"{len(cr_df)} capital reduction(s)")
        # Note: split/par-value data does not support data_id filter for all variants;
        # we skip those here and leave them to Gate 3E.
        if distortions:
            result.checks.append(TriageCheck(
                "Corporate-action distortion", True,  # flag, not fail
                "Present: " + ", ".join(distortions) + " (use adjusted price for comparisons)",
                "TaiwanStockCapitalReductionReferencePrice"
            ))
            result.notes.append(f"Corporate actions detected in last {cfg.corporate_action_lookback_months} months: {distortions}")
        else:
            result.checks.append(TriageCheck(
                "Corporate-action distortion", True,
                f"None in last {cfg.corporate_action_lookback_months} months",
                "TaiwanStockCapitalReductionReferencePrice"
            ))
    except Exception as e:  # noqa: BLE001
        _fail_closed(
            result,
            "Corporate-action distortion",
            f"Corporate-action check unavailable: {e}",
            "TaiwanStockCapitalReductionReferencePrice",
        )

    return result
