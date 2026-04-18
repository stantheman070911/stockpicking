"""
Mass Triage — V2 compressed quick-disqualify (8 merged checks).

Replaces legacy ``triage.py`` per plan Phase 2 / report §7.6. The 17-item
sequential quick-disqualify collapses to 8 merged buckets that run entirely on
free-tier FinMind data. Premium-dependent sub-checks (Disposition, Suspension)
do not hard-fail the stock — they surface as ``Status.NOT_ASSESSED`` with a
note so downstream consumers know data was unavailable, not that the check
passed.

Public API:
    run(client, stock_id, ...)            -> MassTriageResult
    run_all(client_factory, stock_ids, ...) -> dict[str, MassTriageResult]

Overall verdict rule (plan Phase 2.2, last bullet):
    - Overall status is FAILED iff at least one individual check is FAILED.
    - NOT_ASSESSED on a sub-check never forces overall FAIL.
    - MANUAL_REVIEW_REQUIRED on a sub-check propagates up but doesn't fail.
"""

from __future__ import annotations

import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable, Optional

import pandas as pd

from taiwan_equity_toolkit import metrics, parsers
from taiwan_equity_toolkit.client import FinMindClient, PremiumDatasetRequired
from taiwan_equity_toolkit.config import DEFAULT_CONFIG, TriageConfig
from taiwan_equity_toolkit.states import Status

log = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────
# Governance red-flag keyword list (loaded from curated YAML)
# ──────────────────────────────────────────────────────────────────────────

_GOVERNANCE_YAML_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "taiwan_governance_redflags.yaml",
)


def _load_governance_patterns(
    severities: tuple[str, ...] = ("critical",),
    path: str = _GOVERNANCE_YAML_PATH,
) -> list[str]:
    """Load keyword list for the mass-triage governance scan.

    The mass-triage check is the cheapest screen — we only pick up
    ``critical`` severity patterns (embezzlement, insider trading, fraud).
    Broader 'high' / 'medium' patterns are handled in Workstream B's red-flag
    screen (plan Phase 5). YAML file is JSON-compatible so we parse with the
    stdlib to avoid a PyYAML dependency.
    """
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, ValueError) as exc:
        log.warning("Governance red-flag YAML unavailable (%s); mass-triage governance scan will be skipped", exc)
        return []

    keywords: list[str] = []
    for pattern in payload.get("patterns", []):
        if pattern.get("severity") in severities:
            for kw in pattern.get("keywords", []):
                text = str(kw).strip()
                if text:
                    keywords.append(text)
    return keywords


# ──────────────────────────────────────────────────────────────────────────
# Result dataclasses
# ──────────────────────────────────────────────────────────────────────────


@dataclass
class TriageCheck:
    name: str
    status: Status
    detail: str
    source: str = ""


@dataclass
class MassTriageResult:
    stock_id: str
    status: Status = Status.PASSED
    checks: list[TriageCheck] = field(default_factory=list)
    adv_ntd: Optional[float] = None
    notes: list[str] = field(default_factory=list)

    def failures(self) -> list[TriageCheck]:
        return [c for c in self.checks if c.status == Status.FAILED]

    def not_assessed(self) -> list[TriageCheck]:
        return [c for c in self.checks if c.status == Status.NOT_ASSESSED]

    def summary(self) -> str:
        marks = {
            Status.PASSED: "✓",
            Status.FAILED: "✗",
            Status.NOT_ASSESSED: "~",
            Status.MANUAL_REVIEW_REQUIRED: "?",
        }
        lines = [f"Mass-triage verdict: {self.status.value.upper()} ({self.stock_id})"]
        for check in self.checks:
            lines.append(f"  {marks[check.status]} {check.name}: {check.detail}")
        return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────
# Check helpers — every check appends a TriageCheck and returns its status
# ──────────────────────────────────────────────────────────────────────────


def _append(result: MassTriageResult, check: TriageCheck) -> None:
    result.checks.append(check)
    if check.status == Status.FAILED:
        result.notes.append(check.detail)


