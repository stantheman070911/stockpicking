import unittest

import pandas as pd

from taiwan_equity_toolkit import value_chain
from tests.support import DummyFreeTierClient


class LegacyChainClient(DummyFreeTierClient):
    def __init__(self):
        super().__init__(
            dataset_map={
                "TaiwanStockMonthRevenue": {"2303": pd.DataFrame()},
                "TaiwanStockFinancialStatements": {"2303": pd.DataFrame()},
                "TaiwanStockInstitutionalInvestorsBuySell": {"2303": pd.DataFrame()},
            },
            dataset_singletons={
                "TaiwanStockIndustryChain": pd.DataFrame(
                    [
                        {"stock_id": "2330", "industry": "Semiconductor", "sub_industry": "Foundry"},
                        {"stock_id": "2303", "industry": "Semiconductor", "sub_industry": "Foundry"},
                    ]
                )
            },
        )


class ValueChainSignalTests(unittest.TestCase):
    def test_analyze_supports_legacy_industry_chain_fallback(self) -> None:
        report = value_chain.analyze(LegacyChainClient(), stock_id="2330")

        self.assertEqual(report.position.mapping_source, "legacy_industry_chain_fallback")
        self.assertEqual(report.upstream_signals, [])
        self.assertTrue(any("no usable proxy-chain signal data" in note for note in report.notes))


if __name__ == "__main__":
    unittest.main()
