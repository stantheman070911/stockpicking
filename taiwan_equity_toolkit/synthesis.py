"""
V2 synthesis layer that combines the three parallel workstreams with the
analyst-facing memo requirements.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from taiwan_equity_toolkit.models import (
    AssessmentStatus,
    CandidateAssessment,
    ManualRequirement,
    SizingBand,
    StrategyMode,
    WorkstreamResult,
)


WORKSTREAM_WEIGHTS = {
    "industry": 0.30,
    "company": 0.40,
    "setup": 0.30,
}


@dataclass
class SynthesisInputs:
    thesis: str = ""
    variant_perception: str = ""
    invalidation: str = ""
    catalyst: str = ""
    milestone: str = ""
    conviction_tier: str = ""
    management_forensic: str = ""
    scuttlebutt_memo: str = ""
    pre_mortem: str = ""
    exit_archetype: str = ""
    monitoring_cadence: str = ""
    decision_journal: str = ""
    post_mortem_trigger: str = ""
    scenario_cases: list[dict[str, object]] = field(default_factory=list)


def _dedupe_manual_requirements(items: list[ManualRequirement]) -> list[ManualRequirement]:
    deduped: list[ManualRequirement] = []
    seen: set[tuple[str, str, str]] = set()
    for item in items:
        key = (item.title, item.detail, item.category)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _composite_score(industry: WorkstreamResult, company: WorkstreamResult, setup: WorkstreamResult) -> float:
    weighted = 0.0
    total_weight = 0.0
    for name, workstream in [
        ("industry", industry),
        ("company", company),
        ("setup", setup),
    ]:
        if workstream.score is None:
            continue
        weight = WORKSTREAM_WEIGHTS[name]
        weighted += workstream.score * weight
        total_weight += weight
    return round(weighted / total_weight, 2) if total_weight else 0.0


def _auto_thesis_stub(stock_id: str, industry: WorkstreamResult, company: WorkstreamResult, setup: WorkstreamResult) -> str:
    strong_checks = []
    for workstream in [industry, company, setup]:
        passed_checks = [check for check in workstream.checks if check.status == AssessmentStatus.PASSED]
        if not passed_checks:
            continue
        strongest = max(passed_checks, key=lambda check: (check.effective_earned, check.weight, check.name))
        strong_checks.append(f"{workstream.name}: {strongest.name}")
    if not strong_checks:
        return f"{stock_id}: free-tier screen needs manual synthesis before a thesis can be stated confidently."
    return f"{stock_id}: " + "; ".join(strong_checks[:3])


def _required_synthesis_items(
    strategy_mode: StrategyMode,
    inputs: SynthesisInputs,
    sizing_band: Optional[SizingBand],
) -> list[ManualRequirement]:
    requirements: list[ManualRequirement] = []

    if not inputs.thesis.strip():
        requirements.append(
            ManualRequirement(
                title="Write thesis",
                detail="Write the concise investment thesis before promoting the name beyond the screen.",
                category="synthesis",
            )
        )
    if not inputs.variant_perception.strip():
        requirements.append(
            ManualRequirement(
                title="Variant perception",
                detail="State what the market is missing and why that gap should close.",
                category="variant_perception",
            )
        )
    if not inputs.invalidation.strip():
        requirements.append(
            ManualRequirement(
                title="Invalidation criteria",
                detail="Define the observable condition that invalidates the thesis.",
                category="risk_control",
            )
        )
    if strategy_mode == StrategyMode.TACTICAL_LONG_SHORT:
        if not inputs.catalyst.strip():
            requirements.append(
                ManualRequirement(
                    title="Dated catalyst",
                    detail="Tactical mode requires a named, dated catalyst or a manual waiver.",
                    category="catalyst",
                )
            )
    elif not inputs.milestone.strip():
        requirements.append(
            ManualRequirement(
                title="Milestone path",
                detail="Quality-compounder mode still requires a milestone path even when no near-dated catalyst exists.",
                category="catalyst",
            )
        )

    if not inputs.conviction_tier.strip():
        requirements.append(
            ManualRequirement(
                title="Conviction input",
                detail="Final sizing requires analyst conviction and variant-perception quality, not only the mechanical sizing band.",
                category="position_sizing",
            )
        )
    elif sizing_band is None:
        requirements.append(
            ManualRequirement(
                title="Mechanical sizing band",
                detail="The setup workstream did not produce a sizing band; review liquidity, volatility, and correlation inputs.",
                category="position_sizing",
            )
        )

    if not inputs.exit_archetype.strip():
        requirements.append(
            ManualRequirement(
                title="Sell discipline taxonomy",
                detail="Choose an exit archetype and document the forced-review trigger, including the -20% review rule.",
                category="sell_discipline",
            )
        )
    if not inputs.pre_mortem.strip():
        requirements.append(
            ManualRequirement(
                title="Pre-mortem",
                detail="Complete the pre-mortem before final approval.",
                category="pre_mortem",
            )
        )
    if not inputs.management_forensic.strip():
        requirements.append(
            ManualRequirement(
                title="Management forensic memo",
                detail="Record management-forensic findings explicitly; do not leave this as implicit judgment.",
                category="management_forensic",
            )
        )
    if not inputs.scuttlebutt_memo.strip():
        requirements.append(
            ManualRequirement(
                title="Scuttlebutt / channel-check memo",
                detail="Document whether channel checks were completed and what they changed.",
                category="scuttlebutt",
            )
        )
    if not inputs.monitoring_cadence.strip():
        requirements.append(
            ManualRequirement(
                title="Monitoring cadence",
                detail="Define the monitoring cadence and event triggers for this name.",
                category="monitoring",
            )
        )
    if not inputs.decision_journal.strip():
        requirements.append(
            ManualRequirement(
                title="Decision journal entry",
                detail="Create a decision-journal entry before putting capital at risk.",
                category="journal",
            )
        )
    if not inputs.post_mortem_trigger.strip():
        requirements.append(
            ManualRequirement(
                title="Post-mortem trigger",
                detail="Define when the post-mortem should be opened: exit, invalidation, or defined holding-period review.",
                category="post_mortem",
            )
        )
    if not inputs.scenario_cases:
        requirements.append(
            ManualRequirement(
                title="Scenario EV cases",
                detail="Enter bull/base/bear probabilities and payoffs so the scenario EV panel is explicit.",
                category="scenario_ev",
            )
        )

    return requirements


def _aggregate_status(
    industry: WorkstreamResult,
    company: WorkstreamResult,
    setup: WorkstreamResult,
    manual_requirements: list[ManualRequirement],
) -> AssessmentStatus:
    statuses = [industry.status, company.status, setup.status]
    if AssessmentStatus.FAILED in statuses:
        return AssessmentStatus.FAILED
    if manual_requirements or AssessmentStatus.MANUAL_REVIEW_REQUIRED in statuses:
        return AssessmentStatus.MANUAL_REVIEW_REQUIRED
    if AssessmentStatus.NOT_ASSESSED in statuses:
        return AssessmentStatus.NOT_ASSESSED
    return AssessmentStatus.PASSED


def primary_reason(assessment: CandidateAssessment) -> str:
    ordered_workstreams = [
        assessment.company,
        assessment.industry,
        assessment.setup,
    ]
    for workstream in ordered_workstreams:
        for check in workstream.checks:
            if check.status == AssessmentStatus.FAILED:
                return f"{workstream.name}: {check.name} — {check.detail}"
    for workstream in ordered_workstreams:
        for check in workstream.checks:
            if check.status == AssessmentStatus.MANUAL_REVIEW_REQUIRED:
                return f"{workstream.name}: {check.name} — {check.detail}"
    for workstream in ordered_workstreams:
        for check in workstream.checks:
            if check.status == AssessmentStatus.NOT_ASSESSED:
                return f"{workstream.name}: {check.name} — {check.detail}"
    return "All automated checks passed in the free-tier default path."


def synthesize_candidate(
    stock_id: str,
    strategy_mode: StrategyMode,
    industry: WorkstreamResult,
    company: WorkstreamResult,
    setup: WorkstreamResult,
    inputs: Optional[SynthesisInputs] = None,
    sizing_band: Optional[SizingBand] = None,
    thesis_stub: str = "",
) -> CandidateAssessment:
    inputs = inputs or SynthesisInputs()
    manual_requirements = _dedupe_manual_requirements(
        industry.manual_requirements
        + company.manual_requirements
        + setup.manual_requirements
        + _required_synthesis_items(strategy_mode, inputs, sizing_band)
    )

    assessment = CandidateAssessment(
        stock_id=stock_id,
        strategy_mode=strategy_mode,
        industry=industry,
        company=company,
        setup=setup,
        status=_aggregate_status(industry, company, setup, manual_requirements),
        composite_score=_composite_score(industry, company, setup),
        thesis_stub=thesis_stub or inputs.thesis.strip() or _auto_thesis_stub(stock_id, industry, company, setup),
        sizing_band=sizing_band,
        manual_requirements=manual_requirements,
        monitoring_cadence=inputs.monitoring_cadence.strip() or "weekly review + event-driven alerts",
        metadata={
            "variant_perception": inputs.variant_perception.strip(),
            "invalidation": inputs.invalidation.strip(),
            "catalyst": inputs.catalyst.strip(),
            "milestone": inputs.milestone.strip(),
            "conviction_tier": inputs.conviction_tier.strip(),
            "management_forensic": inputs.management_forensic.strip(),
            "scuttlebutt_memo": inputs.scuttlebutt_memo.strip(),
            "pre_mortem": inputs.pre_mortem.strip(),
            "exit_archetype": inputs.exit_archetype.strip(),
            "decision_journal": inputs.decision_journal.strip(),
            "post_mortem_trigger": inputs.post_mortem_trigger.strip(),
            "scenario_cases": list(inputs.scenario_cases),
        },
    )
    assessment.metadata["primary_reason"] = primary_reason(assessment)
    return assessment
