"""
Workstream A — Industry / Macro.

Free-tier default path:
- proxy-map + industry-category peer context
- peer echo from monthly revenue, financials, and institutional flow
- FX / rates backdrop notes
- business-indicator timing explicitly downgraded to not_assessed
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import pandas as pd

from taiwan_equity_toolkit import peers
from taiwan_equity_toolkit.client import FinMindClient
from taiwan_equity_toolkit.data_policy import (
    DatasetTier,
    aggregate_status,
    calculate_score,
    removed_signal_entries,
)
from taiwan_equity_toolkit.models import (
    AssessmentStatus,
    CheckResult,
    ManualRequirement,
    StrategyMode,
    WorkstreamResult,
)


PROXY_MAP_PATH = Path(__file__).resolve().parent.parent / "data" / "value_chain_proxy.json"


def load_proxy_map() -> dict:
    with open(PROXY_MAP_PATH, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _group_for_stock(proxy_map: dict, stock_id: str) -> tuple[Optional[str], Optional[dict]]:
    for group_name, payload in proxy_map.get("groups", {}).items():
        if stock_id in payload.get("stock_ids", []):
            return group_name, payload
    return None, None


def _row_for_stock(stock_info_df: pd.DataFrame, stock_id: str) -> Optional[pd.Series]:
    if stock_info_df.empty:
        return None
    mine = stock_info_df[stock_info_df["stock_id"].astype(str) == str(stock_id)]
    if mine.empty:
        return None
    return mine.iloc[-1]


def resolve_peer_context(
    client: FinMindClient,
    stock_id: str,
    stock_info_df: Optional[pd.DataFrame] = None,
    max_peers: int = 4,
) -> dict:
    proxy_map = load_proxy_map()
    if stock_info_df is None:
        try:
            stock_info_df = client.stock_info()
        except Exception:  # noqa: BLE001
            stock_info_df = pd.DataFrame()
    row = _row_for_stock(stock_info_df, stock_id)
    industry_category = str(row.get("industry_category", "")).strip() if row is not None else ""

    if row is None and hasattr(client, "industry_chain"):
        try:
            chain_df = client.industry_chain()
            mine = chain_df[chain_df["stock_id"].astype(str) == str(stock_id)] if not chain_df.empty else pd.DataFrame()
            if not mine.empty:
                industries = mine["industry"].dropna().astype(str).tolist() if "industry" in mine.columns else []
                peers_in_chain: list[str] = []
                if industries and "industry" in chain_df.columns:
                    peer_rows = chain_df[chain_df["industry"].isin(industries)]
                    peers_in_chain = [
                        sid for sid in peer_rows["stock_id"].astype(str).tolist()
                        if sid != stock_id
                    ][:max_peers]
                return {
                    "group": industries[0] if industries else "legacy_chain_fallback",
                    "label": industries[0] if industries else "legacy_chain_fallback",
                    "peers": peers_in_chain,
                    "mapping_source": "legacy_industry_chain_fallback",
                    "industry_category": industries[0] if industries else "",
                    "supply_chain_heavy": True,
                    "role": "",
                }
        except Exception:  # noqa: BLE001
            pass

    group_name, group_payload = _group_for_stock(proxy_map, stock_id)
    if group_payload:
        peers_in_group = [sid for sid in group_payload.get("stock_ids", []) if sid != stock_id][:max_peers]
        return {
            "group": group_name,
            "label": group_payload.get("label", group_name),
            "peers": peers_in_group,
            "mapping_source": "proxy_map_explicit",
            "industry_category": industry_category,
            "supply_chain_heavy": bool(group_payload.get("supply_chain_heavy")),
            "role": group_payload.get("role_map", {}).get(stock_id, ""),
        }

    category_payload = proxy_map.get("industry_category_groups", {}).get(industry_category)
    if category_payload:
        same_category = stock_info_df[
            stock_info_df["industry_category"].astype(str).str.strip() == industry_category
        ]
        peers_in_group = [
            sid for sid in same_category["stock_id"].astype(str).tolist()
            if sid != stock_id
        ][:max_peers]
        return {
            "group": category_payload.get("group", industry_category),
            "label": category_payload.get("label", industry_category),
            "peers": peers_in_group,
            "mapping_source": "proxy_map_category",
            "industry_category": industry_category,
            "supply_chain_heavy": bool(category_payload.get("supply_chain_heavy")),
            "role": "",
        }

    fallback_peers: list[str] = []
    if row is not None and industry_category:
        same_category = stock_info_df[
            stock_info_df["industry_category"].astype(str).str.strip() == industry_category
        ]
        fallback_peers = [
            sid for sid in same_category["stock_id"].astype(str).tolist()
            if sid != stock_id
        ][:max_peers]

    return {
        "group": industry_category or "unmapped",
        "label": industry_category or "unmapped",
        "peers": fallback_peers,
        "mapping_source": "industry_category_fallback" if fallback_peers else "missing",
        "industry_category": industry_category,
        "supply_chain_heavy": False,
        "role": "",
    }


def _peer_echo_check(comparison: Optional[peers.PeerComparison]) -> CheckResult:
    if comparison is None:
        return CheckResult(
            name="Peer echo",
            status=AssessmentStatus.NOT_ASSESSED,
            detail="Peer comparison unavailable",
            weight=35,
            earned=0,
            source="TaiwanStockMonthRevenue + TaiwanStockFinancialStatements + TaiwanStockInstitutionalInvestorsBuySell",
            signal_key="peer_echo",
            fallback_behavior="not_assessed",
        )

    rankings = getattr(comparison, "candidate_rankings", {}) or {}
    populated = {
        metric: (rank, total)
        for metric, (rank, total) in rankings.items()
        if rank and total and total >= 2
    }
    if len(populated) < 2:
        return CheckResult(
            name="Peer echo",
            status=AssessmentStatus.NOT_ASSESSED,
            detail="Insufficient populated peer metrics",
            weight=35,
            earned=0,
            source="TaiwanStockMonthRevenue + TaiwanStockFinancialStatements + TaiwanStockInstitutionalInvestorsBuySell",
            signal_key="peer_echo",
            fallback_behavior="not_assessed",
        )

    top_half = [
        metric for metric, (rank, total) in populated.items()
        if rank <= ((total + 1) // 2)
    ]
    bottom_ranked = [
        metric for metric, (rank, total) in populated.items()
        if rank == total
    ]

    if len(bottom_ranked) >= 2 and not top_half:
        return CheckResult(
            name="Peer echo",
            status=AssessmentStatus.FAILED,
            detail="Bottom-ranked on multiple peer metrics: " + ", ".join(bottom_ranked),
            weight=35,
            earned=0,
            source="TaiwanStockMonthRevenue + TaiwanStockFinancialStatements + TaiwanStockInstitutionalInvestorsBuySell",
            signal_key="peer_echo",
        )

    earned = 35 if len(top_half) >= 2 else 20
    return CheckResult(
        name="Peer echo",
        status=AssessmentStatus.PASSED,
        detail="Top-half on " + ", ".join(top_half) if top_half else "Mixed peer echo",
        weight=35,
        earned=earned,
        source="TaiwanStockMonthRevenue + TaiwanStockFinancialStatements + TaiwanStockInstitutionalInvestorsBuySell",
        signal_key="peer_echo",
    )


def _institutional_alignment_check(comparison: Optional[peers.PeerComparison], candidate: str) -> CheckResult:
    if comparison is None or comparison.institutional_flow_60d.empty:
        return CheckResult(
            name="Institutional alignment",
            status=AssessmentStatus.NOT_ASSESSED,
            detail="Peer institutional-flow context unavailable",
            weight=20,
            earned=0,
            source="TaiwanStockInstitutionalInvestorsBuySell",
            signal_key="institutional_alignment",
            fallback_behavior="not_assessed",
        )

    row = comparison.institutional_flow_60d[
        comparison.institutional_flow_60d["stock_id"].astype(str) == str(candidate)
    ]
    if row.empty:
        return CheckResult(
            name="Institutional alignment",
            status=AssessmentStatus.NOT_ASSESSED,
            detail="Candidate row missing from institutional-flow comparison",
            weight=20,
            earned=0,
            source="TaiwanStockInstitutionalInvestorsBuySell",
            signal_key="institutional_alignment",
            fallback_behavior="not_assessed",
        )

    numeric_cols = [col for col in row.columns if col != "stock_id"]
    values = pd.to_numeric(row.iloc[0][numeric_cols], errors="coerce").dropna()
    if values.empty:
        return CheckResult(
            name="Institutional alignment",
            status=AssessmentStatus.NOT_ASSESSED,
            detail="No populated institutional-flow fields",
            weight=20,
            earned=0,
            source="TaiwanStockInstitutionalInvestorsBuySell",
            signal_key="institutional_alignment",
            fallback_behavior="not_assessed",
        )

    total_flow = float(values.sum())
    if total_flow > 0:
        return CheckResult(
            name="Institutional alignment",
            status=AssessmentStatus.PASSED,
            detail=f"Net institutional flow positive across peer panel ({total_flow:,.0f})",
            weight=20,
            earned=20,
            source="TaiwanStockInstitutionalInvestorsBuySell",
            signal_key="institutional_alignment",
        )
    if total_flow < 0:
        return CheckResult(
            name="Institutional alignment",
            status=AssessmentStatus.FAILED,
            detail=f"Net institutional flow negative across peer panel ({total_flow:,.0f})",
            weight=20,
            earned=0,
            source="TaiwanStockInstitutionalInvestorsBuySell",
            signal_key="institutional_alignment",
        )
    return CheckResult(
        name="Institutional alignment",
        status=AssessmentStatus.PASSED,
        detail="Institutional flow flat / neutral",
        weight=20,
        earned=10,
        source="TaiwanStockInstitutionalInvestorsBuySell",
        signal_key="institutional_alignment",
    )


def _macro_note_checks(
    client: FinMindClient,
    exporter_bias: bool,
    macro_context: Optional[dict] = None,
) -> list[CheckResult]:
    macro_context = macro_context or {}
    checks: list[CheckResult] = []

    fx_df = macro_context.get("fx_usd_twd")
    if fx_df is None:
        try:
            fx_df = client.get("TaiwanExchangeRate", stock_id="USD", start_date="2025-01-01")
        except Exception:  # noqa: BLE001
            fx_df = pd.DataFrame()
    if not fx_df.empty:
        fx_sorted = fx_df.sort_values("date")
        latest = pd.to_numeric(fx_sorted.iloc[-1].get("spot_sell"), errors="coerce")
        previous = pd.to_numeric(fx_sorted.tail(30).iloc[0].get("spot_sell"), errors="coerce")
        direction = "stable"
        if pd.notna(latest) and pd.notna(previous):
            if latest > previous:
                direction = "TWD weaker / USD stronger"
            elif latest < previous:
                direction = "TWD stronger / USD weaker"
        bias = "exporter tailwind" if exporter_bias else "context only"
        checks.append(
            CheckResult(
                name="FX backdrop",
                status=AssessmentStatus.PASSED,
                detail=f"{direction}; {bias}",
                weight=0,
                earned=0,
                source="TaiwanExchangeRate",
                as_of=str(fx_sorted.iloc[-1].get("date")),
                signal_key="fx_backdrop",
            )
        )
    else:
        checks.append(
            CheckResult(
                name="FX backdrop",
                status=AssessmentStatus.NOT_ASSESSED,
                detail="USD/TWD context unavailable",
                weight=0,
                earned=0,
                source="TaiwanExchangeRate",
                signal_key="fx_backdrop",
                fallback_behavior="not_assessed",
            )
        )

    rate_df = macro_context.get("us_10y")
    if rate_df is None:
        try:
            rate_df = client.get("GovernmentBondsYield", stock_id="United States 10-Year", start_date="2025-01-01")
        except Exception:  # noqa: BLE001
            rate_df = pd.DataFrame()
    if not rate_df.empty:
        sorted_df = rate_df.sort_values("date")
        latest = pd.to_numeric(sorted_df.iloc[-1].get("value"), errors="coerce")
        checks.append(
            CheckResult(
                name="Rates backdrop",
                status=AssessmentStatus.PASSED,
                detail=f"US 10Y yield backdrop observed at {latest:.2f}%" if pd.notna(latest) else "Rates backdrop observed",
                weight=0,
                earned=0,
                source="GovernmentBondsYield",
                as_of=str(sorted_df.iloc[-1].get("date")),
                signal_key="rates_backdrop",
            )
        )
    else:
        checks.append(
            CheckResult(
                name="Rates backdrop",
                status=AssessmentStatus.NOT_ASSESSED,
                detail="US 10Y yield backdrop unavailable",
                weight=0,
                earned=0,
                source="GovernmentBondsYield",
                signal_key="rates_backdrop",
                fallback_behavior="not_assessed",
            )
        )

    checks.append(
        CheckResult(
            name="Business indicator timing",
            status=AssessmentStatus.NOT_ASSESSED,
            detail="Backer-only dataset downgraded to backdrop only and removed from default timing logic",
            weight=0,
            earned=0,
            source="TaiwanBusinessIndicator",
            signal_key="business_indicator_timing",
            fallback_behavior="not_assessed",
        )
    )
    return checks


def run(
    client: FinMindClient,
    stock_id: str,
    strategy_mode: StrategyMode = StrategyMode.TACTICAL_LONG_SHORT,
    stock_info_df: Optional[pd.DataFrame] = None,
    macro_context: Optional[dict] = None,
    max_peers: int = 4,
) -> WorkstreamResult:
    context = resolve_peer_context(client, stock_id, stock_info_df=stock_info_df, max_peers=max_peers)
    checks: list[CheckResult] = []
    manual_requirements: list[ManualRequirement] = []

    peers_for_candidate = context["peers"]
    mapping_status = AssessmentStatus.PASSED
    mapping_detail = (
        f"{context['label']} via {context['mapping_source']}; peers: {', '.join(peers_for_candidate) or 'none'}"
    )
    if context["mapping_source"] == "missing" or not peers_for_candidate:
        mapping_status = AssessmentStatus.MANUAL_REVIEW_REQUIRED
        manual_requirements.append(
            ManualRequirement(
                title="Review industry mapping",
                detail="Proxy map and category fallback could not build enough peer context for this name.",
                category="industry_mapping",
            )
        )
    checks.append(
        CheckResult(
            name="Industry / value-chain mapping",
            status=mapping_status,
            detail=mapping_detail,
            weight=25,
            earned=25 if mapping_status == AssessmentStatus.PASSED else 0,
            source="value_chain_proxy.json + TaiwanStockInfo",
            signal_key="industry_mapping",
            fallback_behavior="manual_review_required",
            metadata={
                "mapping_source": context["mapping_source"],
                "group": context["group"],
                "role": context["role"],
                "tier": DatasetTier.FREE,
            },
        )
    )

    comparison = None
    if peers_for_candidate:
        comparison = peers.compare(client, candidate=stock_id, peers=peers_for_candidate)
    checks.append(_peer_echo_check(comparison))
    checks.append(_institutional_alignment_check(comparison, stock_id))
    checks.extend(_macro_note_checks(client, exporter_bias=context["supply_chain_heavy"], macro_context=macro_context))

    score_summary = calculate_score(checks)
    status = aggregate_status(checks, manual_requirements)
    notes = [
        f"strategy_mode={strategy_mode.value}",
        f"group={context['group']}",
        f"mapping_source={context['mapping_source']}",
    ]
    if comparison is not None:
        notes.append("Peer echo computed from free-tier revenue, financials, and institutional flow.")

    return WorkstreamResult(
        name="Industry/Macro",
        status=status,
        checks=checks,
        score=score_summary.normalized_score,
        available_weight=score_summary.available_weight,
        manual_requirements=manual_requirements,
        notes=notes,
        removed_or_downgraded_signals=[
            entry for entry in removed_signal_entries()
            if entry["signal_key"] in {"business_indicator_timing", "tick_snapshot_timing"}
        ],
        metadata={
            "group": context["group"],
            "label": context["label"],
            "peers": peers_for_candidate,
            "mapping_source": context["mapping_source"],
            "industry_category": context["industry_category"],
            "role": context["role"],
        },
    )
