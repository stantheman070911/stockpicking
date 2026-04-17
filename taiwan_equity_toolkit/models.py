"""
V2 contracts shared across the free-tier default path and overlay workflows.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Optional


class AssessmentStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    NOT_ASSESSED = "not_assessed"
    MANUAL_REVIEW_REQUIRED = "manual_review_required"


class StrategyMode(str, Enum):
    TACTICAL_LONG_SHORT = "tactical_long_short"
    QUALITY_COMPOUNDER = "quality_compounder"


@dataclass
class CheckResult:
    name: str
    status: AssessmentStatus
    detail: str
    weight: float = 0.0
    earned: float = 0.0
    source: str = ""
    as_of: Optional[str] = None
    signal_key: str = ""
    fallback_behavior: str = "warn-and-continue"
    is_overlay: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def effective_weight(self) -> float:
        if self.status in {AssessmentStatus.PASSED, AssessmentStatus.FAILED}:
            return self.weight
        return 0.0

    @property
    def effective_earned(self) -> float:
        if self.status in {AssessmentStatus.PASSED, AssessmentStatus.FAILED}:
            return min(max(self.earned, 0.0), self.weight)
        return 0.0

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["status"] = self.status.value
        return payload


@dataclass
class ManualRequirement:
    title: str
    detail: str
    category: str
    implementation_mode: str = "manual workflow"
    fallback_behavior: str = "manual_review_required"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class WorkstreamResult:
    name: str
    status: AssessmentStatus
    checks: list[CheckResult] = field(default_factory=list)
    score: Optional[float] = None
    available_weight: float = 0.0
    manual_requirements: list[ManualRequirement] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    removed_or_downgraded_signals: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "score": self.score,
            "available_weight": self.available_weight,
            "checks": [check.to_dict() for check in self.checks],
            "manual_requirements": [req.to_dict() for req in self.manual_requirements],
            "notes": list(self.notes),
            "removed_or_downgraded_signals": list(self.removed_or_downgraded_signals),
            "metadata": dict(self.metadata),
        }

    @property
    def manual_requirement_count(self) -> int:
        return len(self.manual_requirements)

    @property
    def not_assessed_count(self) -> int:
        return len([c for c in self.checks if c.status == AssessmentStatus.NOT_ASSESSED])


@dataclass
class SizingBand:
    min_pct: float
    max_pct: float
    suggested_pct: float
    liquidity_cap_pct: float
    volatility_cap_pct: float
    correlation_cap_pct: float
    conviction_input_required: bool = True
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CandidateAssessment:
    stock_id: str
    strategy_mode: StrategyMode
    industry: WorkstreamResult
    company: WorkstreamResult
    setup: WorkstreamResult
    status: AssessmentStatus
    composite_score: float
    thesis_stub: str = ""
    sizing_band: Optional[SizingBand] = None
    manual_requirements: list[ManualRequirement] = field(default_factory=list)
    monitoring_cadence: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "stock_id": self.stock_id,
            "strategy_mode": self.strategy_mode.value,
            "status": self.status.value,
            "composite_score": self.composite_score,
            "thesis_stub": self.thesis_stub,
            "sizing_band": self.sizing_band.to_dict() if self.sizing_band else None,
            "manual_requirements": [req.to_dict() for req in self.manual_requirements],
            "industry": self.industry.to_dict(),
            "company": self.company.to_dict(),
            "setup": self.setup.to_dict(),
            "monitoring_cadence": self.monitoring_cadence,
            "metadata": dict(self.metadata),
        }


@dataclass
class ScreenResultsV2:
    run_date: str
    strategy_mode: StrategyMode
    universe_source: str
    universe_as_of: str
    funnel: dict[str, int]
    top10: list[dict[str, Any]]
    all_ranked: list[dict[str, Any]]
    removed_or_downgraded_signals: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "v2",
            "run_date": self.run_date,
            "strategy_mode": self.strategy_mode.value,
            "universe_source": self.universe_source,
            "universe_as_of": self.universe_as_of,
            "funnel": dict(self.funnel),
            "top10": list(self.top10),
            "all_ranked": list(self.all_ranked),
            "removed_or_downgraded_signals": list(self.removed_or_downgraded_signals),
            "metadata": dict(self.metadata),
        }