def _run_check_1_tradability(
    result: MassTriageResult,
    client: FinMindClient,
    stock_id: str,
    cfg: TriageConfig,
    intended_position_ntd: Optional[float],
    price_start: str,
) -> None:
    """Liquidity ADV floor + position-vs-ADV cap."""
    try:
        price_df = client.price(stock_id, price_start)
    except Exception as exc:  # noqa: BLE001
        _append(result, TriageCheck(
            "Tradability (ADV)",
            Status.FAILED,
            f"Price fetch failed: {exc}",
            "TaiwanStockPrice",
        ))
        return

    adv = metrics.adv_ntd(price_df, lookback=cfg.adv_lookback_days)
    result.adv_ntd = adv.value

    if adv.value is None:
        _append(result, TriageCheck(
            "Tradability (ADV)",
            Status.FAILED,
            "Could not compute ADV (no Trading_money)",
            "TaiwanStockPrice",
        ))
        return

    if adv.value < cfg.min_adv_ntd:
        _append(result, TriageCheck(
            "Tradability (ADV)",
            Status.FAILED,
            f"ADV NT${adv.value:,.0f} < floor NT${cfg.min_adv_ntd:,.0f}",
            "TaiwanStockPrice",
        ))
        return

    _append(result, TriageCheck(
        "Tradability (ADV)",
        Status.PASSED,
        f"ADV NT${adv.value:,.0f} ≥ floor",
        "TaiwanStockPrice",
    ))

    if intended_position_ntd is not None and adv.value:
        pct = intended_position_ntd / adv.value
        if pct > cfg.position_max_pct_of_adv:
            _append(result, TriageCheck(
                "Single-name exposure (Position / ADV)",
                Status.FAILED,
                f"Intended {pct*100:.1f}% of ADV > {cfg.position_max_pct_of_adv*100:.0f}% cap",
                "TaiwanStockPrice",
            ))
        else:
            _append(result, TriageCheck(
                "Single-name exposure (Position / ADV)",
                Status.PASSED,
                f"Intended {pct*100:.1f}% of ADV ≤ {cfg.position_max_pct_of_adv*100:.0f}% cap",
                "TaiwanStockPrice",
            ))


