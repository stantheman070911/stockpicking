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

    def test_compile_final_annotates_workstream_a_fields(self) -> None:
        from taiwan_equity_toolkit.states import Status
        from taiwan_equity_toolkit.workstream_a import (
            WorkstreamAResult,
            PeerAlignmentPanel,
        )

        wa_result = WorkstreamAResult(
            stock_id="2330",
            status=Status.PASSED,
            cluster="semiconductor",
            peer_alignment=PeerAlignmentPanel(
                status=Status.PASSED,
                candidate="2330",
                peer_ids=["2303", "3711"],
                usable_peer_count=3,
            ),
        )

        final = screen.compile_final(
            ["2330"],
            {"2330": SimpleNamespace(total_score=90.0, verdict="Pass", hard_fail_triggered=False)},
            {"2330": SimpleNamespace(verdict="Enter Now")},
            {"2330": SimpleNamespace(adv_ntd=100_000_000)},
            workstream_a_results={"2330": wa_result},
        )

        self.assertEqual(final[0]["workstream_a_status"], "passed")
        self.assertEqual(final[0]["workstream_a_cluster"], "semiconductor")
        self.assertEqual(final[0]["workstream_a_peer_count"], 3)

    def test_main_uses_workstream_a_and_keeps_top_level_json_contract(self) -> None:
        from taiwan_equity_toolkit.states import Status
        from taiwan_equity_toolkit.workstream_a import (
            WorkstreamAResult,
            PeerAlignmentPanel,
            ValueChainPositionPanel,
        )

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
            wa_result = WorkstreamAResult(
                stock_id="2330",
                status=Status.PASSED,
                cluster="semiconductor",
                chain_position=ValueChainPositionPanel(
                    status=Status.PASSED,
                    cluster="semiconductor",
                    node="foundry",
                    source="supply_chain_yaml",
                ),
                peer_alignment=PeerAlignmentPanel(
                    status=Status.PASSED,
                    candidate="2330",
                    peer_ids=["2303", "3711"],
                    usable_peer_count=3,
                ),
            )

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
                        return_value=(["2330", "2603"], {}),
                    ):
                        with patch.object(screen, "run_mass_triage", return_value=(["2330"], {"2330": triage_result})):
                            with patch.object(screen, "run_gate3_batch", return_value=(["2330"], {"2330": gate3_result})):
                                with patch.object(screen, "run_workstream_a_batch", return_value={"2330": wa_result}) as wa_mock:
                                    with patch.object(screen, "run_gate65_batch", return_value=(["2330"], {"2330": gate65_result})) as gate65_mock:
                                        with patch.object(screen, "RESULTS_PATH", str(results_path)):
                                            final = screen.main()

            payload = json.loads(results_path.read_text(encoding="utf-8"))
            # Top-level contract preserved.
            self.assertIn("funnel", payload)
            self.assertIn("top10", payload)
            self.assertIn("all_ranked", payload)
            self.assertEqual(final[0]["gate3_score"], 88.0)
            self.assertEqual(final[0]["workstream_a_status"], "passed")
            self.assertEqual(final[0]["workstream_a_cluster"], "semiconductor")
            self.assertEqual(payload["universe_source"], "snapshot_fallback")
            self.assertEqual(payload["funnel"]["gate1_pass"], 2)
            self.assertEqual(payload["funnel"]["workstream_a_pass"], 1)
            self.assertIn("workstream_a_notes", payload)
            self.assertIn("2330", payload["workstream_a_notes"])
            self.assertEqual(payload["workstream_a_notes"]["2330"]["cluster"], "semiconductor")
            # Old keys are gone.
            self.assertNotIn("gate4_pass", payload["funnel"])
            self.assertNotIn("gate5_pass", payload["funnel"])
            self.assertNotIn("gate4_failures", payload)
            self.assertNotIn("gate5_failures", payload)

            wa_mock.assert_called_once_with(["2330"])
            gate65_mock.assert_called_once_with(["2330"])


if __name__ == "__main__":
    unittest.main()
