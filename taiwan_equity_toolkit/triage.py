"""
Compatibility wrapper for the V2 company-quality triage subset.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from taiwan_equity_toolkit import metrics
from taiwan_equity_toolkit.client import FinMindClient
from taiwan_equity_toolkit.config import DEFAULT_CONFIG, TriageConfig
from taiwan_equity_toolkit.models import AssessmentStatus
from taiwan_equity_toolkit.workstream_company import run as run_company_workstream


TRIAGE_CHECK_NAMES = {
    "Tradability",
    "Financial freshness",
    "Monthly revenue trajectory",
    "Capital action watch",
}


@dataclass
class TriageCheck:
    name: str
    passed: bool
    detail: str
    source: str = ""
    status: AssessmentStatus = AssessmentStatus.PASSED


@dataclass
class TriageResult:
    stock_id: str
    passed: bool
    status: AssessmentStatus
    checks: list[TriageCheck] = field(default_factory=list)
    adv_ntd: Optional[float] = None
    notes: list[str] = field(default_factory=list)
    score: Optional[float] = None
    available_weight: float = 0.0

    def failures(self) -> list[TriageCheck]:
        return [check for check in self.checks if check.status == AssessmentStatus.FAILED]

    def summary(self) -> str:
        verdict = self.status.value
        lines = [f"Triage verdict: {verdict} ({self.stock_id})"]
        for check in self.checks:
            mark = {
                AssessmentStatus.PASSED: "✓",
                AssessmentStatus.FAILED: "✗",
                AssessmentStatus.NOT_ASSESSED: "?",
                AssessmentStatus.MANUAL_REVIEW_REQUIRED: "!",
            }[check.status]
            lines.append(f"  {mark} {check.name}: {check.detail}")
        if self.notes:
            lines.append("  Notes:")
            for note in self.notes:
                lines.append(f"    - {note}")
        return "\n".join(lines)


def _status_from_checks(checks: list[TriageCheck]) -> AssessmentStatus:
    statuses = [check.status for check in checks]
    if AssessmentStatus.FAILED in statuses:
        return AssessmentStatus.FAILED
    if AssessmentStatus.MANUAL_REVIEW_REQUIRED in statuses:
        return AssessmentStatus.MANUAL_REVIEW_REQUIRED
    if AssessmentStatus.NOT_ASSESSED in statuses:
        return AssessmentStatus.NOT_ASSESSED
    return AssessmentStatus.PASSED


def _position_check(
    client: FinMindClient,
    stock_id: str,
    cfg: TriageConfig,
    intended_position_ntd: Optional[float],
) -> tuple[Optional[TriageCheck], Optional[float]]:
    today = datetime.today()
    price_start = (today - timedelta(days=60)).strftime("%Y-%m-%d")
    adv = metrics.adv_ntd(client.price(stock_id, price_start), lookback=cfg.adv_lookback_days)
    adv_value = adv.value
    if intended_position_ntd is None:
        return None, adv_value
    if adv_value is None or adv_value == 0:
        return (
            TriageCheck(
                name="Position vs ADV",
                passed=False,
                detail="Could not compute ADV for position-sizing sanity check",
                source=adv.source,
                status=AssessmentStatus.NOT_ASSESSED,
            ),
            adv_value,
        )
    pct = intended_position_ntd / adv_value
    if pct > cfg.position_max_pct_of_adv:
        status = AssessmentStatus.FAILED
        detail = (
            f"Intended position {pct*100:.1f}% of ADV exceeds "
            f"{cfg.position_max_pct_of_adv*100:.0f}%"
        )
    else:
        status = AssessmentStatus.PASSED
        detail = f"Intended position {pct*100:.1f}% of ADV"
    return (
        TriageCheck(
            name="Position vs ADV",
            passed=status != AssessmentStatus.FAILED,
            detail=detail,
            source=adv.source,
            status=status,
        ),
        adv_value,
    )


def run(
    client: FinMindClient,
    stock_id: str,
    cfg: Optional[TriageConfig] = None,
    intended_position_ntd: Optional[float] = None,
    short_thesis: bool = False,
) -> TriageResult:
    cfg = cfg or DEFAULT_CONFIG.triage
    company = run_company_workstream(client, stock_id=stock_id)

    checks: list[TriageCheck] = []
    for check in company.checks:
        if check.name not in TRIAGE_CHECK_NAMES:
            continue
        status = check.status
        detail = check.detail
        if short_thesis and check.name == "Monthly revenue trajectory" and status == AssessmentStatus.FAILED:
            status = AssessmentStatus.MANUAL_REVIEW_REQUIRED
            detail = f"{check.detail}; collapse filter relaxed in short-thesis mode"
        checks.append(
            TriageCheck(
                name=check.name,
                passed=status != AssessmentStatus.FAILED,
                detail=detail,
                source=check.source,
                status=status,
            )
        )

    checks.append(
        TriageCheck(
            name="Disposition / suspension overlay",
            passed=True,
            detail="Backer-only disposition and suspension datasets are not assessed in the free-tier default path",
            source="TaiwanStockDispositionSecuritiesPeriod + TaiwanStockSuspended",
            status=AssessmentStatus.NOT_ASSESSED,
        )
    )

    position_check, adv_ntd = _position_check(
        client=client,
        stock_id=stock_id,
        cfg=cfg,
        intended_position_ntd=intended_position_ntd,
    )
    if position_check is not None:
        checks.append(position_check)

    status = _status_from_checks(checks)
    notes = list(company.notes)
    notes.append("Triage in V2 is a compact red-flag screen, not a fail-closed premium-data gate.")

    return TriageResult(
        stock_id=stock_id,
        passed=status != AssessmentStatus.FAILED,
        status=status,
        checks=checks,
        adv_ntd=adv_ntd,
        notes=notes,
        score=company.score,
        available_weight=company.available_weight,
    )
