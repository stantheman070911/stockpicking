import unittest

import pandas as pd

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


class TriageSuspensionTests(unittest.TestCase):
    def test_missing_resumption_date_fails_triage_as_active_suspension(self) -> None:
        result = triage.run(DummyTriageClient(), stock_id="2330")

        self.assertFalse(result.passed)
        suspension_check = next(check for check in result.checks if check.name == "Trading suspension")
        self.assertFalse(suspension_check.passed)
        self.assertIn("Currently suspended", suspension_check.detail)


if __name__ == "__main__":
    unittest.main()