def _run_check_2_active_trading(
    result: MassTriageResult,
    client: FinMindClient,
    stock_id: str,
    today: datetime,
) -> None:
    """Not-delisted + not-on-disposition.

    Delisting is free-tier (hard fail); disposition/suspension are premium →
    NOT_ASSESSED. Per plan Phase 2.2 #2, premium gaps never fail overall.
    """
    # Delisting (free tier)
    try:
        delist_df = client.get(
            "TaiwanStockDelisting",
            stock_id,
            (today - timedelta(days=365)).strftime("%Y-%m-%d"),
        )
    except Exception as exc:  # noqa: BLE001
        _append(result, TriageCheck(
            "Active trading (delisting)",
            Status.FAILED,
            f"Delisting fetch failed: {exc}",
            "TaiwanStockDelisting",
        ))
    else:
        if not delist_df.empty:
            _append(result, TriageCheck(
                "Active trading (delisting)",
                Status.FAILED,
                f"Delisting record present ({len(delist_df)} row(s))",
                "TaiwanStockDelisting",
            ))
        else:
            _append(result, TriageCheck(
                "Active trading (delisting)",
                Status.PASSED,
                "No delisting record in last 365 days",
                "TaiwanStockDelisting",
            ))

    # Disposition (premium)
    try:
        disp_df = client.get(
            "TaiwanStockDispositionSecuritiesPeriod",
            stock_id,
            (today - timedelta(days=180)).strftime("%Y-%m-%d"),
        )
    except PremiumDatasetRequired as exc:
        _append(result, TriageCheck(
            "Active trading (disposition)",
            Status.NOT_ASSESSED,
            f"Disposition dataset is premium: {exc}",
            "TaiwanStockDispositionSecuritiesPeriod",
        ))
    except Exception as exc:  # noqa: BLE001
        _append(result, TriageCheck(
            "Active trading (disposition)",
            Status.NOT_ASSESSED,
            f"Disposition fetch failed: {exc}",
            "TaiwanStockDispositionSecuritiesPeriod",
        ))
    else:
        if disp_df.empty:
            _append(result, TriageCheck(
                "Active trading (disposition)",
                Status.PASSED,
                "No disposition record in last 180 days",
                "TaiwanStockDispositionSecuritiesPeriod",
            ))
        elif "period_start" in disp_df.columns and "period_end" in disp_df.columns:
            today_str = today.strftime("%Y-%m-%d")
            active = disp_df[
                (disp_df["period_start"] <= today_str)
                & (disp_df["period_end"] >= today_str)
            ]
            if not active.empty:
                _append(result, TriageCheck(
                    "Active trading (disposition)",
                    Status.FAILED,
                    f"On disposition list: {len(active)} active window(s)",
                    "TaiwanStockDispositionSecuritiesPeriod",
                ))
            else:
                _append(result, TriageCheck(
                    "Active trading (disposition)",
                    Status.PASSED,
                    "No active disposition window today",
                    "TaiwanStockDispositionSecuritiesPeriod",
                ))
        else:
            _append(result, TriageCheck(
                "Active trading (disposition)",
                Status.PASSED,
                "Disposition rows present but no active-window columns",
                "TaiwanStockDispositionSecuritiesPeriod",
            ))

    # Suspension (premium)
    try:
        susp_df = client.get(
            "TaiwanStockSuspended",
            stock_id,
            (today - timedelta(days=30)).strftime("%Y-%m-%d"),
        )
    except PremiumDatasetRequired as exc:
        _append(result, TriageCheck(
            "Active trading (suspension)",
            Status.NOT_ASSESSED,
            f"Suspension dataset is premium: {exc}",
            "TaiwanStockSuspended",
        ))
    except Exception as exc:  # noqa: BLE001
        _append(result, TriageCheck(
            "Active trading (suspension)",
            Status.NOT_ASSESSED,
            f"Suspension fetch failed: {exc}",
            "TaiwanStockSuspended",
        ))
    else:
        if susp_df.empty:
            _append(result, TriageCheck(
                "Active trading (suspension)",
                Status.PASSED,
                "No suspension record in last 30 days",
                "TaiwanStockSuspended",
            ))
        else:
            today_str = today.strftime("%Y-%m-%d")
            if "resumption_date" in susp_df.columns:
                resumption = susp_df["resumption_date"].fillna("").astype(str).str.strip()
                active = susp_df[(resumption == "") | (resumption > today_str)]
            else:
                active = susp_df
            if not active.empty:
                _append(result, TriageCheck(
                    "Active trading (suspension)",
                    Status.FAILED,
                    "Currently suspended",
                    "TaiwanStockSuspended",
                ))
            else:
                _append(result, TriageCheck(
                    "Active trading (suspension)",
                    Status.PASSED,
                    "No active suspension",
                    "TaiwanStockSuspended",
                ))


def _run_check_3_survival_risk(
    result: MassTriageResult,
    client: FinMindClient,
    stock_id: str,
    cfg: TriageConfig,
    rev_start: str,
    short_thesis: bool,
) -> None:
    """Monthly revenue YoY above collapse threshold (unless shorting)."""
    try:
        rev_df = client.monthly_revenue(stock_id, rev_start)
    except Exception as exc:  # noqa: BLE001
        _append(result, TriageCheck(
            "Survival risk (monthly revenue)",
            Status.FAILED,
            f"Monthly revenue fetch failed: {exc}",
            "TaiwanStockMonthRevenue",
        ))
        return

    yoy = metrics.revenue_growth_yoy(rev_df)
    if yoy.value is None:
        _append(result, TriageCheck(
            "Survival risk (monthly revenue)",
            Status.FAILED,
            f"Could not compute YoY ({yoy.note or 'no data'})",
            "TaiwanStockMonthRevenue",
        ))
        return

    threshold_pct = cfg.monthly_revenue_collapse_yoy * 100
    if yoy.value < threshold_pct and not short_thesis:
        _append(result, TriageCheck(
            "Survival risk (monthly revenue)",
            Status.FAILED,
            f"Latest YoY {yoy.value:.1f}% < collapse threshold {threshold_pct:.0f}%",
            "TaiwanStockMonthRevenue",
        ))
    else:
        short_note = " (short thesis — rule relaxed)" if short_thesis and yoy.value < threshold_pct else ""
        _append(result, TriageCheck(
            "Survival risk (monthly revenue)",
            Status.PASSED,
            f"Latest YoY {yoy.value:.1f}%{short_note}",
            "TaiwanStockMonthRevenue",
        ))


