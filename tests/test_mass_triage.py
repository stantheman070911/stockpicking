import unittest
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

from taiwan_equity_toolkit.client import FinMindClient, PremiumDatasetRequired
from taiwan_equity_toolkit import mass_triage
from taiwan_equity_toolkit.mass_triage import MassTriageResult, TriageCheck, run
from taiwan_equity_toolkit.states import Status


# ──────────────────────────────────────────────────────────────────────────
# FakeClient — programmable per-dataset responses without hitting the API
# ──────────────────────────────────────────────────────────────────────────


class FakeClient:
    """FinMind-client stand-in for mass-triage tests.

    ``responses`` maps dataset name → DataFrame OR Exception. Missing entries
    default to an empty DataFrame so the tests only wire up what they care
    about.
    """

    def __init__(self, responses: Optional[dict[str, object]] = None):
        self.responses = responses or {}
        self.calls: list[tuple[str, Optional[str]]] = []

    def _dispatch(self, dataset: str, stock_id: Optional[str] = None):
        self.calls.append((dataset, stock_id))
        resp = self.responses.get(dataset, pd.DataFrame())
        if isinstance(resp, Exception):
            raise resp
        return resp

    # Signatures mirror FinMindClient.
    def get(self, dataset, stock_id=None, start_date=None, end_date=None):
        return self._dispatch(dataset, stock_id)

    def price(self, stock_id, start_date, end_date=None):
        return self._dispatch("TaiwanStockPrice", stock_id)

    def monthly_revenue(self, stock_id, start_date):
        return self._dispatch("TaiwanStockMonthRevenue", stock_id)

    def financial_statements(self, stock_id, start_date):
        return self._dispatch("TaiwanStockFinancialStatements", stock_id)

    def news(self, stock_id, start_date):
        return self._dispatch("TaiwanStockNews", stock_id)

    def stock_info(self):
        return self._dispatch("TaiwanStockInfo", None)


# ──────────────────────────────────────────────────────────────────────────
# Data factories
# ──────────────────────────────────────────────────────────────────────────


def _price_frame(adv_ntd: float, days: int = 30) -> pd.DataFrame:
    # Trading_money is already in NT$ (FinMind convention). Fill with adv_ntd
    # so the mean equals the target ADV exactly.
    today = datetime.today()
    dates = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days - 1, -1, -1)]
    return pd.DataFrame({
        "date": dates,
        "Trading_money": [adv_ntd] * days,
        "close": [100.0] * days,
    })


def _monthly_revenue_frame(yoy_pct: float) -> pd.DataFrame:
    """Build 13 months where month-13's revenue produces the requested YoY."""
    base = 1_000_000_000.0
    latest = base * (1.0 + yoy_pct / 100.0)
    # 13 oldest-first rows. First row is the "year-ago" anchor, last is the latest.
    revenues = [base] + [base] * 11 + [latest]
    today = datetime.today()
    dates = [(today - timedelta(days=30 * (12 - i))).strftime("%Y-%m-%d") for i in range(13)]
    return pd.DataFrame({"date": dates, "revenue": revenues})


def _fs_frame(latest_date: str) -> pd.DataFrame:
    """Minimal financial-statements dataframe that parsers.parse_income_statements can digest.

    parse_income_statements reads the FinMind wide-form (pivoted on `type`).
    We supply exactly one quarter with the bare minimum to make `latest`
    populate.
    """
    return pd.DataFrame({
        "date": [latest_date] * 4,
        "stock_id": ["1234"] * 4,
        "type": ["Revenue", "GrossProfit", "OperatingIncome", "IncomeAfterTaxes"],
        "value": [1_000_000.0, 300_000.0, 150_000.0, 100_000.0],
    })


def _news_frame_with_keyword(kw: str) -> pd.DataFrame:
    return pd.DataFrame({
        "date": ["2026-03-01"],
        "stock_id": ["1234"],
        "title": [f"Some headline mentioning {kw} event"],
        "description": ["Body text"],
    })


def _empty_news() -> pd.DataFrame:
    return pd.DataFrame({"date": [], "stock_id": [], "title": [], "description": []})


def _stock_info_frame(stock_id: str, category: str = "Semiconductor", stock_type: str = "twse") -> pd.DataFrame:
    return pd.DataFrame({
        "stock_id": [stock_id, "9999"],
        "industry_category": [category, "其他"],
        "type": [stock_type, stock_type],
    })


