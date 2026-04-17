import unittest
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

from taiwan_equity_toolkit.models import AssessmentStatus
from taiwan_equity_toolkit.workstream_industry import run
from tests.support import DummyFreeTierClient, make_stock_info_df


class WorkstreamIndustryTests(unittest.TestCase):
    def test_runs_with_proxy_map_and_demotes_business_indicator(self) -> None:
        client = DummyFreeTierClient(dataset_singletons={"TaiwanStockInfo": make_stock_info_df()})
        comparison = SimpleNamespace(
            candidate_rankings={"Revenue YoY": (1, 3), "Gross margin": (2, 3), "Operating margin": (2, 3)},
            institutional_flow_60d=pd.DataFrame([{"stock_id": "2330", "Foreign_Investor": 100, "Investment_Trust": 50, "Dealer": 5}]),
        )
        macro_context = {
            "fx_usd_twd": pd.DataFrame({"date": ["2026-03-01", "2026-04-01"], "spot_sell": [31.8, 32.1]}),
            "us_10y": pd.DataFrame({"date": ["2026-04-01"], "value": [4.2]}),
        }

        with patch("taiwan_equity_toolkit.workstream_industry.peers.compare", return_value=comparison):
            result = run(client, stock_id="2330", stock_info_df=make_stock_info_df(), macro_context=macro_context)

        self.assertEqual(result.status, AssessmentStatus.PASSED)
        business_indicator = next(check for check in result.checks if check.name == "Business indicator timing")
        self.assertEqual(business_indicator.status, AssessmentStatus.NOT_ASSESSED)

    def test_missing_mapping_requires_manual_review(self) -> None:
        stock_info = pd.DataFrame([{"stock_id": "9999", "industry_category": "未知產業"}])
        client = DummyFreeTierClient(dataset_singletons={"TaiwanStockInfo": stock_info})
        macro_context = {
            "fx_usd_twd": pd.DataFrame(),
            "us_10y": pd.DataFrame(),
        }

        result = run(client, stock_id="9999", stock_info_df=stock_info, macro_context=macro_context)

        self.assertEqual(result.status, AssessmentStatus.MANUAL_REVIEW_REQUIRED)
        self.assertTrue(result.manual_requirements)


if __name__ == "__main__":
    unittest.main()
