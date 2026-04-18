import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

import run_top200_screen as screen


class FakeResponse:
    def __init__(self, text: str, status_code: int = 200):
        self.text = text
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def build_taifex_html(stock_ids: list[str]) -> str:
    size = len(stock_ids)
    df = pd.DataFrame({
        "排行": list(range(1, size + 1)),
        "證券名稱": stock_ids,
        "證券名稱.1": [f"Name {idx}" for idx in range(size)],
        "市值佔 大盤比重": [f"{1 - idx / 10000:.4%}" for idx in range(size)],
        "排行.1": list(range(528, 528 + size)),
        "證券名稱.2": [f"{9000 + idx}" for idx in range(size)],
        "證券名稱.3": [f"Tail {idx}" for idx in range(size)],
        "市值佔 大盤比重.1": [f"{0.01 - idx / 100000:.4%}" for idx in range(size)],
    })
    return df.to_html(index=False)


class RunTop200ScreenTests(unittest.TestCase):
    def test_fetch_live_universe_parses_ranked_top200(self) -> None:
        stock_ids = [f"{1000 + idx:04d}" for idx in range(screen.universe.UNIVERSE_SIZE)]
        with patch.object(screen.universe.requests, "get", return_value=FakeResponse(build_taifex_html(stock_ids))):
            parsed, metadata = screen.universe.fetch_live_universe(url="https://example.com/taifex")

        self.assertEqual(parsed, stock_ids)
        self.assertEqual(metadata["universe_source"], "live")
        self.assertEqual(metadata["source_url"], "https://example.com/taifex")
        self.assertTrue(metadata["universe_as_of"])

    def test_build_universe_uses_snapshot_fallback_when_live_table_is_invalid(self) -> None:
        bad_ids = [f"{2000 + idx:04d}" for idx in range(screen.universe.UNIVERSE_SIZE - 1)] + ["2000"]
        snapshot_ids = [f"{3000 + idx:04d}" for idx in range(screen.universe.UNIVERSE_SIZE)]

        with tempfile.TemporaryDirectory() as tmp_dir:
            snapshot_path = Path(tmp_dir) / "taiex_top200_snapshot.json"
            snapshot_path.write_text(
                json.dumps(
                    {
                        "as_of": "2026-04-17",
                        "source_url": "https://example.com/snapshot",
                        "stock_ids": snapshot_ids,
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with patch.object(screen.universe.requests, "get", return_value=FakeResponse(build_taifex_html(bad_ids))):
                with patch.object(screen.universe, "SNAPSHOT_PATH", str(snapshot_path)):
                    parsed, metadata = screen.build_universe()

        self.assertEqual(parsed, snapshot_ids)
        self.assertEqual(metadata["universe_source"], "snapshot_fallback")
        self.assertEqual(metadata["universe_as_of"], "2026-04-17")
        self.assertIn("duplicate", metadata["fallback_reason"].lower())

    def test_apply_gate1_defaults_to_pass_through_and_no_rejects(self) -> None:
        passers, rejects = screen.apply_gate1(["2603", "2330", "2498"])

        self.assertEqual(passers, ["2603", "2330", "2498"])
        self.assertEqual(rejects, {})

    def test_build_gate1_tilt_can_enable_legacy_bias_without_excluding(self) -> None:
        tilt = screen.build_gate1_tilt(enabled=True)

        passers, tilt_notes = screen.universe.apply_sector_tilt(["2603", "2330", "2498"], tilt)

        self.assertEqual(passers, ["2603", "2330", "2498"])
        self.assertEqual(tilt_notes["2603"]["tilt"], "caution")
        self.assertIn("Shipping", tilt_notes["2603"]["reason"])
        self.assertEqual(tilt_notes["2330"]["tilt"], "favor")

    def test_runner_uses_total_score_and_conditional_watchlist_contract(self) -> None:
        g3_results = {
            "2330": SimpleNamespace(total_score=82.5, verdict="Pass", hard_fail_triggered=False),
            "2303": SimpleNamespace(total_score=71.0, verdict="Conditional Watchlist", hard_fail_triggered=False),
            "1101": SimpleNamespace(total_score=40.0, verdict="Fail", hard_fail_triggered=False),
        }

        passers, conditional = screen.classify_gate3_results(g3_results)
        final = screen.compile_final(
            ["2330"],
            g3_results,
            {"2330": SimpleNamespace(verdict="Enter Now")},
            {"2330": SimpleNamespace(adv_ntd=100_000_000)},
        )

        self.assertEqual(passers, ["2330"])
        self.assertEqual(conditional, ["2303"])
        self.assertEqual(final[0]["gate3_score"], 82.5)

    def test_compile_final_excludes_gate65_rejects(self) -> None:
        final = screen.compile_final(
            ["2330", "2303"],
            {
                "2330": SimpleNamespace(total_score=90.0, verdict="Pass", hard_fail_triggered=False),
                "2303": SimpleNamespace(total_score=85.0, verdict="Pass", hard_fail_triggered=False),
            },
            {
                "2330": SimpleNamespace(verdict="Enter Now"),
                "2303": SimpleNamespace(verdict="Reject for Book Fit"),
            },
            {
                "2330": SimpleNamespace(adv_ntd=100_000_000),
                "2303": SimpleNamespace(adv_ntd=100_000_000),
            },
        )

        self.assertEqual([record["stock_id"] for record in final], ["2330"])

    def test_gate4_requires_populated_peer_rankings(self) -> None:
        comparison = SimpleNamespace(candidate_rankings={"Revenue YoY": (0, 0)})

        passed, reason = screen._evaluate_gate4_comparison(comparison)

        self.assertFalse(passed)
        self.assertIn("Insufficient populated peer metrics", reason)

    def test_gate4_rejects_candidate_that_is_bottom_ranked_repeatedly(self) -> None:
        comparison = SimpleNamespace(
            candidate_rankings={
                "Revenue YoY": (3, 3),
                "Gross margin": (3, 3),
                "Operating margin": (2, 3),
            }
        )

        passed, reason = screen._evaluate_gate4_comparison(comparison)

        self.assertFalse(passed)
        self.assertIn("Bottom-ranked", reason)

    def test_gate4_accepts_candidate_with_real_top_half_strength(self) -> None:
        comparison = SimpleNamespace(
            candidate_rankings={
                "Revenue YoY": (1, 3),
                "Gross margin": (2, 3),
                "Operating margin": (3, 3),
            }
        )

        passed, reason = screen._evaluate_gate4_comparison(comparison)

        self.assertTrue(passed)
        self.assertIn("top-half", reason)

    def test_gate5_rejects_placeholder_upstream_rows(self) -> None:
        class DummyClient:
            def __init__(self, token: str):
                self.token = token

        fake_report = SimpleNamespace(
            position=SimpleNamespace(industries=["Semiconductor"], sub_industries=[]),
            upstream_signals=[
                SimpleNamespace(
                    revenue_yoy=None,
                    institutional_flow_60d=None,
                    margin_direction="unknown",
                )
            ],
        )

        with patch.object(screen, "FinMindClient", DummyClient):
            with patch.object(screen.value_chain, "analyze", return_value=fake_report):
                _, result = screen.run_gate5_single(("token", "2330"))

        self.assertFalse(result["passed"])
        self.assertIn("usable upstream", result["reason"])

    def test_main_keeps_gate1_key_but_gate1_no_longer_rejects(self) -> None:
        class DummyClient:
            def __init__(self, token: str):
                self.token = token

            def usage(self) -> SimpleNamespace:
                return SimpleNamespace(
                    user_count=1,
                    api_request_limit=600,
                    remaining=599,
                    utilization_pct=1 / 600,
                )

        with tempfile.TemporaryDirectory() as tmp_dir:
            results_path = Path(tmp_dir) / "screen_results.json"
            triage_result = SimpleNamespace(adv_ntd=123_000_000, passed=True)
            gate3_result = SimpleNamespace(total_score=88.0, verdict="Pass", hard_fail_triggered=False)
            gate65_result = SimpleNamespace(verdict="Enter Now")
            gate4_result = {"passed": True, "peer_ids": ["2303", "3711"], "comparison": None, "reason": "ok"}
            gate5_result = {"passed": True, "report": None, "reason": "ok"}

            with patch.object(screen, "FinMindClient", DummyClient):
                with patch.object(
                    screen,
                    "build_universe",
                    return_value=(
                        ["2330", "2603"],
                        {"universe_source": "snapshot_fallback", "universe_as_of": "2026-04-17"},
                    ),
                ):
                    with patch.object(
                        screen,
                        "apply_gate1",
                        return_value=(
                            ["2330", "2603"],
                            {},
                        ),
                    ):
                        with patch.object(screen, "run_mass_triage", return_value=(["2330"], {"2330": triage_result})):
                            with patch.object(screen, "run_gate3_batch", return_value=(["2330"], {"2330": gate3_result})):
                                with patch.object(screen, "run_gate4_batch", return_value=(["2330"], {"2330": gate4_result})) as gate4_mock:
                                    with patch.object(screen, "run_gate5_batch", return_value=(["2330"], {"2330": gate5_result})) as gate5_mock:
                                        with patch.object(screen, "run_gate65_batch", return_value=(["2330"], {"2330": gate65_result})) as gate65_mock:
                                            with patch.object(screen, "RESULTS_PATH", str(results_path)):
                                                final = screen.main()

            payload = json.loads(results_path.read_text(encoding="utf-8"))
            self.assertEqual(final[0]["gate3_score"], 88.0)
            self.assertEqual(payload["universe_source"], "snapshot_fallback")
            self.assertEqual(payload["universe_as_of"], "2026-04-17")
            self.assertEqual(payload["gate1_rejects"], {})
            self.assertEqual(payload["funnel"]["gate1_pass"], 2)
            self.assertEqual(payload["funnel"]["gate4_pass"], 1)
            self.assertEqual(payload["funnel"]["gate5_pass"], 1)
            gate4_mock.assert_called_once_with(["2330"])
            gate5_mock.assert_called_once_with(["2330"])
            gate65_mock.assert_called_once_with(["2330"])


if __name__ == "__main__":
    unittest.main()
