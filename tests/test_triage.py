import unittest

import pandas as pd

from taiwan_equity_toolkit.client import PremiumDatasetRequired
from taiwan_equity_toolkit.states import Status
from taiwan_equity_toolkit import triage


class DummyTriageClient:
    def get(self, dataset: str, stock_id: str, start_date: str):
        if dataset == "TaiwanStockDispositionSecuritiesPeriod":
            return pd.DataFrame()
        if dataset == "TaiwanStockSuspended":
            return pd.DataFrame([
                {"date": "2026-04-10", "stock_id": stock_id, "resumption_date": None}
            ])
        if dataset == "TaiwanStockCapitalReductionReferencePrice":
            return pd.DataFrame()
        raise AssertionError(f"unexpected dataset {dataset}")

    def price(self, stock_id: str, start_date: str):
        return pd.DataFrame([
            {"date": f"2026-03-{day:02d}", "Trading_money": 100_000_000}
            for day in range(1, 26)
        ])

    def financial_statements(self, stock_id: str, start_date: str):
        return pd.DataFrame([
            {"date": "2026-03-31", "stock_id": stock_id, "type": "Revenue", "value": 1000},
            {"date": "2026-03-31", "stock_id": stock_id, "type": "IncomeAfterTax", "value": 100},
        ])

    def monthly_revenue(self, stock_id: str, start_date: str):
        return pd.DataFrame([
            {"date": f"2025-{month:02d}-01", "stock_id": stock_id, "revenue": 100}
            for month in range(1, 13)
        ] + [
            {"date": "2026-01-01", "stock_id": stock_id, "revenue": 105},
        ])


class DispositionErrorClient(DummyTriageClient):
    def get(self, dataset: str, stock_id: str, start_date: str):
        if dataset == "TaiwanStockDispositionSecuritiesPeriod":
            raise RuntimeError("upstream unavailable")
        return super().get(dataset, stock_id, start_date)


class ShortRevenueHistoryClient(DummyTriageClient):
    def get(self, dataset: str, stock_id: str, start_date: str):
        if dataset == "TaiwanStockSuspended":
            return pd.DataFrame()
        return super().get(dataset, stock_id, start_date)

    def monthly_revenue(self, stock_id: str, start_date: str):
        return pd.DataFrame([
            {"date": f"2025-{month:02d}-01", "stock_id": stock_id, "revenue": 100}
            for month in range(1, 13)
        ])


class CleanPremiumCheckClient(DummyTriageClient):
    def get(self, dataset: str, stock_id: str, start_date: str):
        if dataset == "TaiwanStockSuspended":
            return pd.DataFrame()
        return super().get(dataset, stock_id, start_date)


class PremiumDatasetGapClient(CleanPremiumCheckClient):
    def get(self, dataset: str, stock_id: str, start_date: str):
        if dataset in {"TaiwanStockDispositionSecuritiesPeriod", "TaiwanStockSuspended"}:
            raise PremiumDatasetRequired(f"{dataset} requires premium tier")
        return super().get(dataset, stock_id, start_date)


class TriageSuspensionTests(unittest.TestCase):
    def test_missing_resumption_date_fails_triage_as_active_suspension(self) -> None:
        result = triage.run(DummyTriageClient(), stock_id="2330")

        self.assertFalse(result.passed)
        suspension_check = next(check for check in result.checks if check.name == "Trading suspension")
        self.assertFalse(suspension_check.passed)
        self.assertIn("Currently suspended", suspension_check.detail)

    def test_unavailable_disposition_check_fails_closed(self) -> None:
        result = triage.run(DispositionErrorClient(), stock_id="2330")

        self.assertFalse(result.passed)
        disposition_check = next(check for check in result.checks if check.name == "Disposition status")
        self.assertFalse(disposition_check.passed)
        self.assertIn("unavailable", disposition_check.detail)

    def test_premium_dataset_gaps_do_not_fail_triage(self) -> None:
        result = triage.run(PremiumDatasetGapClient(), stock_id="2330")

        self.assertTrue(result.passed)
        disposition_check = next(check for check in result.checks if check.name == "Disposition status")
        suspension_check = next(check for check in result.checks if check.name == "Trading suspension")
        self.assertTrue(disposition_check.passed)
        self.assertTrue(suspension_check.passed)
        self.assertEqual(disposition_check.status, Status.NOT_ASSESSED)
        self.assertEqual(suspension_check.status, Status.NOT_ASSESSED)
        self.assertIn("not assessed on free tier", disposition_check.detail)
        self.assertEqual(result.failures(), [])

    def test_missing_monthly_yoy_data_fails_triage(self) -> None:
        result = triage.run(ShortRevenueHistoryClient(), stock_id="2330")

        self.assertFalse(result.passed)
        revenue_check = next(check for check in result.checks if check.name == "Monthly revenue trend")
        self.assertFalse(revenue_check.passed)
        self.assertIn("Could not compute YoY", revenue_check.detail)


if __name__ == "__main__":
    unittest.main()