def _run_check_4_data_freshness(
    result: MassTriageResult,
    client: FinMindClient,
    stock_id: str,
    fs_start: str,
    today: datetime,
) -> None:
    """Latest financial statement ≤ 135 days old."""
    try:
        fs_df = client.financial_statements(stock_id, fs_start)
    except Exception as exc:  # noqa: BLE001
        _append(result, TriageCheck(
            "Data freshness (financials)",
            Status.FAILED,
            f"Financial-statements fetch failed: {exc}",
            "TaiwanStockFinancialStatements",
        ))
        return

    inc = parsers.parse_income_statements(fs_df)
    if not inc:
        _append(result, TriageCheck(
            "Data freshness (financials)",
            Status.FAILED,
            "No income-statement rows parsed",
            "TaiwanStockFinancialStatements",
        ))
        return

    latest_date = inc[-1].date
    try:
        latest_dt = datetime.strptime(latest_date[:10], "%Y-%m-%d")
    except (TypeError, ValueError):
        _append(result, TriageCheck(
            "Data freshness (financials)",
            Status.FAILED,
            f"Unparseable latest date: {latest_date!r}",
            "TaiwanStockFinancialStatements",
        ))
        return

    days_stale = (today - latest_dt).days
    if days_stale > 135:
        _append(result, TriageCheck(
            "Data freshness (financials)",
            Status.FAILED,
            f"Latest FS {latest_date} is {days_stale} days old (> 135)",
            "TaiwanStockFinancialStatements",
        ))
    else:
        _append(result, TriageCheck(
            "Data freshness (financials)",
            Status.PASSED,
            f"Latest FS {latest_date} ({days_stale} days ago)",
            "TaiwanStockFinancialStatements",
        ))


def _run_check_5_corporate_actions(
    result: MassTriageResult,
    client: FinMindClient,
    stock_id: str,
    cfg: TriageConfig,
) -> None:
    """Flag unexplained capital reductions / par-value changes / splits.

    All three datasets are free-tier. Presence of events does NOT hard-fail —
    it annotates. Per plan Phase 2.2 #5, the check reports compound frequency
    and only fails when the data source itself is broken.
    """
    today = datetime.today()
    lookback_start = (today - timedelta(days=cfg.corporate_action_lookback_months * 30)).strftime("%Y-%m-%d")
    sub_statuses: list[Status] = []
    distortions: list[str] = []

    # Capital reduction (free)
    try:
        cr_df = client.get("TaiwanStockCapitalReductionReferencePrice", stock_id, lookback_start)
        if not cr_df.empty:
            distortions.append(f"{len(cr_df)} capital reduction(s)")
        sub_statuses.append(Status.PASSED)
    except Exception as exc:  # noqa: BLE001
        _append(result, TriageCheck(
            "Corporate-action cleanliness (capital reduction)",
            Status.FAILED,
            f"Capital-reduction fetch failed: {exc}",
            "TaiwanStockCapitalReductionReferencePrice",
        ))
        return

    # Par-value change (free; dataset returns list even without data_id)
    try:
        pv_df = client.get("TaiwanStockParValueChange", stock_id, lookback_start)
        if not pv_df.empty:
            distortions.append(f"{len(pv_df)} par-value change(s)")
    except Exception as exc:  # noqa: BLE001
        log.debug("Par-value fetch failed for %s: %s", stock_id, exc)

    # Stock split (free)
    try:
        sp_df = client.get("TaiwanStockSplitPrice", stock_id, lookback_start)
        if not sp_df.empty:
            distortions.append(f"{len(sp_df)} split(s)")
    except Exception as exc:  # noqa: BLE001
        log.debug("Split fetch failed for %s: %s", stock_id, exc)

    detail = (
        "Present: " + ", ".join(distortions) + " — use adjusted prices"
        if distortions
        else f"None in last {cfg.corporate_action_lookback_months} months"
    )
    _append(result, TriageCheck(
        "Corporate-action cleanliness",
        Status.PASSED,
        detail,
        "TaiwanStockCapitalReductionReferencePrice + ParValueChange + SplitPrice",
    ))
    if distortions:
        result.notes.append(f"Corporate actions detected: {distortions}")


