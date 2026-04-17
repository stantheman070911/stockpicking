import unittest

import pandas as pd

from taiwan_equity_toolkit import value_chain


class EmptySignalClient:
    def industry_chain(self):
        return pd.DataFrame(
            [
                {
                    "stock_id": "2330",
                    "industry": "Semiconductor",
                    "sub_industry": "Foundry",
                },
                {
                    "stock_id": "2303",
                    "industry": "Semiconductor",
                    "sub_industry": "Foundry",
                },
            ]
        )

    def get_multi(self, dataset: str, stock_ids: list[str], start_date: str):
        return {stock_id: pd.DataFrame() for stock_id in stock_ids}


class ValueChainSignalTests(unittest.TestCase):
    def test_analyze_omits_empty_placeholder_signals(self) -> None:
        report = value_chain.analyze(EmptySignalClient(), stock_id="2330")

        self.assertEqual(report.upstream_signals, [])
        self.assertTrue(any("no usable upstream signal data" in note for note in report.notes))


if __name__ == "__main__":
    unittest.main()
