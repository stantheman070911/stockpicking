import unittest

from taiwan_equity_toolkit.data_policy import DatasetTier, calculate_score, dataset_tier, ensure_point_in_time
from taiwan_equity_toolkit.models import AssessmentStatus, CheckResult


class DataPolicyTests(unittest.TestCase):
    def test_dataset_tier_marks_premium_only_sources(self) -> None:
        self.assertEqual(dataset_tier("TaiwanStockIndustryChain"), DatasetTier.BACKER)

    def test_calculate_score_reweights_away_not_assessed_checks(self) -> None:
        summary = calculate_score(
            [
                CheckResult("a", AssessmentStatus.PASSED, "ok", weight=10, earned=8),
                CheckResult("b", AssessmentStatus.NOT_ASSESSED, "missing", weight=10, earned=10),
            ]
        )

        self.assertEqual(summary.available_weight, 10)
        self.assertEqual(summary.normalized_score, 80.0)

    def test_point_in_time_guard_rejects_future_data(self) -> None:
        with self.assertRaises(ValueError):
            ensure_point_in_time("2026-04-19", "2026-04-18")


if __name__ == "__main__":
    unittest.main()