def _run_check_6_governance(
    result: MassTriageResult,
    client: FinMindClient,
    stock_id: str,
    today: datetime,
    critical_keywords: list[str],
) -> None:
    """News keyword scan against critical governance patterns."""
    if not critical_keywords:
        _append(result, TriageCheck(
            "Governance red-flag scan",
            Status.NOT_ASSESSED,
            "Governance keyword list unavailable",
            "data/taiwan_governance_redflags.yaml",
        ))
        return

    start = (today - timedelta(days=365)).strftime("%Y-%m-%d")
    try:
        news_df = client.news(stock_id, start)
    except Exception as exc:  # noqa: BLE001
        _append(result, TriageCheck(
            "Governance red-flag scan",
            Status.NOT_ASSESSED,
            f"News fetch failed: {exc}",
            "TaiwanStockNews",
        ))
        return

    if news_df.empty:
        _append(result, TriageCheck(
            "Governance red-flag scan",
            Status.PASSED,
            "No news in last 12 months",
            "TaiwanStockNews",
        ))
        return

    text_cols = [c for c in ("title", "description", "content") if c in news_df.columns]
    if not text_cols:
        _append(result, TriageCheck(
            "Governance red-flag scan",
            Status.NOT_ASSESSED,
            f"News has no text columns (got {list(news_df.columns)})",
            "TaiwanStockNews",
        ))
        return

    combined = news_df[text_cols].fillna("").astype(str).agg(" ".join, axis=1).str.lower()
    hits: list[str] = []
    for kw in critical_keywords:
        needle = kw.lower()
        if combined.str.contains(needle, regex=False, na=False).any():
            hits.append(kw)

    if hits:
        _append(result, TriageCheck(
            "Governance red-flag scan",
            Status.FAILED,
            "Critical governance keyword(s) in news: " + ", ".join(hits),
            "TaiwanStockNews + data/taiwan_governance_redflags.yaml",
        ))
    else:
        _append(result, TriageCheck(
            "Governance red-flag scan",
            Status.PASSED,
            f"No critical keywords across {len(news_df)} articles",
            "TaiwanStockNews + data/taiwan_governance_redflags.yaml",
        ))


def _run_check_7_business_parse(
    result: MassTriageResult,
    client: FinMindClient,
    stock_id: str,
) -> None:
    """Sanity-check: stock_id resolves to a tradable equity, not a warrant/ETF."""
    try:
        info_df = client.stock_info()
    except Exception as exc:  # noqa: BLE001
        _append(result, TriageCheck(
            "Business parse (TaiwanStockInfo)",
            Status.NOT_ASSESSED,
            f"Stock-info fetch failed: {exc}",
            "TaiwanStockInfo",
        ))
        return

    if info_df.empty or "stock_id" not in info_df.columns:
        _append(result, TriageCheck(
            "Business parse (TaiwanStockInfo)",
            Status.NOT_ASSESSED,
            "Stock-info table empty or missing stock_id",
            "TaiwanStockInfo",
        ))
        return

    row = info_df[info_df["stock_id"].astype(str) == stock_id]
    if row.empty:
        _append(result, TriageCheck(
            "Business parse (TaiwanStockInfo)",
            Status.FAILED,
            f"{stock_id} not present in TaiwanStockInfo",
            "TaiwanStockInfo",
        ))
        return

    category = str(row.iloc[0].get("industry_category", "")).strip()
    stock_type = str(row.iloc[0].get("type", "")).strip().lower()

    # Known non-equity instrument markers.
    disallowed = ("權證", "warrant", "etf", "etn", "受益", "基金")
    lowered_cat = category.lower()
    if any(d in category or d in lowered_cat for d in disallowed):
        _append(result, TriageCheck(
            "Business parse (TaiwanStockInfo)",
            Status.FAILED,
            f"Non-equity instrument: category='{category}'",
            "TaiwanStockInfo",
        ))
        return

    if stock_type and stock_type not in ("twse", "tpex", "otc", ""):
        _append(result, TriageCheck(
            "Business parse (TaiwanStockInfo)",
            Status.FAILED,
            f"Unexpected type='{stock_type}' (category='{category}')",
            "TaiwanStockInfo",
        ))
        return

    _append(result, TriageCheck(
        "Business parse (TaiwanStockInfo)",
        Status.PASSED,
        f"Tradable equity — category='{category or 'unspecified'}'",
        "TaiwanStockInfo",
    ))


