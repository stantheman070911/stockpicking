import unittest

from taiwan_equity_toolkit.models import AssessmentStatus
from taiwan_equity_toolkit.workstream_company import run
from tests.support import make_cash_flow_df, make_default_client, make_news_df


class WorkstreamCompanyTests(unittest.TestCase):
    def test_low_cfo_to_ni_is_manual_review_not_auto_fail(self) -> None:
        client = make_default_client()
        client.dataset_map["TaiwanStockCashFlowsStatement"]["2330"] = make_cash_flow_df(
            "2330",
            cfo_values=[20.0, 20.0, 20.0, 20.0],
        )
        client.dataset_map["TaiwanStockNews"]["2330"] = make_news_df(["auditor 辭任"])

        result = run(client, stock_id="2330", include_manual_overlay_protocols=True)

        cfo = next(check for check in result.checks if check.name == "CFO/NI quality")
        self.assertEqual(cfo.status, AssessmentStatus.MANUAL_REVIEW_REQUIRED)
        self.assertTrue(result.metadata["full_forensic_triggered"])
        removed_keys = {entry["signal_key"] for entry in result.removed_or_downgraded_signals}
        self.assertIn("broker_branch_fendian", removed_keys)
        self.assertIn("convertible_bond_overlay", removed_keys)


if __name__ == "__main__":
    unittest.main()
