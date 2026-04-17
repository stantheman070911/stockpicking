import unittest

from taiwan_equity_toolkit import triage
from taiwan_equity_toolkit.models import AssessmentStatus
from tests.support import make_default_client, make_monthly_revenue_df


class TriageV2Tests(unittest.TestCase):
    def test_position_vs_adv_can_fail_without_using_premium_overlay_datasets(self) -> None:
        client = make_default_client()

        result = triage.run(client, stock_id="2330", intended_position_ntd=50_000_000)

        self.assertFalse(result.passed)
        overlay = next(check for check in result.checks if check.name == "Disposition / suspension overlay")
        self.assertEqual(overlay.status, AssessmentStatus.NOT_ASSESSED)
        position = next(check for check in result.checks if check.name == "Position vs ADV")
        self.assertEqual(position.status, AssessmentStatus.FAILED)

    def test_short_thesis_relaxes_revenue_collapse_from_fail_to_manual_review(self) -> None:
        client = make_default_client()
        client.dataset_map["TaiwanStockMonthRevenue"]["2330"] = make_monthly_revenue_df(
            "2330",
            values=[300.0] * 12 + [180.0] * 12,
        )

        result = triage.run(client, stock_id="2330", short_thesis=True)

        revenue = next(check for check in result.checks if check.name == "Monthly revenue trajectory")
        self.assertEqual(revenue.status, AssessmentStatus.MANUAL_REVIEW_REQUIRED)


if __name__ == "__main__":
    unittest.main()