# ──────────────────────────────────────────────────────────────────────────
# Public entry points
# ──────────────────────────────────────────────────────────────────────────


def run(
    client: FinMindClient,
    stock_id: str,
    cfg: Optional[TriageConfig] = None,
    intended_position_ntd: Optional[float] = None,
    short_thesis: bool = False,
    *,
    governance_keywords: Optional[list[str]] = None,
) -> MassTriageResult:
    """Run the 8-check mass triage on a single stock.

    Args:
        client: authenticated FinMindClient (free-tier safe).
        stock_id: 4-digit TW stock code.
        cfg: TriageConfig override.
        intended_position_ntd: if provided, runs check 8 (position / ADV).
        short_thesis: relax monthly-revenue-collapse rule if shorting.
        governance_keywords: explicit critical-keyword list (test injection).
            Defaults to loading from data/taiwan_governance_redflags.yaml.
    """
    cfg = cfg or DEFAULT_CONFIG.triage
    today = datetime.today()
    price_start = (today - timedelta(days=60)).strftime("%Y-%m-%d")
    rev_start = (today - timedelta(days=730)).strftime("%Y-%m-%d")
    fs_start = (today - timedelta(days=540)).strftime("%Y-%m-%d")
    keywords = governance_keywords if governance_keywords is not None else _load_governance_patterns()

    result = MassTriageResult(stock_id=stock_id, status=Status.PASSED)

    _run_check_1_tradability(result, client, stock_id, cfg, intended_position_ntd, price_start)
    _run_check_2_active_trading(result, client, stock_id, today)
    _run_check_3_survival_risk(result, client, stock_id, cfg, rev_start, short_thesis)
    _run_check_4_data_freshness(result, client, stock_id, fs_start, today)
    _run_check_5_corporate_actions(result, client, stock_id, cfg)
    _run_check_6_governance(result, client, stock_id, today, keywords)
    _run_check_7_business_parse(result, client, stock_id)
    # Check 8 (single-name exposure) is folded into check 1 when
    # intended_position_ntd is provided — avoids double-fetching price data.

    # Overall status: FAILED iff any individual check FAILED (plan Phase 2.2).
    # NOT_ASSESSED on a premium sub-check is informational — the stock is still
    # tradable, we just have fewer signals. MANUAL_REVIEW_REQUIRED propagates
    # up so downstream consumers prompt the analyst.
    if any(c.status == Status.FAILED for c in result.checks):
        result.status = Status.FAILED
    elif any(c.status == Status.MANUAL_REVIEW_REQUIRED for c in result.checks):
        result.status = Status.MANUAL_REVIEW_REQUIRED
    else:
        result.status = Status.PASSED

    return result


def run_all(
    client_factory: Callable[[], FinMindClient],
    stock_ids: list[str],
    cfg: Optional[TriageConfig] = None,
    intended_position_ntd: Optional[float] = None,
    short_thesis: bool = False,
    max_workers: int = 8,
) -> dict[str, MassTriageResult]:
    """Run mass triage across a universe of stocks, in parallel.

    ``client_factory`` builds one FinMindClient per worker thread — each
    underlying ``requests.Session`` would otherwise not be safe to share across
    threads. Callers typically wrap a shared token + policy in the factory.
    """
    keywords = _load_governance_patterns()
    results: dict[str, MassTriageResult] = {}

    def _work(stock_id: str) -> tuple[str, MassTriageResult]:
        client = client_factory()
        return stock_id, run(
            client,
            stock_id,
            cfg=cfg,
            intended_position_ntd=intended_position_ntd,
            short_thesis=short_thesis,
            governance_keywords=keywords,
        )

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_work, sid): sid for sid in stock_ids}
        for fut in as_completed(futures):
            sid = futures[fut]
            try:
                stock_id, res = fut.result()
                results[stock_id] = res
            except Exception as exc:  # noqa: BLE001
                log.warning("Mass-triage worker failed for %s: %s", sid, exc)
                results[sid] = MassTriageResult(
                    stock_id=sid,
                    status=Status.FAILED,
                    notes=[f"Worker raised: {exc}"],
                )

    return results
