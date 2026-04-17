import unittest

from taiwan_equity_toolkit.models import StrategyMode
from taiwan_equity_toolkit.sizing import build_sizing_band, scenario_expected_irr


class SizingTests(unittest.TestCase):
    def test_build_sizing_band_respects_mechanical_caps(self) -> None:
        band = build_sizing_band(
            adv_ntd=60_000_000,
            vol_90=32.0,
            max_corr=0.75,
            strategy_mode=StrategyMode.TACTICAL_LONG_SHORT,
        )

        self.assertEqual(band.max_pct, 2.0)
        self.assertTrue(band.conviction_input_required)

    def test_scenario_expected_irr_requires_probabilities_to_sum_to_one(self) -> None:
        with self.assertRaises(ValueError):
            scenario_expected_irr([("bull", 0.7, 30.0), ("bear", 0.2, -10.0)])


if __name__ == "__main__":
    unittest.main()