def _happy_path_responses(stock_id: str = "1234") -> dict[str, object]:
    """Baseline map where every check should PASS (or NOT_ASSESSED on premium)."""
    today = datetime.today()
    return {
        "TaiwanStockPrice": _price_frame(adv_ntd=100_000_000),
        "TaiwanStockDelisting": pd.DataFrame(),  # empty = not delisted
        "TaiwanStockMonthRevenue": _monthly_revenue_frame(yoy_pct=10.0),
        "TaiwanStockFinancialStatements": _fs_frame(today.strftime("%Y-%m-%d")),
        "TaiwanStockCapitalReductionReferencePrice": pd.DataFrame(),
        "TaiwanStockParValueChange": pd.DataFrame(),
        "TaiwanStockSplitPrice": pd.DataFrame(),
        "TaiwanStockNews": _empty_news(),
        "TaiwanStockInfo": _stock_info_frame(stock_id),
        # Premium datasets — mass_triage must route these through PremiumDatasetRequired
        "TaiwanStockDispositionSecuritiesPeriod": PremiumDatasetRequired("premium"),
        "TaiwanStockSuspended": PremiumDatasetRequired("premium"),
    }


# ──────────────────────────────────────────────────────────────────────────
# Happy path + overall-status rules
# ──────────────────────────────────────────────────────────────────────────


class HappyPathTests(unittest.TestCase):
    def test_all_checks_pass_or_not_assessed_overall_passes(self) -> None:
        client = FakeClient(_happy_path_responses("1234"))
        result = run(client, "1234", governance_keywords=["掏空"])
        self.assertIsInstance(result, MassTriageResult)
        self.assertEqual(result.status, Status.PASSED)
        self.assertGreaterEqual(result.adv_ntd or 0, 100_000_000 - 1)

        # Premium checks surface as NOT_ASSESSED but must NOT force overall fail.
        na_names = [c.name for c in result.not_assessed()]
        self.assertTrue(any("disposition" in n.lower() for n in na_names))
        self.assertTrue(any("suspension" in n.lower() for n in na_names))
        self.assertEqual(result.failures(), [])


# ──────────────────────────────────────────────────────────────────────────
# Individual check failures
# ──────────────────────────────────────────────────────────────────────────


class CheckFailureTests(unittest.TestCase):
    def _run_with(self, overrides: dict[str, object], **kwargs) -> MassTriageResult:
        responses = _happy_path_responses("1234")
        responses.update(overrides)
        client = FakeClient(responses)
        return run(client, "1234", governance_keywords=["掏空"], **kwargs)

    def test_adv_below_floor_fails_tradability(self) -> None:
        # Default min_adv_ntd is 50M. Use 1M.
        result = self._run_with({"TaiwanStockPrice": _price_frame(adv_ntd=1_000_000)})
        self.assertEqual(result.status, Status.FAILED)
        self.assertTrue(any("Tradability" in c.name and c.status == Status.FAILED for c in result.checks))

    def test_position_over_cap_fails_single_name_exposure(self) -> None:
        # ADV 100M, intended 50M → 50% of ADV > 10% cap.
        responses = _happy_path_responses("1234")
        client = FakeClient(responses)
        result = run(client, "1234", intended_position_ntd=50_000_000, governance_keywords=["掏空"])
        self.assertEqual(result.status, Status.FAILED)
        self.assertTrue(any(
            "Single-name exposure" in c.name and c.status == Status.FAILED
            for c in result.checks
        ))

    def test_delisting_row_fails_active_trading(self) -> None:
        result = self._run_with({
            "TaiwanStockDelisting": pd.DataFrame({
                "date": ["2026-01-15"],
                "stock_id": ["1234"],
                "reason": ["delisted"],
            })
        })
        self.assertEqual(result.status, Status.FAILED)

    def test_monthly_revenue_collapse_fails_survival(self) -> None:
        # -50% YoY breaches default -30% floor.
        result = self._run_with({"TaiwanStockMonthRevenue": _monthly_revenue_frame(yoy_pct=-50.0)})
        self.assertEqual(result.status, Status.FAILED)
        self.assertTrue(any("Survival" in c.name and c.status == Status.FAILED for c in result.checks))

    def test_short_thesis_relaxes_revenue_collapse(self) -> None:
        responses = _happy_path_responses("1234")
        responses["TaiwanStockMonthRevenue"] = _monthly_revenue_frame(yoy_pct=-50.0)
        client = FakeClient(responses)
        result = run(client, "1234", short_thesis=True, governance_keywords=["掏空"])
        # Revenue check should still PASS under short thesis.
        rev_check = next(c for c in result.checks if "Survival" in c.name)
        self.assertEqual(rev_check.status, Status.PASSED)
        self.assertEqual(result.status, Status.PASSED)

    def test_stale_financials_fail_data_freshness(self) -> None:
        stale_date = (datetime.today() - timedelta(days=400)).strftime("%Y-%m-%d")
        result = self._run_with({"TaiwanStockFinancialStatements": _fs_frame(stale_date)})
        self.assertEqual(result.status, Status.FAILED)
        self.assertTrue(any("Data freshness" in c.name and c.status == Status.FAILED for c in result.checks))

    def test_critical_governance_keyword_fails(self) -> None:
        responses = _happy_path_responses("1234")
        responses["TaiwanStockNews"] = _news_frame_with_keyword("掏空")
        client = FakeClient(responses)
        result = run(client, "1234", governance_keywords=["掏空"])
        self.assertEqual(result.status, Status.FAILED)
        gov_check = next(c for c in result.checks if "Governance" in c.name)
        self.assertEqual(gov_check.status, Status.FAILED)

    def test_news_fetch_failure_is_not_assessed_not_failed(self) -> None:
        responses = _happy_path_responses("1234")
        responses["TaiwanStockNews"] = RuntimeError("news 500")
        client = FakeClient(responses)
        result = run(client, "1234", governance_keywords=["掏空"])
        # News failure must NOT hard-fail the stock overall.
        self.assertEqual(result.status, Status.PASSED)
        gov_check = next(c for c in result.checks if "Governance" in c.name)
        self.assertEqual(gov_check.status, Status.NOT_ASSESSED)

    def test_unknown_stock_in_stock_info_fails_business_parse(self) -> None:
        result = self._run_with({
            "TaiwanStockInfo": _stock_info_frame("9999"),  # 1234 absent
        })
        self.assertEqual(result.status, Status.FAILED)
        biz_check = next(c for c in result.checks if "Business parse" in c.name)
        self.assertEqual(biz_check.status, Status.FAILED)

    def test_warrant_category_fails_business_parse(self) -> None:
        result = self._run_with({
            "TaiwanStockInfo": _stock_info_frame("1234", category="權證", stock_type="twse"),
        })
        self.assertEqual(result.status, Status.FAILED)


