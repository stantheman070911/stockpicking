import unittest

from taiwan_equity_toolkit.models import AssessmentStatus, CheckResult, ScreenResultsV2, StrategyMode


class ModelContractTests(unittest.TestCase):
    def test_non_automated_statuses_zero_out_score_weights(self) -> None:
        check = CheckResult(
            name="Premium overlay",
            status=AssessmentStatus.NOT_ASSESSED,
            detail="missing",
            weight=10,
            earned=10,
        )
        self.assertEqual(check.effective_weight, 0.0)
        self.assertEqual(check.effective_earned, 0.0)

    def test_screen_results_serializes_enum_values(self) -> None:
        payload = ScreenResultsV2(
            run_date="2026-04-18",
            strategy_mode=StrategyMode.TACTICAL_LONG_SHORT,
            universe_source="snapshot_fallback",
            universe_as_of="2026-04-17",
            funnel={"started": 1},
            top10=[],
            all_ranked=[],
        ).to_dict()

        self.assertEqual(payload["schema_version"], "v2")
        self.assertEqual(payload["strategy_mode"], "tactical_long_short")


if __name__ == "__main__":
    unittest.main()
