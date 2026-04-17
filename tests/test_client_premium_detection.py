import unittest
from unittest.mock import patch

import pandas as pd

from taiwan_equity_toolkit.client import (
    FinMindClient,
    FinMindError,
    PremiumDatasetRequired,
    is_premium,
)


class FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code
        self.text = str(payload)

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise FinMindError(f"HTTP {self.status_code}")


class ClientPremiumDetectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = FinMindClient(token="test-token")

    def test_is_premium_identifies_known_premium_datasets(self) -> None:
        datasets = {
            "TaiwanStockIndustryChain",
            "TaiwanBusinessIndicator",
            "TaiwanStockDispositionSecuritiesPeriod",
            "TaiwanStockSuspended",
            "TaiwanStockConvertibleBondInfo",
            "TaiwanStockConvertibleBondDaily",
            "TaiwanStockConvertibleBondInstitutionalInvestors",
            "TaiwanStockConvertibleBondDailyOverview",
            "TaiwanStockTradingDailyReport",
            "TaiwanstockGovernmentBankBuySell",
            "TaiwanStockMarketValue",
            "TaiwanStockMarketValueWeight",
            "TaiwanStockPriceTick",
            "CnnFearGreedIndex",
        }

        for dataset in datasets:
            with self.subTest(dataset=dataset):
                self.assertTrue(is_premium(dataset))
                self.assertTrue(FinMindClient.is_premium(dataset))

    def test_is_premium_does_not_flag_free_tier_dataset(self) -> None:
        self.assertFalse(is_premium("TaiwanStockPrice"))
        self.assertFalse(FinMindClient.is_premium("TaiwanStockMonthRevenue"))

    def test_get_raises_premium_dataset_required_before_http_call(self) -> None:
        with patch("taiwan_equity_toolkit.client.requests.get") as mock_get:
            with self.assertRaises(PremiumDatasetRequired):
                self.client.get("TaiwanStockIndustryChain")

        mock_get.assert_not_called()

    def test_get_passes_through_for_free_dataset(self) -> None:
        response = FakeResponse(
            {
                "status": 200,
                "data": [
                    {
                        "date": "2026-04-18",
                        "stock_id": "2330",
                        "close": 950.0,
                    }
                ],
            }
        )

        with patch("taiwan_equity_toolkit.client.requests.get", return_value=response) as mock_get:
            frame = self.client.get(
                "TaiwanStockPrice",
                stock_id="2330",
                start_date="2026-04-01",
                end_date="2026-04-18",
            )

        self.assertIsInstance(frame, pd.DataFrame)
        self.assertEqual(frame.iloc[0]["stock_id"], "2330")
        mock_get.assert_called_once()


if __name__ == "__main__":
    unittest.main()