# ──────────────────────────────────────────────────────────────────────────
# Premium-dataset fallback — NOT_ASSESSED must not fail overall
# ──────────────────────────────────────────────────────────────────────────


class PremiumFallbackTests(unittest.TestCase):
    def test_disposition_premium_required_surfaces_not_assessed(self) -> None:
        client = FakeClient(_happy_path_responses("1234"))
        result = run(client, "1234", governance_keywords=["掏空"])
        disp_check = next(
            c for c in result.checks if "disposition" in c.name.lower()
        )
        self.assertEqual(disp_check.status, Status.NOT_ASSESSED)
        self.assertIn("premium", disp_check.detail.lower())
        # Overall must still be PASSED.
        self.assertEqual(result.status, Status.PASSED)

    def test_suspension_premium_required_surfaces_not_assessed(self) -> None:
        client = FakeClient(_happy_path_responses("1234"))
        result = run(client, "1234", governance_keywords=["掏空"])
        susp_check = next(
            c for c in result.checks if "suspension" in c.name.lower()
        )
        self.assertEqual(susp_check.status, Status.NOT_ASSESSED)
        self.assertEqual(result.status, Status.PASSED)


# ──────────────────────────────────────────────────────────────────────────
# Corporate-action check emits a note, never fails on presence
# ──────────────────────────────────────────────────────────────────────────


class CorporateActionTests(unittest.TestCase):
    def test_capital_reduction_row_adds_note_but_passes(self) -> None:
        responses = _happy_path_responses("1234")
        responses["TaiwanStockCapitalReductionReferencePrice"] = pd.DataFrame({
            "date": ["2025-08-01"],
            "stock_id": ["1234"],
        })
        client = FakeClient(responses)
        result = run(client, "1234", governance_keywords=["掏空"])
        ca_check = next(c for c in result.checks if "Corporate-action" in c.name)
        self.assertEqual(ca_check.status, Status.PASSED)  # annotates, never fails
        self.assertTrue(any("capital reduction" in n.lower() for n in result.notes))
        self.assertEqual(result.status, Status.PASSED)


# ──────────────────────────────────────────────────────────────────────────
# Real client integration — verify no silent HTTP 400
# ──────────────────────────────────────────────────────────────────────────


class RealClientPremiumGateTests(unittest.TestCase):
    def test_mass_triage_routes_premium_through_premium_dataset_required(self) -> None:
        """When wired with a real FinMindClient, mass_triage must surface
        NOT_ASSESSED on premium datasets instead of silently 400-ing."""
        # Use a real (unauthenticated-to-premium) client and capture the error.
        real_client = FinMindClient(token="test-token")

        # Minimal stub: only premium methods should raise PremiumDatasetRequired.
        # Everything else would hit the network — so we patch via monkey-hook on
        # the `get` method to block network calls and simulate empty responses.
        original_get = real_client.get

        def stubbed(dataset, stock_id=None, start_date=None, end_date=None):
            try:
                return original_get(dataset, stock_id, start_date, end_date)
            except PremiumDatasetRequired:
                raise
            except Exception:
                # For non-premium datasets, substitute an empty frame so the
                # test focuses on the premium-gate behaviour, not the network.
                return pd.DataFrame()

        real_client.get = stubbed  # type: ignore[assignment]

        result = run(real_client, "1234", governance_keywords=["掏空"])
        premium_named = [
            c for c in result.checks
            if c.status == Status.NOT_ASSESSED
            and c.source in {"TaiwanStockDispositionSecuritiesPeriod", "TaiwanStockSuspended"}
        ]
        self.assertEqual(len(premium_named), 2)


if __name__ == "__main__":
    unittest.main()
