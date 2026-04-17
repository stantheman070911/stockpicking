"""
Compatibility wrapper for the V2 setup / entry workstream.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from taiwan_equity_toolkit.client import FinMindClient
from taiwan_equity_toolkit.models import AssessmentStatus, SizingBand, StrategyMode
from taiwan_equity_toolkit.workstream_setup import run as run_setup_workstream


LAYER_MAP = {
    "Valuation / expectation gap": "6.5A",
    "Volatility": "6.5B",
    "Portfolio overlap": "6.5B",
    "Liquidity / execution": "6.5C",
    "Crowding / setup": "6.5D",
    "Tick / snapshot overlay": "6.5D",
}


@dataclass
class Gate65Check:
    layer: str
    name: str
    result: str
    detail: str
    status: AssessmentStatus


@dataclass
class Gate65Result:
    stock_id: str
    verdict: str
    status: AssessmentStatus
    checks: list[Gate65Check] = field(default_factory=list)
    green_count: int = 0
    yellow_count: int = 0
    red_count: int = 0
    correlations: dict[str, float] = field(default_factory=dict)
    sizing_band: Optional[SizingBand] = None

    def summary(self) -> str:
        lines = [f"# Gate 6.5 — Entry Architecture: {self.stock_id}"]
        lines.append(
            f"Verdict: {self.verdict} ({self.status.value}) "
            f"(Green {self.green_count} / Yellow {self.yellow_count} / Red {self.red_count})"
        )
        current_layer = None
        for check in self.checks:
            if check.layer != current_layer:
                lines.append("")
                lines.append(f"## {check.layer}")
                current_layer = check.layer
            mark = {"Green": "✓", "Yellow": "⚠", "Red": "✗"}[check.result]
            lines.append(f"  {mark} {check.name}: {check.detail} [{check.status.value}]")
        if self.correlations:
            lines.append("")
            lines.append("## Correlation to existing book")
            for stock_id, corr in self.correlations.items():
                lines.append(f"  - {stock_id}: {corr:+.2f}")
        if self.sizing_band:
            lines.append("")
            lines.append(
                f"## Mechanical sizing band\n"
                f"  {self.sizing_band.min_pct:.2f}%–{self.sizing_band.max_pct:.2f}% "
                f"(suggested {self.sizing_band.suggested_pct:.2f}%)"
            )
        return "\n".join(lines)


def _traffic_light(status: AssessmentStatus) -> str:
    if status == AssessmentStatus.PASSED:
        return "Green"
    if status == AssessmentStatus.FAILED:
        return "Red"
    return "Yellow"


def run(
    client: FinMindClient,
    stock_id: str,
    existing_book: Optional[list[str]] = None,
    intended_position_ntd: Optional[float] = None,
    cfg=None,
) -> Gate65Result:
    del intended_position_ntd, cfg
    setup, extras = run_setup_workstream(
        client,
        stock_id=stock_id,
        strategy_mode=StrategyMode.TACTICAL_LONG_SHORT,
        existing_book=existing_book,
    )

    checks = [
        Gate65Check(
            layer=LAYER_MAP.get(check.name, "6.5D"),
            name=check.name,
            result=_traffic_light(check.status),
            detail=check.detail,
            status=check.status,
        )
        for check in setup.checks
    ]

    greens = len([check for check in checks if check.result == "Green"])
    yellows = len([check for check in checks if check.result == "Yellow"])
    reds = len([check for check in checks if check.result == "Red"])
    correlations = {}
    if extras.get("max_corr_id") is not None and extras.get("max_corr") is not None:
        correlations[str(extras["max_corr_id"])] = float(extras["max_corr"])

    return Gate65Result(
        stock_id=stock_id,
        verdict=str(extras["entry_verdict"]),
        status=setup.status,
        checks=checks,
        green_count=greens,
        yellow_count=yellows,
        red_count=reds,
        correlations=correlations,
        sizing_band=extras.get("sizing_band"),
    )
