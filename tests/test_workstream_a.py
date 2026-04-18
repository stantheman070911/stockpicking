"""Tests for Workstream A — Industry / Macro backdrop (Phase 3).

Covers:
- Happy path across all panels → overall Status.PASSED
- YAML supply-chain lookup for a known stock (2330 → semiconductor/foundry)
- YAML fallback to TaiwanStockInfo.industry_category for unknown stocks
- Macro backdrop composition (4 free-tier datasets)
- Premium-dataset absence
- Missing chain data → chain_position.status == NOT_ASSESSED, overall not FAILED
- Macro fetch exception → macro panel NOT_ASSESSED, overall not FAILED
"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

from taiwan_equity_toolkit import workstream_a
from taiwan_equity_toolkit.client import FinMindError
from taiwan_equity_toolkit.states import Status
from taiwan_equity_toolkit.workstream_a import (
    MacroBackdropPanel,
    run,
    PeerAlignmentPanel,
    SectorTailwindPanel,
    TsmcAnchorPanel,
    ValueChainPositionPanel,
    WorkstreamAResult,
)


# ──────────────────────────────────────────────────────────────────────────
# FakeClient — same shape as tests/test_mass_triage.py
# ──────────────────────────────────────────────────────────────────────────


class FakeClient:
    """FinMind stand-in that records every dataset requested."""

    def __init__(self, responses: Optional[dict[str, object]] = None,
                 per_id_responses: Optional[dict[tuple[str, str], object]] = None):
        self.responses = responses or {}
        # per_id_responses keys are (dataset, data_id). Optional override.
        self.per_id_responses = per_id_responses or {}
        self.calls: list[tuple[str, Optional[str]]] = []

    def _dispatch(self, dataset: str, stock_id: Optional[str] = None):
        self.calls.append((dataset, stock_id))
        # Prefer (dataset, data_id) match if configured.
        if stock_id is not None and (dataset, stock_id) in self.per_id_responses:
            resp = self.per_id_responses[(dataset, stock_id)]
        else:
            resp = self.responses.get(dataset, pd.DataFrame())
        if isinstance(resp, Exception):
            raise resp
        return resp

    def get(self, dataset, stock_id=None, start_date=None, end_date=None):
        return self._dispatch(dataset, stock_id)

    def monthly_revenue(self, stock_id, start_date):
        return self._dispatch("TaiwanStockMonthRevenue", stock_id)

    def stock_info(self):
        return self._dispatch("TaiwanStockInfo", None)

    def get_multi(self, dataset, stock_ids, start_date=None, end_date=None):
        out: dict[str, pd.DataFrame] = {}
        for sid in stock_ids:
            try:
                df = self._dispatch(dataset, sid)
            except Exception:
                continue
            out[sid] = df
        return out


# ──────────────────────────────────────────────────────────────────────────
# Factories
# ──────────────────────────────────────────────────────────────────────────


def _rev_frame(yoy_pct: float = 10.0, months: int = 13) -> pd.DataFrame:
    base = 1_000_000_000.0
    yoy_window = max(1, months - 12)
    revenues = [base] * months
    for idx in range(months - yoy_window, months):
        revenues[idx] = base * (1.0 + yoy_pct / 100.0)
    today = datetime.today()
    dates = [
        (today - timedelta(days=30 * (months - 1 - i))).strftime("%Y-%m-%d")
        for i in range(months)
    ]
    return pd.DataFrame({"date": dates, "revenue": revenues})


def _fs_frame_with_margin(gross_margin_pct: float = 40.0) -> pd.DataFrame:
    """Wide-form FinancialStatements with a single quarter."""
    revenue = 1_000_000.0
    gross_profit = revenue * gross_margin_pct / 100.0
    today_str = datetime.today().strftime("%Y-%m-%d")
    return pd.DataFrame({
        "date": [today_str] * 4,
        "stock_id": ["X"] * 4,
        "type": ["Revenue", "GrossProfit", "OperatingIncome", "IncomeAfterTaxes"],
        "value": [revenue, gross_profit, gross_profit * 0.5, gross_profit * 0.3],
    })


def _flow_frame(net: float = 100_000.0) -> pd.DataFrame:
    today = datetime.today()
    dates = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(10)]
    rows = []
    for d in dates:
        rows.append({"date": d, "name": "Foreign_Investor", "buy": net, "sell": 0})
        rows.append({"date": d, "name": "Investment_Trust", "buy": 0, "sell": 0})
        rows.append({"date": d, "name": "Dealer", "buy": 0, "sell": 0})
    return pd.DataFrame(rows)


def _stock_info(stock_id: str = "1234", category: str = "Semiconductor") -> pd.DataFrame:
    return pd.DataFrame({
        "stock_id": [stock_id, "9999", "8888"],
        "industry_category": [category, category, "Other"],
        "type": ["twse", "twse", "twse"],
    })


def _interest_rate_frame(rate: float = 5.25) -> pd.DataFrame:
    today = datetime.today()
    dates = [(today - timedelta(days=i * 30)).strftime("%Y-%m-%d") for i in range(6, 0, -1)]
    return pd.DataFrame({
        "country": ["US"] * len(dates),
        "date": dates,
        "full_country_name": ["United States"] * len(dates),
        "interest_rate": [rate] * len(dates),
    })


def _bond_yield_frame(value: float) -> pd.DataFrame:
    today = datetime.today()
    dates = [(today - timedelta(days=i * 15)).strftime("%Y-%m-%d") for i in range(12, 0, -1)]
    return pd.DataFrame({
        "date": dates,
        "name": ["yield"] * len(dates),
        "value": [value] * len(dates),
    })


def _wti_frame(price_start: float = 70.0, price_end: float = 80.0) -> pd.DataFrame:
    today = datetime.today()
    # 200 trading days
    n = 200
    dates = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(n - 1, -1, -1)]
    # Simple ramp from start → end
    step = (price_end - price_start) / max(1, n - 1)
    prices = [price_start + step * i for i in range(n)]
    return pd.DataFrame({"date": dates, "name": ["WTI"] * n, "price": prices})


def _twd_frame(spot_start: float = 32.0, spot_end: float = 31.5) -> pd.DataFrame:
    today = datetime.today()
    n = 200
    dates = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(n - 1, -1, -1)]
    step = (spot_end - spot_start) / max(1, n - 1)
    spots = [spot_start + step * i for i in range(n)]
    return pd.DataFrame({
        "date": dates,
        "currency": ["USD"] * n,
        "cash_buy": spots,
        "cash_sell": spots,
        "spot_buy": spots,
        "spot_sell": spots,
    })


def _happy_path_responses(stock_id: str = "2330") -> dict[str, object]:
    return {
        "TaiwanStockMonthRevenue": _rev_frame(yoy_pct=12.0),
        "TaiwanStockFinancialStatements": _fs_frame_with_margin(40.0),
        "TaiwanStockInstitutionalInvestorsBuySell": _flow_frame(net=500_000.0),
        "TaiwanStockInfo": _stock_info(stock_id, category="Semiconductor"),
        "InterestRate": _interest_rate_frame(5.25),
        "GovernmentBondsYield": _bond_yield_frame(4.0),
        "CrudeOilPrices": _wti_frame(70.0, 80.0),
        "TaiwanExchangeRate": _twd_frame(32.0, 31.5),
    }


# The datasets Workstream A must NEVER touch (premium or otherwise out of scope).
def _dataset(*parts: str) -> str:
    return "".join(parts)


FORBIDDEN_DATASETS: frozenset = frozenset(
    {
        _dataset("Taiwan", "BusinessIndicator"),
        _dataset("TaiwanStock", "IndustryChain"),
        _dataset("TaiwanStockDisposition", "SecuritiesPeriod"),
        _dataset("TaiwanStock", "Suspended"),
        _dataset("TaiwanStock", "MarketValue"),
        _dataset("TaiwanStock", "MarketValueWeek"),
        _dataset("TaiwanStock", "MarketValueMonth"),
        _dataset("TaiwanStock", "MarketValueWeight"),
        _dataset("TaiwanStock", "KBar"),
        _dataset("TaiwanStock", "PriceTick"),
        _dataset("TaiwanStockTrading", "DailyReport"),
        _dataset("TaiwanStockTrading", "DailyReportSecIdAgg"),
        _dataset("TaiwanStockConvertible", "BondInfo"),
        _dataset("TaiwanStockConvertible", "BondDaily"),
        _dataset("TaiwanStockConvertible", "BondDailyOverview"),
        _dataset("TaiwanStockConvertible", "BondInstitutionalInvestors"),
        _dataset("TaiwanStock", "10Year"),
        _dataset("TaiwanStock", "HoldingSharesPer"),
        _dataset("Cnn", "FearGreedIndex"),
    }
)


# ──────────────────────────────────────────────────────────────────────────
# Happy path
# ──────────────────────────────────────────────────────────────────────────


class HappyPathTests(unittest.TestCase):
    def test_all_panels_populate_overall_passed(self) -> None:
        client = FakeClient(_happy_path_responses("2330"))
        result = run(client, "2330")

        self.assertIsInstance(result, WorkstreamAResult)
        self.assertEqual(result.stock_id, "2330")
        self.assertEqual(result.status, Status.PASSED)
        # Panels must all be populated dataclasses.
        self.assertIsInstance(result.sector_signal, SectorTailwindPanel)
        self.assertIsInstance(result.chain_position, ValueChainPositionPanel)
        self.assertIsInstance(result.tsmc_anchor, TsmcAnchorPanel)
        self.assertIsInstance(result.peer_alignment, PeerAlignmentPanel)
        self.assertIsInstance(result.macro_backdrop, MacroBackdropPanel)


# ──────────────────────────────────────────────────────────────────────────
# Sector tailwind specifics
# ──────────────────────────────────────────────────────────────────────────


class SectorTailwindPanelTests(unittest.TestCase):
    def test_sector_signal_populates_three_month_average_when_history_is_long_enough(self) -> None:
        responses = _happy_path_responses("2330")
        responses["TaiwanStockMonthRevenue"] = _rev_frame(yoy_pct=12.0, months=15)
        client = FakeClient(responses)

        result = run(client, "2330")

        self.assertEqual(result.sector_signal.status, Status.PASSED)
        self.assertAlmostEqual(result.sector_signal.candidate_yoy_12m, 12.0)
        self.assertAlmostEqual(result.sector_signal.candidate_yoy_3m, 12.0)


# ──────────────────────────────────────────────────────────────────────────
# YAML supply-chain lookup
# ──────────────────────────────────────────────────────────────────────────


class ValueChainPositionTests(unittest.TestCase):
    def test_known_stock_resolves_to_cluster_and_node(self) -> None:
        client = FakeClient(_happy_path_responses("2330"))
        result = run(client, "2330")
        self.assertEqual(result.cluster, "semiconductor")
        self.assertEqual(result.chain_position.cluster, "semiconductor")
        self.assertEqual(result.chain_position.node, "foundry")
        # Downstream from YAML: foundry → ["idm", "osat", "ic_design"]
        # Each of those expands into stock IDs.
        expected_downstream_nodes = {"idm", "osat", "ic_design"}
        # Collect peer ids from the fixtures by expanding the YAML nodes.
        downstream_peers = set(result.chain_position.downstream_peers)
        # At minimum expect some OSAT peers (e.g. 2308, 3711).
        self.assertTrue(downstream_peers & {"2308", "3711", "6239", "2449"})
        # Chain status must be PASSED when we found the stock.
        self.assertEqual(result.chain_position.status, Status.PASSED)

    def test_unknown_stock_falls_back_to_industry_category(self) -> None:
        # 9999 is not in the YAML but present in TaiwanStockInfo with a shared category.
        responses = _happy_path_responses("9999")
        responses["TaiwanStockInfo"] = pd.DataFrame({
            "stock_id": ["9999", "8888", "7777", "1111"],
            "industry_category": ["Textile", "Textile", "Textile", "Other"],
            "type": ["twse", "twse", "twse", "twse"],
        })
        client = FakeClient(responses)
        result = run(client, "9999")
        # Fallback: cluster = category; node = None.
        self.assertEqual(result.chain_position.cluster, "Textile")
        self.assertIsNone(result.chain_position.node)
        self.assertEqual(result.chain_position.source, "industry_category_fallback")
        # Peers should be other stocks in the same category.
        peers = set(result.chain_position.downstream_peers) | set(
            result.chain_position.upstream_peers
        )
        self.assertEqual(peers, {"8888", "7777"})
        # Chain position should still be PASSED or NOT_ASSESSED (fallback used),
        # but must NEVER be FAILED.
        self.assertNotEqual(result.chain_position.status, Status.FAILED)

    def test_duplicate_stock_info_rows_pick_non_blank_category_deterministically(self) -> None:
        responses = _happy_path_responses("9999")
        responses["TaiwanStockInfo"] = pd.DataFrame(
            {
                "stock_id": ["9999", "9999", "8888"],
                "industry_category": ["", "Textile", "Textile"],
                "type": ["otc", "twse", "twse"],
            }
        )
        client = FakeClient(responses)

        result = run(client, "9999")

        self.assertEqual(result.chain_position.cluster, "Textile")
        self.assertIn("Multiple TaiwanStockInfo rows found", " ".join(result.chain_position.notes))

    def test_completely_unresolvable_is_not_assessed(self) -> None:
        responses = _happy_path_responses("7777")
        responses["TaiwanStockInfo"] = pd.DataFrame()  # no info at all
        client = FakeClient(responses)
        result = run(client, "7777")
        self.assertEqual(result.chain_position.status, Status.NOT_ASSESSED)
        # Overall must NOT be FAILED.
        self.assertNotEqual(result.status, Status.FAILED)


# ──────────────────────────────────────────────────────────────────────────
# Macro backdrop composition
# ──────────────────────────────────────────────────────────────────────────


class MacroBackdropTests(unittest.TestCase):
    def test_all_four_datasets_populate_panel_passes(self) -> None:
        client = FakeClient(_happy_path_responses("2330"))
        result = run(client, "2330")
        macro = result.macro_backdrop
        self.assertEqual(macro.status, Status.PASSED)
        self.assertIsNotNone(macro.fed_rate_latest)
        self.assertIsNotNone(macro.wti_trend_pct)
        self.assertIsNotNone(macro.twd_trend_pct)
        self.assertIsNotNone(macro.ust_2y10y_spread)

    def test_macro_fetch_exception_surfaces_not_assessed(self) -> None:
        responses = _happy_path_responses("2330")
        responses["InterestRate"] = FinMindError("boom")
        responses["GovernmentBondsYield"] = FinMindError("boom")
        responses["CrudeOilPrices"] = FinMindError("boom")
        responses["TaiwanExchangeRate"] = FinMindError("boom")
        client = FakeClient(responses)
        result = run(client, "2330")
        # Macro panel itself should be NOT_ASSESSED or MANUAL_REVIEW_REQUIRED, never FAILED.
        self.assertIn(result.macro_backdrop.status,
                      (Status.NOT_ASSESSED, Status.MANUAL_REVIEW_REQUIRED))
        self.assertNotEqual(result.status, Status.FAILED)

    def test_trend_pct_uses_datetime_order_not_lexicographic_string_order(self) -> None:
        df = pd.DataFrame(
            {
                "date": ["2026-1-01", "2026-6-01", "2026-10-01"],
                "price": [100.0, 110.0, 120.0],
            }
        )

        trend = workstream_a._trend_pct(df, "price", lookback_days=200)

        self.assertAlmostEqual(trend, 20.0)


# ──────────────────────────────────────────────────────────────────────────
# Premium-dataset absence
# ──────────────────────────────────────────────────────────────────────────


class PremiumDatasetAbsenceTests(unittest.TestCase):
    def test_no_premium_dataset_is_called(self) -> None:
        client = FakeClient(_happy_path_responses("2330"))
        run(client, "2330")
        called_datasets = {dataset for dataset, _ in client.calls}
        overlap = called_datasets & FORBIDDEN_DATASETS
        self.assertEqual(overlap, set(), f"Workstream A called forbidden datasets: {overlap}")


# ──────────────────────────────────────────────────────────────────────────
# Missing chain data does not fail overall
# ──────────────────────────────────────────────────────────────────────────


class GracefulDegradationTests(unittest.TestCase):
    def test_missing_chain_data_does_not_fail_overall(self) -> None:
        responses = _happy_path_responses("7777")
        responses["TaiwanStockInfo"] = pd.DataFrame()  # nothing
        client = FakeClient(responses)
        result = run(client, "7777")
        self.assertEqual(result.chain_position.status, Status.NOT_ASSESSED)
        self.assertNotEqual(result.status, Status.FAILED)

    def test_revenue_fetch_exception_does_not_fail_overall(self) -> None:
        responses = _happy_path_responses("2330")
        responses["TaiwanStockMonthRevenue"] = RuntimeError("fetch err")
        client = FakeClient(responses)
        result = run(client, "2330")
        # Sector signal degrades but overall does not FAIL.
        self.assertNotEqual(result.status, Status.FAILED)

    def test_peer_alignment_with_only_candidate_data_requires_manual_review(self) -> None:
        responses = {
            "TaiwanStockMonthRevenue": pd.DataFrame(),
            "TaiwanStockFinancialStatements": pd.DataFrame(),
            "TaiwanStockInstitutionalInvestorsBuySell": pd.DataFrame(),
        }
        per_id_responses = {
            ("TaiwanStockMonthRevenue", "2330"): _rev_frame(yoy_pct=12.0),
            ("TaiwanStockFinancialStatements", "2330"): _fs_frame_with_margin(40.0),
            ("TaiwanStockInstitutionalInvestorsBuySell", "2330"): _flow_frame(net=500_000.0),
        }
        client = FakeClient(responses=responses, per_id_responses=per_id_responses)

        panel = workstream_a.peer_alignment_panel(
            client=client,
            stock_id="2330",
            chain_peers=["2303"],
            rev_start="2024-01-01",
            fs_start="2024-01-01",
            flow_start="2024-01-01",
        )

        self.assertEqual(panel.status, Status.MANUAL_REVIEW_REQUIRED)
        self.assertEqual(panel.usable_peer_count, 1)

    def test_unexpected_panel_exception_degrades_only_that_panel(self) -> None:
        client = FakeClient(_happy_path_responses("2330"))

        with unittest.mock.patch.object(
            workstream_a,
            "peer_alignment_panel",
            side_effect=ValueError("panel boom"),
        ):
            result = run(client, "2330")

        self.assertEqual(result.sector_signal.status, Status.PASSED)
        self.assertEqual(result.chain_position.status, Status.PASSED)
        self.assertEqual(result.tsmc_anchor.status, Status.PASSED)
        self.assertEqual(result.peer_alignment.status, Status.MANUAL_REVIEW_REQUIRED)
        self.assertEqual(result.macro_backdrop.status, Status.PASSED)
        self.assertEqual(result.status, Status.MANUAL_REVIEW_REQUIRED)
        self.assertIn("peer_alignment raised unexpectedly", " ".join(result.notes))


# ──────────────────────────────────────────────────────────────────────────
# run_all parallel helper
# ──────────────────────────────────────────────────────────────────────────


class RunAllTests(unittest.TestCase):
    def test_run_all_returns_result_per_stock(self) -> None:
        responses = _happy_path_responses("2330")

        def factory():
            return FakeClient(responses)

        results = workstream_a.run_all(client_factory=factory, stock_ids=["2330", "2303"], max_workers=2)
        self.assertEqual(set(results.keys()), {"2330", "2303"})
        for sid, res in results.items():
            self.assertIsInstance(res, WorkstreamAResult)


if __name__ == "__main__":
    unittest.main()
