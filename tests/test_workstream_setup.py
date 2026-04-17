import unittest

from taiwan_equity_toolkit.models import AssessmentStatus
from taiwan_equity_toolkit.workstream_setup import run
from tests.support import make_default_client


class WorkstreamSetupTests(unittest.TestCase):
    def test_overlap_becomes_manual_review_not_hard_reject(self) -> None:
        client = make_default_client()

        result, extras = run(client, stock_id="2330", existing_book=["2317"])

        overlap = next(check for check in result.checks if check.name == "Portfolio overlap")
        tick_overlay = next(check for check in result.checks if check.name == "Tick / snapshot overlay")
        self.assertEqual(overlap.status, AssessmentStatus.MANUAL_REVIEW_REQUIRED)
        self.assertEqual(tick_overlay.status, AssessmentStatus.NOT_ASSESSED)
        self.assertEqual(extras["entry_verdict"], "Wait for Setup")
        self.assertIsNotNone(extras["sizing_band"])


if __name__ == "__main__":
    unittest.main()
