"""
Compatibility wrapper for the V2 company-quality workstream.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from taiwan_equity_toolkit import metrics
from taiwan_equity_toolkit.client import FinMindClient
from taiwan_equity_toolkit.models import AssessmentStatus
from taiwan_equity_toolkit.workstream_company import run as run_company_workstream


SUB_LAYER_MAP = {
    "3A": {
        "name": "Operating Quality",
        "checks": {
            "Monthly revenue trajectory",
            "CFO/NI quality",
            "Full forensic — operating quality",
            "Full forensic — cash conversion",
        },
    },
    "3B": {
        "name": "Balance Sheet & Cash Survival",
        "checks": {
            "Financial freshness",
            "Balance-sheet stress",
        },
    },
    "3C": {
        "name": "Ownership & Market Structure",
        "checks": {
            "Tradability",
            "Ownership / crowding",
            "Full forensic — ownership quality",
        },
    },
    "3D": {
        "name": "Capital Structure Overlays",
        "checks": {
            "Capital action watch",
        },
    },
    "3E": {
        "name": "Data Integrity & Governance",
        "checks": {
            "Governance / news red flags",
            "Monthly / quarterly consistency",
            "Full forensic — integrity composite",
        },
    },
}


@dataclass
class SubLayerScore:
    layer: str
    name: str
    score: float
    max_score: int
    components: list[dict] = field(default_factory=list)

    def as_line(self) -> str:
        return f"{self.layer} {self.name}: {self.score:.1f} / {self.max_score}"


@dataclass
class HardFailFinding:
    name: str
    triggered: bool
    detail: str


@dataclass
class Gate3Result:
    stock_id: str
    total_score: float
    verdict: str
    status: AssessmentStatus
    sub_layers: list[SubLayerScore] = field(default_factory=list)
    hard_fails: list[HardFailFinding] = field(default_factory=list)
    hard_fail_triggered: bool = False
    headline_metrics: list[metrics.Metric] = field(default_factory=list)
    thesis_bullets: list[str] = field(default_factory=list)
    risk_bullets: list[str] = field(default_factory=list)
    data_gaps: list[str] = field(default_factory=list)

    def memo(self) -> str:
        lines = [
            f"# Gate 3 — Company Quality: {self.stock_id}",
            f"Score: {self.total_score:.1f} / 100 → {self.verdict} ({self.status.value})",
            "",
            "## Sub-layer scores",
        ]
        for sub_layer in self.sub_layers:
            lines.append(f"- {sub_layer.as_line()}")
        if self.hard_fails:
            lines.append("")
            lines.append("## Triggered red flags")
            for finding in self.hard_fails:
                mark = "⚠" if finding.triggered else "·"
                lines.append(f"- {mark} {finding.name}: {finding.detail}")
        if self.risk_bullets:
            lines.append("")
            lines.append("## Risks / follow-up")
            for bullet in self.risk_bullets:
                lines.append(f"- {bullet}")
        if self.data_gaps:
            lines.append("")
            lines.append("## Data gaps")
            for gap in self.data_gaps:
                lines.append(f"- {gap}")
        return "\n".join(lines)


def _sub_layer_from_checks(layer: str, checks) -> SubLayerScore:
    payload = SUB_LAYER_MAP[layer]
    selected = [check for check in checks if check.name in payload["checks"]]
    score = sum(check.effective_earned for check in selected)
    max_score = int(sum(check.effective_weight for check in selected))
    components = [
        {
            "check": check.name,
            "status": check.status.value,
            "detail": check.detail,
            "points": check.effective_earned,
            "max": check.effective_weight,
        }
        for check in selected
    ]
    return SubLayerScore(
        layer=layer,
        name=payload["name"],
        score=score,
        max_score=max_score,
        components=components,
    )


def run(client: FinMindClient, stock_id: str) -> Gate3Result:
    company = run_company_workstream(client, stock_id=stock_id)
    sub_layers = [_sub_layer_from_checks(layer, company.checks) for layer in ["3A", "3B", "3C", "3D", "3E"]]

    hard_fails = [
        HardFailFinding(name=check.name, triggered=True, detail=check.detail)
        for check in company.checks
        if check.status == AssessmentStatus.FAILED
    ]
    risks = [
        f"{check.name}: {check.detail}"
        for check in company.checks
        if check.status == AssessmentStatus.MANUAL_REVIEW_REQUIRED
    ]
    data_gaps = [
        f"{check.name}: {check.detail}"
        for check in company.checks
        if check.status == AssessmentStatus.NOT_ASSESSED
    ]

    verdict = {
        AssessmentStatus.PASSED: "Pass",
        AssessmentStatus.FAILED: "Fail",
        AssessmentStatus.NOT_ASSESSED: "Conditional Watchlist",
        AssessmentStatus.MANUAL_REVIEW_REQUIRED: "Conditional Watchlist",
    }[company.status]

    return Gate3Result(
        stock_id=stock_id,
        total_score=company.score or 0.0,
        verdict=verdict,
        status=company.status,
        sub_layers=sub_layers,
        hard_fails=hard_fails,
        hard_fail_triggered=company.status == AssessmentStatus.FAILED,
        thesis_bullets=[
            "V2 Gate 3 is a free-tier red-flag framework with conditional forensic escalation.",
        ],
        risk_bullets=risks + [req.detail for req in company.manual_requirements],
        data_gaps=data_gaps,
    )
