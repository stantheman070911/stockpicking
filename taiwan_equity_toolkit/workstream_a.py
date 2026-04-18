"""
Workstream A — Industry / Macro backdrop (V2 Phase 3).

Absorbs ex-Gate 4 (peer validation) and ex-Gate 5 (value chain) into one
informational workstream. Never hard-fails a candidate: the worst a panel can
produce for its own `status` is `FAILED`, but the overall workstream rolls up
to `MANUAL_REVIEW_REQUIRED` / `NOT_ASSESSED` / `PASSED` for most real-world
inputs (per plan Phase 3.2 "status=FAILED is rare in Workstream A").

Design choices:
- Supply-chain lookup comes from `data/taiwan_supply_chain.yaml` (JSON-shape),
  parsed with stdlib `json.load`. If the stock is not in the YAML we fall back
  to grouping by `TaiwanStockInfo.industry_category` (free-tier).
- Never call premium-only industry-chain or business-indicator datasets in the
  default path.
- Macro backdrop uses four free-tier datasets only: `InterestRate(FED)`,
  `GovernmentBondsYield` (2Y + 10Y), `CrudeOilPrices(WTI)`,
  `TaiwanExchangeRate(USD)`.
- Missing data surfaces as `Status.NOT_ASSESSED`. Ambiguous signals
  (partial data) surface as `Status.MANUAL_REVIEW_REQUIRED`.

Public entry points:
    run(client, stock_id, context=None) -> WorkstreamAResult
    run_all(client_factory, stock_ids, max_workers=4) -> dict[str, WorkstreamAResult]
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

from taiwan_equity_toolkit.client import (
    FinMindError,
    PremiumDatasetRequired,
    RateLimitExceeded,
)
from taiwan_equity_toolkit.config import DEFAULT_CONFIG
from taiwan_equity_toolkit import metrics, parsers
from taiwan_equity_toolkit.states import Status

log = logging.getLogger(__name__)

_WORKSTREAM_A_CFG = DEFAULT_CONFIG.workstream_a
_MACRO_CFG = DEFAULT_CONFIG.macro


# ──────────────────────────────────────────────────────────────────────────
# Supply-chain YAML (JSON-shape; parsed with stdlib)
# ──────────────────────────────────────────────────────────────────────────

_SUPPLY_CHAIN_YAML_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "taiwan_supply_chain.yaml",
)

# Top-level metadata keys to skip when iterating cluster entries.
_NON_CLUSTER_KEYS: frozenset[str] = frozenset({"as_of", "source"})


def _load_supply_chain(path: str = _SUPPLY_CHAIN_YAML_PATH) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError) as exc:
        log.warning("Supply-chain YAML unavailable (%s); value-chain lookup will fall back", exc)
        return {}


def _locate_in_supply_chain(
    stock_id: str, chain_data: dict
) -> Optional[tuple[str, str]]:
    """Return (cluster_name, node_name) if the stock_id is listed, else None."""
    for cluster_name, cluster in chain_data.items():
        if cluster_name in _NON_CLUSTER_KEYS or not isinstance(cluster, dict):
            continue
        for node_name, members in cluster.items():
            if not isinstance(members, list):
                continue
            if stock_id in [str(m) for m in members]:
                return cluster_name, node_name
    return None


def _peers_for_node(
    cluster_name: str,
    node_name: str,
    chain_data: dict,
    direction: str,
) -> list[str]:
    """Expand upstream or downstream nodes for (cluster, node) into stock IDs.

    direction ∈ {"upstream", "downstream"}.
    """
    cluster = chain_data.get(cluster_name) or {}
    relations = cluster.get(direction) or {}
    neighbour_nodes = relations.get(node_name) or []
    member_ids: list[str] = []
    for n in neighbour_nodes:
        members = cluster.get(n) or []
        for m in members:
            sid = str(m)
            if sid and sid not in member_ids:
                member_ids.append(sid)
    return member_ids


# ──────────────────────────────────────────────────────────────────────────
# Panel dataclasses
# ──────────────────────────────────────────────────────────────────────────


@dataclass
class SectorTailwindPanel:
    status: Status = Status.NOT_ASSESSED
    candidate_yoy_3m: Optional[float] = None        # 3-month average revenue YoY %
    candidate_yoy_12m: Optional[float] = None       # most recent revenue YoY % (latest month)
    chain_cluster_avg_yoy: Optional[float] = None   # mean YoY % across candidate + chain peers
    peer_count: int = 0
    notes: list[str] = field(default_factory=list)


@dataclass
class ValueChainPositionPanel:
    status: Status = Status.NOT_ASSESSED
    cluster: Optional[str] = None
    node: Optional[str] = None
    upstream_peers: list[str] = field(default_factory=list)
    downstream_peers: list[str] = field(default_factory=list)
    source: str = ""  # "supply_chain_yaml" | "industry_category_fallback" | "none"
    notes: list[str] = field(default_factory=list)


@dataclass
class TsmcAnchorPanel:
    status: Status = Status.NOT_ASSESSED
    tsmc_revenue_yoy: Optional[float] = None
    as_of: Optional[str] = None
    notes: list[str] = field(default_factory=list)


@dataclass
class PeerAlignmentPanel:
    status: Status = Status.NOT_ASSESSED
    candidate: Optional[str] = None
    peer_ids: list[str] = field(default_factory=list)
    # Row dicts: {stock_id, revenue_yoy_pct, gross_margin_pct, inst_flow_60d}
    rows: list[dict] = field(default_factory=list)
    candidate_rank_revenue_yoy: Optional[tuple[int, int]] = None
    candidate_rank_gross_margin: Optional[tuple[int, int]] = None
    usable_peer_count: int = 0
    notes: list[str] = field(default_factory=list)


@dataclass
class MacroBackdropPanel:
    status: Status = Status.NOT_ASSESSED
    fed_rate_latest: Optional[float] = None
    ust_2y10y_spread: Optional[float] = None        # 10Y - 2Y
    wti_trend_pct: Optional[float] = None           # latest vs 180d-ago
    twd_trend_pct: Optional[float] = None           # latest vs 180d-ago
    notes: list[str] = field(default_factory=list)


@dataclass
class WorkstreamAResult:
    stock_id: str
    status: Status = Status.NOT_ASSESSED
    cluster: Optional[str] = None
    sector_signal: SectorTailwindPanel = field(default_factory=SectorTailwindPanel)
    chain_position: ValueChainPositionPanel = field(default_factory=ValueChainPositionPanel)
    tsmc_anchor: TsmcAnchorPanel = field(default_factory=TsmcAnchorPanel)
    peer_alignment: PeerAlignmentPanel = field(default_factory=PeerAlignmentPanel)
    macro_backdrop: MacroBackdropPanel = field(default_factory=MacroBackdropPanel)
    notes: list[str] = field(default_factory=list)


# ──────────────────────────────────────────────────────────────────────────
# Panel implementations
# ──────────────────────────────────────────────────────────────────────────


def value_chain_position_panel(client, stock_id: str) -> ValueChainPositionPanel:
    """Resolve the stock's cluster / node / chain-peer lists.

    Primary source: `data/taiwan_supply_chain.yaml`. Fallback: group by
    `TaiwanStockInfo.industry_category` (free tier). No call to any premium
    industry-chain dataset.
    """
    panel = ValueChainPositionPanel()
    chain_data = _load_supply_chain()
    located = _locate_in_supply_chain(stock_id, chain_data) if chain_data else None

    if located is not None:
        cluster_name, node_name = located
        panel.cluster = cluster_name
        panel.node = node_name
        panel.upstream_peers = _peers_for_node(cluster_name, node_name, chain_data, "upstream")
        # Remove the candidate itself in case node members overlap
        panel.upstream_peers = [p for p in panel.upstream_peers if p != stock_id]
        panel.downstream_peers = _peers_for_node(cluster_name, node_name, chain_data, "downstream")
        panel.downstream_peers = [p for p in panel.downstream_peers if p != stock_id]
        panel.source = "supply_chain_yaml"
        panel.status = Status.PASSED
        panel.notes.append(f"Located in YAML: cluster={cluster_name}, node={node_name}")
        return panel

    # Fallback — TaiwanStockInfo.industry_category
    try:
        info_df = client.stock_info()
    except Exception as exc:  # noqa: BLE001
        panel.status = Status.NOT_ASSESSED
        panel.source = "none"
        panel.notes.append(f"Stock-info fetch failed: {exc}")
        return panel

    if info_df is None or info_df.empty or "stock_id" not in info_df.columns:
        panel.status = Status.NOT_ASSESSED
        panel.source = "none"
        panel.notes.append("TaiwanStockInfo unavailable for fallback clustering")
        return panel

    stock_rows = info_df[info_df["stock_id"].astype(str) == str(stock_id)].copy()
    if stock_rows.empty:
        panel.status = Status.NOT_ASSESSED
        panel.source = "none"
        panel.notes.append(f"{stock_id} not found in TaiwanStockInfo")
        return panel

    if "industry_category" in stock_rows.columns:
        stock_rows["industry_category"] = (
            stock_rows["industry_category"].fillna("").astype(str).str.strip()
        )
    else:
        stock_rows["industry_category"] = ""
    if "type" in stock_rows.columns:
        stock_rows["type"] = stock_rows["type"].fillna("").astype(str).str.strip().str.lower()
    else:
        stock_rows["type"] = ""

    if len(stock_rows) > 1:
        panel.notes.append(
            "Multiple TaiwanStockInfo rows found; selected the first non-blank "
            "industry_category deterministically"
        )

    stock_rows = stock_rows.sort_values(
        by=["industry_category", "type"],
        ascending=[False, True],
        kind="stable",
    )
    category = str(stock_rows.iloc[0].get("industry_category", "")).strip()
    if not category:
        panel.status = Status.NOT_ASSESSED
        panel.source = "none"
        panel.notes.append("No industry_category on TaiwanStockInfo row")
        return panel

    # Peers = other stocks in the same category (excluding candidate).
    same_cat = info_df[info_df["industry_category"].astype(str).str.strip() == category]
    peers = [
        str(s) for s in same_cat["stock_id"].astype(str).tolist()
        if str(s) != str(stock_id)
    ]

    panel.cluster = category
    panel.node = None
    # Fallback has no directional info — expose the same category-peer list
    # under downstream_peers and spell that out in notes for analysts.
    panel.downstream_peers = peers
    panel.upstream_peers = []
    panel.source = "industry_category_fallback"
    panel.status = Status.PASSED
    panel.notes.append(
        f"Fallback via TaiwanStockInfo.industry_category='{category}' "
        f"({len(peers)} peer(s))"
    )
    panel.notes.append("Fallback peers are category peers only; directionality unavailable")
    return panel


def sector_tailwind_panel(
    client,
    stock_id: str,
    chain_peers: list[str],
    rev_start: str,
) -> SectorTailwindPanel:
    """Revenue YoY for candidate + up to 5 chain members.

    `candidate_yoy_12m` = revenue YoY on the latest monthly row.
    `candidate_yoy_3m` = mean YoY of the 3 most recent months (if ≥ 15 months
    of history). `chain_cluster_avg_yoy` = mean of latest-month YoY across
    candidate + cluster members that produced usable numbers.
    """
    panel = SectorTailwindPanel()

    # Candidate series first
    try:
        cand_df = client.monthly_revenue(stock_id, rev_start)
    except Exception as exc:  # noqa: BLE001
        panel.status = Status.NOT_ASSESSED
        panel.notes.append(f"Candidate monthly revenue fetch failed: {exc}")
        return panel

    cand_yoy_latest = metrics.revenue_growth_yoy(cand_df)
    panel.candidate_yoy_12m = cand_yoy_latest.value
    panel.candidate_yoy_3m = _avg_yoy_last_n_months(cand_df, n=3)

    cluster_yoys: list[float] = []
    if cand_yoy_latest.value is not None:
        cluster_yoys.append(cand_yoy_latest.value)

    # Peers — up to 5, via async batch
    peer_subset = [
        p for p in chain_peers if p != stock_id
    ][:_WORKSTREAM_A_CFG.sector_signal_peer_cap]
    panel.peer_count = 0
    if peer_subset:
        try:
            peer_map = client.get_multi("TaiwanStockMonthRevenue", peer_subset, rev_start)
        except Exception as exc:  # noqa: BLE001
            peer_map = {}
            panel.notes.append(f"Peer monthly revenue batch failed: {exc}")
        for sid, df in peer_map.items():
            m = metrics.revenue_growth_yoy(df)
            if m.value is not None:
                cluster_yoys.append(m.value)
                panel.peer_count += 1

    if cluster_yoys:
        panel.chain_cluster_avg_yoy = sum(cluster_yoys) / len(cluster_yoys)

    if panel.candidate_yoy_12m is None and panel.chain_cluster_avg_yoy is None:
        panel.status = Status.NOT_ASSESSED
        panel.notes.append("No usable YoY data for candidate or peers")
    else:
        panel.status = Status.PASSED
    return panel


def _avg_yoy_last_n_months(monthly_rev_df: pd.DataFrame, n: int = 3) -> Optional[float]:
    """Average YoY% over the last n months (requires n + 12 months of history)."""
    if monthly_rev_df is None or monthly_rev_df.empty:
        return None
    if "revenue" not in monthly_rev_df.columns or "date" not in monthly_rev_df.columns:
        return None
    df = monthly_rev_df.copy()
    df["_d"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["_d"]).sort_values("_d").reset_index(drop=True)
    if len(df) < 12 + n:
        return None
    values: list[float] = []
    for i in range(n):
        latest_idx = len(df) - 1 - i
        prior_idx = latest_idx - 12
        if prior_idx < 0:
            continue
        latest_rev = df.iloc[latest_idx]["revenue"]
        prior_rev = df.iloc[prior_idx]["revenue"]
        if not prior_rev or prior_rev == 0:
            continue
        values.append(float((latest_rev - prior_rev) / prior_rev * 100))
    if not values:
        return None
    return sum(values) / len(values)


def tsmc_anchor_signal(client, rev_start: str) -> TsmcAnchorPanel:
    """TSMC (2330) revenue YoY — one informational indicator for all stocks."""
    panel = TsmcAnchorPanel()
    try:
        df = client.monthly_revenue("2330", rev_start)
    except Exception as exc:  # noqa: BLE001
        panel.status = Status.NOT_ASSESSED
        panel.notes.append(f"TSMC monthly revenue fetch failed: {exc}")
        return panel

    m = metrics.revenue_growth_yoy(df)
    if m.value is None:
        panel.status = Status.NOT_ASSESSED
        panel.notes.append(f"TSMC YoY unavailable: {m.note or 'no data'}")
        return panel

    panel.tsmc_revenue_yoy = m.value
    panel.as_of = m.as_of
    panel.status = Status.PASSED
    return panel


def peer_alignment_panel(
    client,
    stock_id: str,
    chain_peers: list[str],
    rev_start: str,
    fs_start: str,
    flow_start: str,
) -> PeerAlignmentPanel:
    """Batch revenue / margin / flow for candidate + up to 6 chain members."""
    panel = PeerAlignmentPanel(candidate=stock_id)
    # Build the id set — candidate + peers, deduped, cap at 6 peers + candidate.
    peer_subset = [
        p for p in chain_peers if p != stock_id
    ][:_WORKSTREAM_A_CFG.peer_alignment_peer_cap]
    all_ids = [stock_id] + peer_subset
    panel.peer_ids = peer_subset

    if not peer_subset:
        panel.status = Status.NOT_ASSESSED
        panel.notes.append("No chain peers available for peer alignment")
        return panel

    try:
        rev_map = client.get_multi("TaiwanStockMonthRevenue", all_ids, rev_start)
    except Exception as exc:  # noqa: BLE001
        rev_map = {}
        panel.notes.append(f"Revenue batch failed: {exc}")

    try:
        fs_map = client.get_multi("TaiwanStockFinancialStatements", all_ids, fs_start)
    except Exception as exc:  # noqa: BLE001
        fs_map = {}
        panel.notes.append(f"Financial-statements batch failed: {exc}")

    try:
        flow_map = client.get_multi(
            "TaiwanStockInstitutionalInvestorsBuySell", all_ids, flow_start
        )
    except Exception as exc:  # noqa: BLE001
        flow_map = {}
        panel.notes.append(f"Institutional flow batch failed: {exc}")

    rows: list[dict] = []
    usable = 0
    for sid in all_ids:
        rev_m = metrics.revenue_growth_yoy(rev_map.get(sid, pd.DataFrame()))
        income = parsers.parse_income_statements(fs_map.get(sid, pd.DataFrame()))
        gm_m = metrics.gross_margin_latest(income)
        flow_m = metrics.institutional_net_flow(
            flow_map.get(sid, pd.DataFrame()), lookback_days=60
        )
        net_total: Optional[float] = None
        any_flow = False
        running = 0.0
        for m in flow_m.values():
            if m.value is not None:
                running += float(m.value)
                any_flow = True
        if any_flow:
            net_total = running

        row = {
            "stock_id": sid,
            "revenue_yoy_pct": rev_m.value,
            "gross_margin_pct": gm_m.value,
            "inst_flow_60d": net_total,
        }
        rows.append(row)
        if rev_m.value is not None or gm_m.value is not None or net_total is not None:
            usable += 1

    panel.rows = rows
    panel.usable_peer_count = usable
    panel.candidate_rank_revenue_yoy = _rank_candidate(rows, stock_id, "revenue_yoy_pct")
    panel.candidate_rank_gross_margin = _rank_candidate(rows, stock_id, "gross_margin_pct")

    # Status: PASSED if we got at least 2 rows of usable data (incl. candidate).
    if usable >= 2:
        panel.status = Status.PASSED
    elif usable == 1:
        panel.status = Status.MANUAL_REVIEW_REQUIRED
        panel.notes.append("Only one peer produced usable metrics — analyst review")
    else:
        panel.status = Status.NOT_ASSESSED
        panel.notes.append("No peer produced usable metrics")
    return panel


def _rank_candidate(
    rows: list[dict], candidate: str, metric_col: str
) -> Optional[tuple[int, int]]:
    """Return (rank, total) for candidate within rows sorted by metric_col desc.

    Higher is better. Returns None if candidate has no value or total < 2.
    """
    populated = [r for r in rows if r.get(metric_col) is not None]
    if len(populated) < 2:
        return None
    ordered = sorted(populated, key=lambda r: float(r[metric_col]), reverse=True)
    for idx, r in enumerate(ordered, start=1):
        if r["stock_id"] == candidate:
            return (idx, len(ordered))
    return None


def macro_backdrop_panel(client) -> MacroBackdropPanel:
    """Four free-tier macro indicators. Never FAILS — degrades to NOT_ASSESSED.

    Judgment call: when any single dataset fetch errors, that sub-metric
    becomes None and we append a note. If at least one metric populates we
    still return `PASSED`. If ALL four fail we downgrade to `NOT_ASSESSED`.
    `MANUAL_REVIEW_REQUIRED` is reserved for partial/ambiguous cases.
    """
    panel = MacroBackdropPanel()
    today = datetime.today()
    history_start = (today - timedelta(days=_WORKSTREAM_A_CFG.macro_history_days)).strftime(
        "%Y-%m-%d"
    )

    # Fed policy rate
    df = _macro_get(client, "InterestRate", "FED", history_start, panel)
    if df is not None:
        if not df.empty and "interest_rate" in df.columns:
            df = df.sort_values("date")
            panel.fed_rate_latest = float(df.iloc[-1]["interest_rate"])
        else:
            panel.notes.append("InterestRate(FED) returned empty")

    # UST 2Y / 10Y spread
    ust_2y = _latest_yield_value(client, "United States 2-Year", history_start, panel)
    ust_10y = _latest_yield_value(client, "United States 10-Year", history_start, panel)
    if ust_2y is not None and ust_10y is not None:
        panel.ust_2y10y_spread = ust_10y - ust_2y

    # WTI crude oil trend — latest vs 180d-ago
    df = _macro_get(client, "CrudeOilPrices", "WTI", history_start, panel)
    if df is not None:
        panel.wti_trend_pct = _trend_pct(df, "price", lookback_days=_MACRO_CFG.oil_lookback_days)
        if panel.wti_trend_pct is None:
            panel.notes.append("WTI trend unavailable (insufficient history)")

    # TWD trend — latest vs 180d-ago
    df = _macro_get(client, "TaiwanExchangeRate", "USD", history_start, panel)
    if df is not None:
        col = _pick_fx_col(df)
        if col is None:
            panel.notes.append("TaiwanExchangeRate(USD) has no usable spot column")
        else:
            panel.twd_trend_pct = _trend_pct(df, col, lookback_days=_MACRO_CFG.twd_lookback_days)
            if panel.twd_trend_pct is None:
                panel.notes.append("TWD trend unavailable (insufficient history)")

    populated = sum(
        1 for v in (panel.fed_rate_latest, panel.ust_2y10y_spread,
                    panel.wti_trend_pct, panel.twd_trend_pct)
        if v is not None
    )
    if populated == 4:
        panel.status = Status.PASSED
    elif populated == 0:
        panel.status = Status.NOT_ASSESSED
    else:
        # At least one missing → analyst should eyeball the remaining signals.
        panel.status = Status.MANUAL_REVIEW_REQUIRED

    return panel


def _latest_yield_value(
    client, data_id: str, start_date: str, panel: MacroBackdropPanel
) -> Optional[float]:
    df = _macro_get(client, "GovernmentBondsYield", data_id, start_date, panel)
    if df is None:
        return None
    if df is None or df.empty or "value" not in df.columns:
        panel.notes.append(f"GovernmentBondsYield({data_id}) returned empty")
        return None
    try:
        df_sorted = df.sort_values("date")
        return float(df_sorted.iloc[-1]["value"])
    except Exception as exc:  # noqa: BLE001
        panel.notes.append(f"GovernmentBondsYield({data_id}) parse failed: {exc}")
        return None


def _trend_pct(
    df: pd.DataFrame, value_col: str, lookback_days: int = 180
) -> Optional[float]:
    """Latest value vs `lookback_days`-ago value, as percent change."""
    if df is None or df.empty or value_col not in df.columns or "date" not in df.columns:
        return None
    try:
        df = df.copy()
        df["_d"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["_d"]).sort_values("_d").reset_index(drop=True)
        if df.empty:
            return None
        latest_dt = df["_d"].iloc[-1]
        cutoff = latest_dt - pd.Timedelta(days=lookback_days)
        older = df[df["_d"] <= cutoff]
        if older.empty:
            # fall back to the first row if history is shorter than lookback
            older = df.iloc[:1]
        old_val = float(older.iloc[-1][value_col])
        new_val = float(df.iloc[-1][value_col])
        if old_val == 0:
            return None
        return (new_val - old_val) / old_val * 100
    except Exception:  # noqa: BLE001
        return None


def _macro_get(
    client,
    dataset: str,
    data_id: str,
    start_date: str,
    panel: MacroBackdropPanel,
) -> Optional[pd.DataFrame]:
    """Fetch a free-tier macro dataset while surfacing programming mistakes.

    PremiumDatasetRequired should never happen in Workstream A because all
    datasets in the default path are explicitly free-tier. Re-raise it so
    a future regression is loud.
    """
    try:
        return client.get(dataset, data_id, start_date)
    except PremiumDatasetRequired:
        raise
    except (RateLimitExceeded, FinMindError, RuntimeError) as exc:
        panel.notes.append(f"{dataset}({data_id}) fetch failed: {exc}")
        return None


def _pick_fx_col(df: pd.DataFrame) -> Optional[str]:
    if df is None or df.empty:
        return None
    for col in ("spot_buy", "spot_sell", "cash_buy", "cash_sell"):
        if col in df.columns:
            return col
    return None


# ──────────────────────────────────────────────────────────────────────────
# Public entry points
# ──────────────────────────────────────────────────────────────────────────


def run(
    client,
    stock_id: str,
    context: Optional[dict] = None,
) -> WorkstreamAResult:
    """Run all Workstream A panels for a single stock.

    `context` is reserved for future use (analyst overlays, existing book).
    """
    result = WorkstreamAResult(stock_id=stock_id)
    today = datetime.today()
    rev_start = (today - timedelta(days=730)).strftime("%Y-%m-%d")
    fs_start = (today - timedelta(days=540)).strftime("%Y-%m-%d")
    flow_start = (today - timedelta(days=120)).strftime("%Y-%m-%d")

    # Panel 1 — chain position first; gives us the peer list for others.
    result.chain_position = _safe_panel(
        stock_id,
        "chain_position",
        lambda: value_chain_position_panel(client, stock_id),
        lambda note: ValueChainPositionPanel(
            status=Status.MANUAL_REVIEW_REQUIRED,
            source="none",
            notes=[note],
        ),
    )
    result.cluster = result.chain_position.cluster
    chain_peers = list(
        dict.fromkeys(
            result.chain_position.upstream_peers
            + result.chain_position.downstream_peers
        )
    )

    # Panel 2 — sector tailwind (candidate + chain peers).
    result.sector_signal = _safe_panel(
        stock_id,
        "sector_signal",
        lambda: sector_tailwind_panel(client, stock_id, chain_peers, rev_start),
        lambda note: SectorTailwindPanel(
            status=Status.MANUAL_REVIEW_REQUIRED,
            notes=[note],
        ),
    )

    # Panel 3 — TSMC anchor (always runs).
    result.tsmc_anchor = _safe_panel(
        stock_id,
        "tsmc_anchor",
        lambda: tsmc_anchor_signal(client, rev_start),
        lambda note: TsmcAnchorPanel(
            status=Status.MANUAL_REVIEW_REQUIRED,
            notes=[note],
        ),
    )

    # Panel 4 — peer alignment (async batch).
    result.peer_alignment = _safe_panel(
        stock_id,
        "peer_alignment",
        lambda: peer_alignment_panel(client, stock_id, chain_peers, rev_start, fs_start, flow_start),
        lambda note: PeerAlignmentPanel(
            status=Status.MANUAL_REVIEW_REQUIRED,
            candidate=stock_id,
            peer_ids=list(chain_peers[:_WORKSTREAM_A_CFG.peer_alignment_peer_cap]),
            notes=[note],
        ),
    )

    # Panel 5 — macro backdrop.
    result.macro_backdrop = _safe_panel(
        stock_id,
        "macro_backdrop",
        lambda: macro_backdrop_panel(client),
        lambda note: MacroBackdropPanel(
            status=Status.MANUAL_REVIEW_REQUIRED,
            notes=[note],
        ),
    )

    result.status = _rollup_status(result)

    # Gather notes from panels for convenience (trimmed).
    for panel in (result.sector_signal, result.chain_position, result.tsmc_anchor,
                  result.peer_alignment, result.macro_backdrop):
        for note in panel.notes:
            if note:
                result.notes.append(note)

    return result


def _safe_panel(stock_id: str, panel_name: str, factory, fallback_factory):
    try:
        return factory()
    except PremiumDatasetRequired:
        raise
    except Exception as exc:  # noqa: BLE001
        log.warning("Workstream A panel %s crashed for %s: %s", panel_name, stock_id, exc)
        return fallback_factory(f"{panel_name} raised unexpectedly: {exc}")


def _rollup_status(result: WorkstreamAResult) -> Status:
    panel_statuses = [
        result.sector_signal.status,
        result.chain_position.status,
        result.tsmc_anchor.status,
        result.peer_alignment.status,
        result.macro_backdrop.status,
    ]
    if any(status == Status.FAILED for status in panel_statuses):
        return Status.FAILED
    if any(status == Status.MANUAL_REVIEW_REQUIRED for status in panel_statuses):
        return Status.MANUAL_REVIEW_REQUIRED

    # Phase 3 plan: PASS requires core context to resolve. Auxiliary panels
    # (TSMC anchor, peer alignment) are informational and may be not_assessed
    # without blocking a PASS.
    core_statuses = [
        result.sector_signal.status,
        result.chain_position.status,
        result.macro_backdrop.status,
    ]
    if all(status == Status.PASSED for status in core_statuses):
        return Status.PASSED
    return Status.MANUAL_REVIEW_REQUIRED


def run_all(
    client_factory: Callable[[], object],
    stock_ids: list[str],
    max_workers: int = 4,
) -> dict[str, WorkstreamAResult]:
    """Run Workstream A across a universe in parallel.

    Mirrors `mass_triage.run_all` — one client per worker via `client_factory`.
    """
    results: dict[str, WorkstreamAResult] = {}

    def _work(stock_id: str) -> tuple[str, WorkstreamAResult]:
        client = client_factory()
        return stock_id, run(client, stock_id)

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_work, sid): sid for sid in stock_ids}
        for fut in as_completed(futures):
            sid = futures[fut]
            try:
                stock_id, res = fut.result()
                results[stock_id] = res
            except Exception as exc:  # noqa: BLE001
                log.warning("Workstream A worker failed for %s: %s", sid, exc)
                results[sid] = WorkstreamAResult(
                    stock_id=sid,
                    status=Status.NOT_ASSESSED,
                    notes=[f"Worker raised: {exc}"],
                )

    return results
