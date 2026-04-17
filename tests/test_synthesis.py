import unittest

from taiwan_equity_toolkit.models import AssessmentStatus, SizingBand, StrategyMode, WorkstreamResult
from taiwan_equity_toolkit.synthesis import SynthesisInputs, synthesize_candidate


def make_workstream(name: str, status: AssessmentStatus = AssessmentStatus.PASSED, score: float = 80.0) -> WorkstreamResult:
    return WorkstreamResult(name=name, status=status, score=score)


class SynthesisTests(unittest.TestCase):
    def test_tactical_mode_requires_dated_catalyst(self) -> None:
        assessment = synthesize_candidate(
            stock_id="2330",
            strategy_mode=StrategyMode.TACTICAL_LONG_SHORT,
            industry=make_workstream("Industry/Macro"),
            company=make_workstream("Company Quality"),
            setup=make_workstream("Setup/Entry"),
            inputs=SynthesisInputs(
                thesis="AI demand persists",
                variant_perception="Street underestimates mix shift",
                invalidation="Revenue stalls",
            ),
        )

        titles = {req.title for req in assessment.manual_requirements}
        self.assertIn("Dated catalyst", titles)
        self.assertEqual(assessment.status, AssessmentStatus.MANUAL_REVIEW_REQUIRED)

    def test_quality_compounder_can_use_milestone_instead_of_catalyst(self) -> None:
        assessment = synthesize_candidate(
            stock_id="2330",
            strategy_mode=StrategyMode.QUALITY_COMPOUNDER,
            industry=make_workstream("Industry/Macro"),
            company=make_workstream("Company Quality"),
            setup=make_workstream("Setup/Entry"),
            sizing_band=SizingBand(
                min_pct=1.0,
                max_pct=3.0,
                suggested_pct=2.0,
                liquidity_cap_pct=3.0,
                volatility_cap_pct=4.0,
                correlation_cap_pct=5.0,
            ),
            inputs=SynthesisInputs(
                thesis="Quality compounder",
                variant_perception="Margins can stay above consensus",
                invalidation="ROE structurally falls",
                milestone="Margin expansion over the next 4 quarters",
                conviction_tier="B",
                management_forensic="Reviewed",
                scuttlebutt_memo="Checked",
                pre_mortem="Done",
                exit_archetype="Thesis break",
                monitoring_cadence="Monthly",
                decision_journal="Logged",
                post_mortem_trigger="At exit",
                scenario_cases=[{"name": "base", "probability": 1.0, "irr": 12.0}],
            ),
        )

        titles = {req.title for req in assessment.manual_requirements}
        self.assertNotIn("Dated catalyst", titles)
        self.assertEqual(assessment.status, AssessmentStatus.PASSED)


if __name__ == "__main__":
    unittest.main()
