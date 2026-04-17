"""
Memo formatter — assemble structured gate outputs into a CIO-grade memo.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from taiwan_equity_toolkit.triage import TriageResult
from taiwan_equity_toolkit.gate3 import Gate3Result
from taiwan_equity_toolkit.peers import PeerComparison


@dataclass
class FullScreenMemo:
    stock_id: str
    industry_view: str = ""
    company_qualitative: str = ""
    triage: Optional[TriageResult] = None
    gate3: Optional[Gate3Result] = None
    peer_comparison: Optional[PeerComparison] = None
    value_chain_notes: str = ""
    portfolio_fit_notes: str = ""
    entry_architecture_notes: str = ""
    thesis_statement: str = ""
    catalyst_path: str = ""
    invalidation: str = ""
    verdict: str = ""  # Actionable Watchlist / Conditional / Reject

    def render(self) -> str:
        lines = [
            f"# Pre-Trade Screening Memo — {self.stock_id}",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            f"## Verdict: {self.verdict or '(pending)'}",
            "",
        ]

        if self.industry_view:
            lines += ["## Gate 1 — Industry Direction", self.industry_view, ""]

        if self.company_qualitative:
            lines += ["## Gate 2 — Company Qualitative", self.company_qualitative, ""]

        if self.triage:
            lines += ["## Triage Filter", self.triage.summary(), ""]

        if self.gate3:
            lines += ["## Gate 3 — Forensic Quality", self.gate3.memo(), ""]

        if self.peer_comparison:
            lines += ["## Gate 4 — Cross-Source Validation", self.peer_comparison.summary(), ""]

        if self.value_chain_notes:
            lines += ["## Gate 5 — Value Chain Positioning", self.value_chain_notes, ""]

        if self.portfolio_fit_notes:
            lines += ["## Gate 6 — Portfolio Fit (Strategic)", self.portfolio_fit_notes, ""]

        if self.entry_architecture_notes:
            lines += ["## Gate 6.5 — Entry Architecture", self.entry_architecture_notes, ""]

        if self.thesis_statement or self.catalyst_path or self.invalidation:
            lines += ["## Gate 7 — Thesis & Dated Catalyst"]
            if self.thesis_statement:
                lines += [f"**Thesis:** {self.thesis_statement}"]
            if self.catalyst_path:
                lines += [f"**Dated catalyst:** {self.catalyst_path}"]
            if self.invalidation:
                lines += [f"**Invalidation criteria:** {self.invalidation}"]
            lines += [""]

        return "\n".join(lines)
