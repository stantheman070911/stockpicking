import unittest

import pandas as pd

from taiwan_equity_toolkit import metrics, parsers


class MetricsMissingDataTests(unittest.TestCase):
    def test_cfo_to_ni_returns_none_when_trailing_window_has_missing_quarter(self) -> None:
        income = [
            parsers.IncomeStatement(date="2024-03-31", stock_id="2330", net_income=100.0),
            parsers.IncomeStatement(date="2024-06-30", stock_id="2330", net_income=None),
            parsers.IncomeStatement(date="2024-09-30", stock_id="2330", net_income=100.0),
            parsers.IncomeStatement(date="2024-12-31", stock_id="2330", net_income=100.0),
        ]
        cash = [
            parsers.CashFlow(date="2024-03-31", stock_id="2330", cfo=100.0),
            parsers.CashFlow(date="2024-06-30", stock_id="2330", cfo=100.0),
            parsers.CashFlow(date="2024-09-30", stock_id="2330", cfo=100.0),
            parsers.CashFlow(date="2024-12-31", stock_id="2330", cfo=100.0),
        ]

        metric = metrics.cfo_to_ni_ratio(income, cash, 4)

        self.assertIsNone(metric.value)
        self.assertIn("missing quarter", metric.note)

    def test_net_debt_to_ebitda_returns_none_when_depreciation_is_missing(self) -> None:
        balance = [
            parsers.BalanceSheet(
                date="2024-12-31",
                stock_id="2330",
                cash_and_equivalents=100.0,
                short_term_borrowings=200.0,
                long_term_borrowings=300.0,
            )
        ]
        income = [
            parsers.IncomeStatement(date="2024-03-31", stock_id="2330", operating_income=100.0, depreciation=10.0),
            parsers.IncomeStatement(date="2024-06-30", stock_id="2330", operating_income=100.0, depreciation=None),
            parsers.IncomeStatement(date="2024-09-30", stock_id="2330", operating_income=100.0, depreciation=10.0),
            parsers.IncomeStatement(date="2024-12-31", stock_id="2330", operating_income=100.0, depreciation=10.0),
        ]

        metric = metrics.net_debt_to_ebitda(balance, income)

        self.assertIsNone(metric.value)
        self.assertIn("missing quarter", metric.note)

    def test_cfo_to_ni_returns_none_when_only_three_quarters_exist(self) -> None:
        income = [
            parsers.IncomeStatement(date="2024-03-31", stock_id="2330", net_income=100.0),
            parsers.IncomeStatement(date="2024-06-30", stock_id="2330", net_income=100.0),
            parsers.IncomeStatement(date="2024-09-30", stock_id="2330", net_income=100.0),
        ]
        cash = [
            parsers.CashFlow(date="2024-03-31", stock_id="2330", cfo=100.0),
            parsers.CashFlow(date="2024-06-30", stock_id="2330", cfo=100.0),
            parsers.CashFlow(date="2024-09-30", stock_id="2330", cfo=100.0),
        ]

        metric = metrics.cfo_to_ni_ratio(income, cash, 4)

        self.assertIsNone(metric.value)
        self.assertIn("insufficient data", metric.note)

    def test_ttm_requires_a_full_window(self) -> None:
        records = [
            parsers.IncomeStatement(date="2024-03-31", stock_id="2330"),
            parsers.IncomeStatement(date="2024-06-30", stock_id="2330"),
            parsers.IncomeStatement(date="2024-09-30", stock_id="2330"),
        ]

        self.assertEqual(parsers.ttm(records, 4), [])

    def test_institutional_net_flow_uses_stable_prefix_buckets(self) -> None:
        flow_df = pd.DataFrame(
            {
                "date": ["2026-04-01"] * 5,
                "name": [
                    "Foreign_Investor",
                    "Investment_Trust",
                    "Dealer_self",
                    "Dealer_Hedging",
                    "Foreign_Dealer_Self",
                ],
                "buy": [100.0, 50.0, 30.0, 20.0, 999.0],
                "sell": [0.0, 0.0, 0.0, 0.0, 0.0],
            }
        )

        flows = metrics.institutional_net_flow(flow_df, lookback_days=60)

        self.assertEqual(flows["Foreign_Investor"].value, 100.0)
        self.assertEqual(flows["Investment_Trust"].value, 50.0)
        self.assertEqual(flows["Dealer"].value, 50.0)


if __name__ == "__main__":
    unittest.main()
