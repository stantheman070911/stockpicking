import unittest

from taiwan_equity_toolkit import gate3
from tests.support import make_cash_flow_df, make_default_client


class Gate3WrapperTests(unittest.TestCase):
    def test_gate3_downgrades_weak_cfo_to_conditional_watchlist(self) -> None:
        client = make_default_client()
        client.dataset_map["TaiwanStockCashFlowsStatement"]["2330"] = make_cash_flow_df(
            "2330",
            cfo_values=[20.0, 20.0, 20.0, 20.0],
        )

        result = gate3.run(client, stock_id="2330")

        self.assertEqual(result.verdict, "Conditional Watchlist")
        self.assertFalse(result.hard_fail_triggered)
        self.assertTrue(any("CFO/NI" in bullet for bullet in result.risk_bullets))


if __name__ == "__main__":
    unittest.main()
