import unittest
from typing import Optional

from taiwan_equity_toolkit import parsers
from taiwan_equity_toolkit.config import DEFAULT_CONFIG
from taiwan_equity_toolkit.gate3 import (
    HardFailFinding,
    SubLayerScore,
    _check_hard_fails,
    _check_persistent_cfo_ni_divergence,
)


def make_income(date: str, net_income: Optional[float]) -> parsers.IncomeStatement:
    return parsers.IncomeStatement(date=date, stock_id="2330", net_income=net_income)


def make_cash(date: str, cfo: Optional[float]) -> parsers.CashFlow:
    return parsers.CashFlow(date=date, stock_id="2330", cfo=cfo)


class Gate3PersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.thresholds = DEFAULT_CONFIG.gate3_thresholds
        self.dates = ["2024-03-31", "2024-06-30", "2024-09-30", "2024-12-31"]

    def test_persistent_cfo_ni_divergence_triggers_after_four_weak_quarters(self) -> None:
        income = [make_income(date, 100.0) for date in self.dates]
        cash = [make_cash(date, 40.0) for date in self.dates]

        triggered, detail = _check_persistent_cfo_ni_divergence(income, cash, self.thresholds)

        self.assertTrue(triggered)
        self.assertIn("4 consecutive quarters", detail)

    def test_three_weak_quarters_do_not_trigger_hard_fail(self) -> None:
        income = [make_income(date, 100.0) for date in self.dates]
        cash = [
            make_cash(self.dates[0], 80.0),
            make_cash(self.dates[1], 40.0),
            make_cash(self.dates[2], 40.0),
            make_cash(self.dates[3], 40.0),
        ]

        triggered, detail = _check_persistent_cfo_ni_divergence(income, cash, self.thresholds)

        self.assertFalse(triggered)
        self.assertIn("max weak streak 3/4", detail)

    def test_missing_quarter_breaks_the_weak_streak(self) -> None:
        income = [make_income(date, 100.0) for date in self.dates]
        cash = [
            make_cash(self.dates[0], 40.0),
            make_cash(self.dates[1], 40.0),
            make_cash(self.dates[3], 40.0),
        ]

        triggered, detail = _check_persistent_cfo_ni_divergence(income, cash, self.thresholds)

        self.assertFalse(triggered)
        self.assertIn("n/a", detail)
        self.assertIn("unverifiable", detail)

    def test_insufficient_computable_history_is_unverifiable(self) -> None:
        income = [make_income(date, 100.0) for date in self.dates[:3]]
        cash = [make_cash(date, 40.0) for date in self.dates[:3]]

        triggered, detail = _check_persistent_cfo_ni_divergence(income, cash, self.thresholds)

        self.assertFalse(triggered)
        self.assertIn("unverifiable", detail)

    def test_low_3c_score_alone_does_not_trigger_cross_data_hard_fail(self) -> None:
        findings = _check_hard_fails(
            income=[],
            cash=[],
            balance=[],
            sub_3a=SubLayerScore("3A", "Operating Quality", 10.0, 25, []),
            sub_3b=SubLayerScore("3B", "Balance Sheet & Cash Survival", 10.0, 35, []),
            sub_3c=SubLayerScore("3C", "Ownership & Market Structure", 5.0, 20, []),
            sub_3e=SubLayerScore(
                "3E",
                "Data Integrity & Event Audit",
                10.0,
                10,
                [{"check": "Monthly↔Quarterly revenue consistency", "points": 5.0, "detail": "ok"}],
            ),
            th=self.thresholds,
        )

        conflict = next(
            finding for finding in findings
            if isinstance(finding, HardFailFinding) and finding.name == "Unresolved cross-data conflict"
        )
        self.assertFalse(conflict.triggered)
        self.assertIn("not a hard-fail", conflict.detail)


if __name__ == "__main__":
    unittest.main()
