"""
Memo formatter for the V2 architecture with a compatibility fallback.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from taiwan_equity_toolkit.models import AssessmentStatus, CandidateAssessment
from taiwan_equity_toolkit.synthesis import SynthesisInputs


def _status_label(status: AssessmentStatus) -> str:
    return status.value.upper()


@dataclass
class FullScreenMemo:
    stock_id: str
    industry_view: str = ""
    company_qualitative: str = ""
    triage: Optional[object] = None
    gate3: Optional[object] = None
    peer_comparison: Optional[object] = None
    value_chain_notes: str = ""
    portfolio_fit_notes: str = ""
    entry_architecture_notes: str = ""
    thesis_statement: str = ""
    catalyst_path: str = ""
    invalidation: str = ""
    verdict: str = ""
    candidate_assessment: Optional[CandidateAssessment] = None
    synthesis_inputs: Optional[SynthesisInputs] = None

    def _render_v2(self) -> str:
        assert self.candidate_assessment is not None
        inputs = self.synthesis_inputs or SynthesisInputs()
        assessment = self.candidate_assessment
        primary_reason = str(assessment.metadata.get("primary_reason", "")).strip()

        lines = [
            f"# Taiwan Equity Memo V2 — {assessment.stock_id}",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            f"## Verdict: {_status_label(assessment.status)}",
            primary_reason or assessment.thesis_stub,
            "",
            "## Parallel workstreams",
        ]
        for workstream in [assessment.industry, assessment.company, assessment.setup]:
            lines.append(
                f"- {workstream.name}: {workstream.status.value} | "
                f"score {workstream.score if workstream.score is not None else 'n/a'}"
            )

        lines += [
            "",
            "## Synthesis",
            f"- Thesis: {inputs.thesis.strip() or assessment.thesis_stub}",
            f"- Variant perception: {inputs.variant_perception.strip() or 'manual_review_required'}",
            f"- Invalidation: {inputs.invalidation.strip() or 'manual_review_required'}",
        ]
        if assessment.strategy_mode.value == "tactical_long_short":
            lines.append(f"- Dated catalyst: {inputs.catalyst.strip() or 'manual_review_required'}")
        else:
            lines.append(f"- Milestone path: {inputs.milestone.strip() or 'manual_review_required'}")

        sizing_band = assessment.sizing_band
        lines += [
            "",
            "## Position sizing",
            (
                f"- Mechanical sizing band: {sizing_band.min_pct:.2f}%–{sizing_band.max_pct:.2f}% "
                f"(suggested {sizing_band.suggested_pct:.2f}%)"
                if sizing_band
                else "- Mechanical sizing band: manual_review_required"
            ),
            f"- Conviction tier: {inputs.conviction_tier.strip() or 'manual_review_required'}",
        ]

        scenario_cases = assessment.metadata.get("scenario_cases") or []
        if scenario_cases:
            lines.append(f"- Scenario EV cases: {len(scenario_cases)}")
        else:
            lines.append("- Scenario EV cases: manual_review_required")

        lines += [
            "",
            "## Risk discipline",
            f"- Sell discipline taxonomy: {inputs.exit_archetype.strip() or 'manual_review_required'}",
            "- Forced review trigger: price down 20% from cost or thesis invalidation evidence",
            f"- Pre-mortem: {inputs.pre_mortem.strip() or 'manual_review_required'}",
            f"- Monitoring cadence: {assessment.monitoring_cadence}",
        ]

        if assessment.manual_requirements:
            lines += ["", "## Manual requirements"]
            for requirement in assessment.manual_requirements:
                lines.append(f"- {requirement.title}: {requirement.detail}")

        removed = (
            assessment.industry.removed_or_downgraded_signals
            + assessment.company.removed_or_downgraded_signals
            + assessment.setup.removed_or_downgraded_signals
        )
        if removed:
            seen = set()
            lines += ["", "## Removed / downgraded default-path signals"]
            for item in removed:
                key = item.get("signal_key")
                if key in seen:
                    continue
                seen.add(key)
                lines.append(f"- {key}: {item.get('reason', '')}")

        return "\n".join(lines)

    def _render_legacy(self) -> str:
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
            lines += ["## Gate 3 — Company Quality", self.gate3.memo(), ""]
        if self.peer_comparison:
            lines += ["## Peer Context", self.peer_comparison.summary(), ""]
        if self.value_chain_notes:
            lines += ["## Value Chain", self.value_chain_notes, ""]
        if self.portfolio_fit_notes:
            lines += ["## Portfolio Fit", self.portfolio_fit_notes, ""]
        if self.entry_architecture_notes:
            lines += ["## Setup / Entry", self.entry_architecture_notes, ""]
        if self.thesis_statement or self.catalyst_path or self.invalidation:
            lines += ["## Thesis"]
            if self.thesis_statement:
                lines.append(f"**Thesis:** {self.thesis_statement}")
            if self.catalyst_path:
                lines.append(f"**Catalyst / milestone:** {self.catalyst_path}")
            if self.invalidation:
                lines.append(f"**Invalidation criteria:** {self.invalidation}")
            lines.append("")
        return "\n".join(lines)

    def render(self) -> str:
        if self.candidate_assessment is not None:
            return self._render_v2()
        return self._render_legacy()
