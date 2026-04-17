"""
Value Chain Helper — Gate 5 support.

Maps a stock to its industry chain position using TaiwanStockIndustryChain,
then fetches upstream/downstream signals via async batch.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

from taiwan_equity_toolkit.client import FinMindClient
from taiwan_equity_toolkit import parsers, metrics


@dataclass
class ChainPosition:
    stock_id: str
    industries: list[str] = field(default_factory=list)        # all industry tags for this stock
    sub_industries: list[str] = field(default_factory=list)
    peers_in_chain: list[str] = field(default_factory=list)    # other stocks in same chain tags


@dataclass
class UpstreamSignal:
    stock_id: str
    revenue_yoy: Optional[float] = None
    margin_direction: str = "unknown"  # "expanding", "flat", "compressing", "unknown"
    institutional_flow_60d: Optional[float] = None
    as_of: Optional[str] = None


@dataclass
class ValueChainReport:
    candidate: str
    position: ChainPosition
    upstream_signals: list[UpstreamSignal] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = [f"# Value Chain — {self.candidate}"]
        lines.append(f"Industries: {', '.join(self.position.industries) or 'n/a'}")
        lines.append(f"Sub-industries: {', '.join(self.position.sub_industries) or 'n/a'}")
        lines.append(f"Peers in chain: {len(self.position.peers_in_chain)} — {', '.join(self.position.peers_in_chain[:8])}" +
                     (" ..." if len(self.position.peers_in_chain) > 8 else ""))
        if self.upstream_signals:
            lines.append("")
            lines.append("## Upstream / chain signals")
            for s in self.upstream_signals:
                yoy = f"{s.revenue_yoy:+.1f}%" if s.revenue_yoy is not None else "n/a"
                flow = f"{s.institutional_flow_60d:+,.0f}" if s.institutional_flow_60d is not None else "n/a"
                lines.append(f"  - {s.stock_id}: Rev YoY {yoy} | Margin {s.margin_direction} | Inst flow {flow} ({s.as_of})")
        if self.notes:
            lines.append("")
            for n in self.notes:
                lines.append(f"_{n}_")
        return "\n".join(lines)


def has_usable_signal(signal: UpstreamSignal) -> bool:
    return (
        signal.revenue_yoy is not None
        or signal.institutional_flow_60d is not None
        or signal.margin_direction != "unknown"
    )


def locate(client: FinMindClient, stock_id: str) -> ChainPosition:
    """Identify the industry-chain position of a stock and its chain-peers."""
    chain_df = client.industry_chain()
    if chain_df.empty:
        return ChainPosition(stock_id=stock_id)

    mine = chain_df[chain_df["stock_id"].astype(str) == str(stock_id)]
    if mine.empty:
        return ChainPosition(stock_id=stock_id)

    industries = sorted(mine["industry"].dropna().unique().tolist()) if "industry" in mine.columns else []
    sub_industries = sorted(mine["sub_industry"].dropna().unique().tolist()) if "sub_industry" in mine.columns else []

    # Find peers in the same industry/sub_industry tags
    peers = set()
    if industries:
        same_ind = chain_df[chain_df["industry"].isin(industries)]
        peers.update(same_ind["stock_id"].astype(str).unique())
    if sub_industries:
        same_sub = chain_df[chain_df["sub_industry"].isin(sub_industries)]
        peers.update(same_sub["stock_id"].astype(str).unique())
    peers.discard(str(stock_id))

    return ChainPosition(
        stock_id=stock_id,
        industries=industries,
        sub_industries=sub_industries,
        peers_in_chain=sorted(peers),
    )


def analyze(
    client: FinMindClient,
    stock_id: str,
    override_upstream: Optional[list[str]] = None,
    max_upstream_names: int = 6,
) -> ValueChainReport:
    """
    Full Gate 5 analysis: locate chain position, fetch upstream signals.

    Args:
        client: Authenticated client
        stock_id: Candidate
        override_upstream: If provided, use these IDs as the upstream universe
                           (bypass industry-chain auto-detection)
        max_upstream_names: Cap on async batch size
    """
    today = datetime.today()
    rev_start = (today - timedelta(days=540)).strftime("%Y-%m-%d")
    fs_start = (today - timedelta(days=540)).strftime("%Y-%m-%d")
    flow_start = (today - timedelta(days=90)).strftime("%Y-%m-%d")

    position = locate(client, stock_id)
    report = ValueChainReport(candidate=stock_id, position=position)

    # Select names to batch
    if override_upstream:
        upstream_ids = override_upstream[:max_upstream_names]
    elif position.peers_in_chain:
        upstream_ids = position.peers_in_chain[:max_upstream_names]
    else:
        report.notes.append("No chain data available — Gate 5 requires manual upstream/downstream selection.")
        return report

    # Async batch
    rev_map = client.get_multi("TaiwanStockMonthRevenue", upstream_ids, rev_start)
    fs_map = client.get_multi("TaiwanStockFinancialStatements", upstream_ids, fs_start)
    flow_map = client.get_multi("TaiwanStockInstitutionalInvestorsBuySell", upstream_ids, flow_start)

    for sid in upstream_ids:
        signal = UpstreamSignal(stock_id=sid)

        # Revenue YoY
        rev_m = metrics.revenue_growth_yoy(rev_map.get(sid, pd.DataFrame()))
        signal.revenue_yoy = rev_m.value
        signal.as_of = rev_m.as_of

        # Margin direction (gross margin last 4Q)
        income = parsers.parse_income_statements(fs_map.get(sid, pd.DataFrame()))
        if len(income) >= 2:
            series = [r.gross_margin for r in sorted(income, key=lambda r: r.date)[-4:] if r.gross_margin is not None]
            if len(series) >= 2:
                if series[-1] > series[0] + 0.01:
                    signal.margin_direction = "expanding"
                elif series[-1] < series[0] - 0.01:
                    signal.margin_direction = "compressing"
                else:
                    signal.margin_direction = "flat"

        # Institutional net flow 60d
        flows = metrics.institutional_net_flow(flow_map.get(sid, pd.DataFrame()), lookback_days=60)
        # Net across all three investor types
        net = 0.0
        any_data = False
        for m in flows.values():
            if m.value is not None:
                net += m.value
                any_data = True
        signal.institutional_flow_60d = net if any_data else None

        if has_usable_signal(signal):
            report.upstream_signals.append(signal)
        else:
            report.notes.append(f"{sid}: no usable upstream signal data")

    return report
