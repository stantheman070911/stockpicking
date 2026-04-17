"""
Peer comparison — async batch utilities for cross-source validation.

Where the AI-vs-retail edge is most visible. `compare()` runs all peers
concurrently and returns ranked comparative tables.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

from taiwan_equity_toolkit.client import FinMindClient
from taiwan_equity_toolkit import metrics, parsers


@dataclass
class PeerComparison:
    candidate: str
    peers: list[str]
    revenue_yoy: pd.DataFrame        # stock_id, yoy_pct, as_of
    gross_margin: pd.DataFrame       # stock_id, gm_pct, as_of
    operating_margin: pd.DataFrame
    cfo_to_ni: pd.DataFrame
    correlation_matrix: pd.DataFrame  # symmetric return correlation
    institutional_flow_60d: pd.DataFrame
    candidate_rankings: dict[str, tuple[int, int]] = field(default_factory=dict)  # metric → (rank, total)

    def summary(self) -> str:
        lines = [f"# Peer comparison: {self.candidate} vs {len(self.peers)} peer(s)"]
        lines.append("")
        lines.append("## Revenue YoY")
        lines.append(self.revenue_yoy.to_string(index=False))
        lines.append("")
        lines.append("## Gross margin")
        lines.append(self.gross_margin.to_string(index=False))
        lines.append("")
        lines.append("## Operating margin")
        lines.append(self.operating_margin.to_string(index=False))
        lines.append("")
        lines.append("## CFO/NI")
        lines.append(self.cfo_to_ni.to_string(index=False))
        lines.append("")
        lines.append("## 90-day return correlation")
        lines.append(self.correlation_matrix.to_string())
        lines.append("")
        lines.append("## 60-day institutional net flow")
        lines.append(self.institutional_flow_60d.to_string(index=False))
        if self.candidate_rankings:
            lines.append("")
            lines.append("## Candidate's peer rankings")
            for metric, (rank, total) in self.candidate_rankings.items():
                lines.append(f"- {metric}: #{rank} of {total}")
        return "\n".join(lines)


def _rank_candidate(df: pd.DataFrame, candidate: str, metric_col: str, higher_is_better: bool = True) -> tuple[int, int]:
    """Return (rank, total) for the candidate within a ranked peer df."""
    if df.empty or metric_col not in df.columns:
        return (0, 0)
    ranked = df.dropna(subset=[metric_col]).sort_values(metric_col, ascending=not higher_is_better).reset_index(drop=True)
    total = len(ranked)
    match = ranked[ranked["stock_id"].astype(str) == str(candidate)]
    if match.empty:
        return (0, total)
    return (int(match.index[0]) + 1, total)


def compare(
    client: FinMindClient,
    candidate: str,
    peers: list[str],
    lookback_days: int = 365,
) -> PeerComparison:
    """
    Run a comparative analysis of candidate vs peers across operating and
    market-structure dimensions. Uses async batch where available.
    """
    all_ids = [candidate] + [p for p in peers if p != candidate]
    today = datetime.today()
    fs_start = (today - timedelta(days=540)).strftime("%Y-%m-%d")
    rev_start = (today - timedelta(days=730)).strftime("%Y-%m-%d")
    price_start = (today - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    flow_start = (today - timedelta(days=90)).strftime("%Y-%m-%d")

    # Batch fetches
    fs_map = client.get_multi("TaiwanStockFinancialStatements", all_ids, fs_start)
    cf_map = client.get_multi("TaiwanStockCashFlowsStatement", all_ids, fs_start)
    rev_map = client.get_multi("TaiwanStockMonthRevenue", all_ids, rev_start)
    price_map = client.get_multi("TaiwanStockPriceAdj", all_ids, price_start)
    flow_map = client.get_multi("TaiwanStockInstitutionalInvestorsBuySell", all_ids, flow_start)

    # Operating metrics across peers
    rev_yoy_rows = []
    gm_rows = []
    om_rows = []
    cfo_ni_rows = []
    for sid in all_ids:
        income = parsers.parse_income_statements(fs_map.get(sid, pd.DataFrame()))
        cash = parsers.parse_cash_flows(cf_map.get(sid, pd.DataFrame()))

        rev_yoy = metrics.revenue_growth_yoy(rev_map.get(sid, pd.DataFrame()))
        rev_yoy_rows.append({"stock_id": sid, "yoy_pct": rev_yoy.value, "as_of": rev_yoy.as_of})

        gm = metrics.gross_margin_latest(income)
        gm_rows.append({"stock_id": sid, "gm_pct": gm.value, "as_of": gm.as_of})

        om = metrics.operating_margin_latest(income)
        om_rows.append({"stock_id": sid, "om_pct": om.value, "as_of": om.as_of})

        cfoni = metrics.cfo_to_ni_ratio(income, cash, 4)
        cfo_ni_rows.append({"stock_id": sid, "cfo_ni": cfoni.value, "as_of": cfoni.as_of})

    rev_yoy_df = pd.DataFrame(rev_yoy_rows)
    gm_df = pd.DataFrame(gm_rows)
    om_df = pd.DataFrame(om_rows)
    cfo_ni_df = pd.DataFrame(cfo_ni_rows)

    # Correlation matrix
    corr_frames = []
    for sid in all_ids:
        p = price_map.get(sid, pd.DataFrame())
        if p.empty or "close" not in p.columns:
            continue
        s = p[["date", "close"]].copy()
        s["date"] = pd.to_datetime(s["date"])
        s = s.set_index("date")["close"].pct_change().rename(sid)
        corr_frames.append(s)
    if corr_frames:
        corr_df = pd.concat(corr_frames, axis=1).tail(91).corr().round(2)
    else:
        corr_df = pd.DataFrame()

    # Institutional flow (60d net) per name
    flow_rows = []
    for sid in all_ids:
        f_df = flow_map.get(sid, pd.DataFrame())
        flows = metrics.institutional_net_flow(f_df, lookback_days=60)
        row = {"stock_id": sid}
        for k, m in flows.items():
            row[k] = m.value
        flow_rows.append(row)
    flow_df = pd.DataFrame(flow_rows)

    # Candidate rankings
    rankings = {
        "Revenue YoY": _rank_candidate(rev_yoy_df, candidate, "yoy_pct", True),
        "Gross margin": _rank_candidate(gm_df, candidate, "gm_pct", True),
        "Operating margin": _rank_candidate(om_df, candidate, "om_pct", True),
        "CFO/NI": _rank_candidate(cfo_ni_df, candidate, "cfo_ni", True),
    }

    return PeerComparison(
        candidate=candidate,
        peers=peers,
        revenue_yoy=rev_yoy_df.sort_values("yoy_pct", ascending=False, na_position="last"),
        gross_margin=gm_df.sort_values("gm_pct", ascending=False, na_position="last"),
        operating_margin=om_df.sort_values("om_pct", ascending=False, na_position="last"),
        cfo_to_ni=cfo_ni_df.sort_values("cfo_ni", ascending=False, na_position="last"),
        correlation_matrix=corr_df,
        institutional_flow_60d=flow_df,
        candidate_rankings=rankings,
    )
