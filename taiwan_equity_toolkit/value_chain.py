"""
Value-chain helper rebuilt for the V2 free-tier default path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

from taiwan_equity_toolkit import metrics, parsers
from taiwan_equity_toolkit.client import FinMindClient
from taiwan_equity_toolkit.workstream_industry import resolve_peer_context


@dataclass
class ChainPosition:
    stock_id: str
    industries: list[str] = field(default_factory=list)
    sub_industries: list[str] = field(default_factory=list)
    peers_in_chain: list[str] = field(default_factory=list)
    mapping_source: str = ""
    role: str = ""


@dataclass
class UpstreamSignal:
    stock_id: str
    revenue_yoy: Optional[float] = None
    margin_direction: str = "unknown"
    institutional_flow_60d: Optional[float] = None
    as_of: Optional[str] = None


@dataclass
class ValueChainReport:
    candidate: str
    position: ChainPosition
    upstream_signals: list[UpstreamSignal] = field(default_factory=list)
    downstream_signals: list[UpstreamSignal] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = [f"# Value Chain — {self.candidate}"]
        lines.append(f"Industries: {', '.join(self.position.industries) or 'n/a'}")
        lines.append(f"Sub-industries: {', '.join(self.position.sub_industries) or 'n/a'}")
        lines.append(
            f"Peers in chain: {len(self.position.peers_in_chain)} — "
            f"{', '.join(self.position.peers_in_chain[:8])}"
            + (" ..." if len(self.position.peers_in_chain) > 8 else "")
        )
        lines.append(f"Mapping source: {self.position.mapping_source or 'n/a'}")
        if self.upstream_signals:
            lines.append("")
            lines.append("## Proxy chain signals")
            for signal in self.upstream_signals:
                yoy = f"{signal.revenue_yoy:+.1f}%" if signal.revenue_yoy is not None else "n/a"
                flow = f"{signal.institutional_flow_60d:+,.0f}" if signal.institutional_flow_60d is not None else "n/a"
                lines.append(
                    f"  - {signal.stock_id}: Rev YoY {yoy} | "
                    f"Margin {signal.margin_direction} | Inst flow {flow} ({signal.as_of})"
                )
        if self.notes:
            lines.append("")
            for note in self.notes:
                lines.append(f"_{note}_")
        return "\n".join(lines)


def has_usable_signal(signal: UpstreamSignal) -> bool:
    return (
        signal.revenue_yoy is not None
        or signal.institutional_flow_60d is not None
        or signal.margin_direction != "unknown"
    )


def locate(client: FinMindClient, stock_id: str) -> ChainPosition:
    context = resolve_peer_context(client, stock_id)
    return ChainPosition(
        stock_id=stock_id,
        industries=[context["label"]] if context["label"] else [],
        sub_industries=[context["group"]] if context["group"] else [],
        peers_in_chain=list(context["peers"]),
        mapping_source=str(context["mapping_source"]),
        role=str(context["role"]),
    )


def analyze(
    client: FinMindClient,
    stock_id: str,
    override_upstream: Optional[list[str]] = None,
    max_upstream_names: int = 6,
) -> ValueChainReport:
    today = datetime.today()
    rev_start = (today - timedelta(days=540)).strftime("%Y-%m-%d")
    fs_start = (today - timedelta(days=540)).strftime("%Y-%m-%d")
    flow_start = (today - timedelta(days=90)).strftime("%Y-%m-%d")

    position = locate(client, stock_id)
    report = ValueChainReport(candidate=stock_id, position=position)

    if override_upstream:
        upstream_ids = override_upstream[:max_upstream_names]
    elif position.peers_in_chain:
        upstream_ids = position.peers_in_chain[:max_upstream_names]
    else:
        report.notes.append(
            "Proxy value-chain map could not build peers for this stock; manual review required."
        )
        return report

    rev_map = client.get_multi("TaiwanStockMonthRevenue", upstream_ids, rev_start)
    fs_map = client.get_multi("TaiwanStockFinancialStatements", upstream_ids, fs_start)
    flow_map = client.get_multi("TaiwanStockInstitutionalInvestorsBuySell", upstream_ids, flow_start)

    for peer_id in upstream_ids:
        signal = UpstreamSignal(stock_id=peer_id)
        rev_metric = metrics.revenue_growth_yoy(rev_map.get(peer_id, pd.DataFrame()))
        signal.revenue_yoy = rev_metric.value
        signal.as_of = rev_metric.as_of

        income = parsers.parse_income_statements(fs_map.get(peer_id, pd.DataFrame()))
        if len(income) >= 2:
            series = [item.gross_margin for item in sorted(income, key=lambda row: row.date)[-4:] if item.gross_margin is not None]
            if len(series) >= 2:
                if series[-1] > series[0] + 0.01:
                    signal.margin_direction = "expanding"
                elif series[-1] < series[0] - 0.01:
                    signal.margin_direction = "compressing"
                else:
                    signal.margin_direction = "flat"

        flows = metrics.institutional_net_flow(flow_map.get(peer_id, pd.DataFrame()), lookback_days=60)
        total_flow = 0.0
        any_flow = False
        for metric_value in flows.values():
            if metric_value.value is None:
                continue
            total_flow += float(metric_value.value)
            any_flow = True
        signal.institutional_flow_60d = total_flow if any_flow else None

        if has_usable_signal(signal):
            report.upstream_signals.append(signal)
        else:
            report.notes.append(f"{peer_id}: no usable proxy-chain signal data")

    if not report.upstream_signals:
        report.notes.append(
            "The default free-tier path found no usable proxy-chain signals; review manually or add an adapter."
        )
    return report
