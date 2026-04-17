import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import run_top200_screen as screen
from taiwan_equity_toolkit.models import AssessmentStatus, CandidateAssessment, StrategyMode, WorkstreamResult


class FakeResponse:
    def __init__(self, text: str, status_code: int = 200):
        self.text = text
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def build_taifex_html(stock_ids: list[str]) -> str:
    size = len(stock_ids)
    df = pd.DataFrame(
        {
            "排行": list(range(1, size + 1)),
            "證券名稱": stock_ids,
            "證券名稱.1": [f"Name {idx}" for idx in range(size)],
        }
    )
    return df.to_html(index=False)


def make_assessment(stock_id: str, status: AssessmentStatus, score: float) -> CandidateAssessment:
    workstream = WorkstreamResult(name="Industry/Macro", status=status, score=score)
    company = WorkstreamResult(name="Company Quality", status=status, score=score)
    setup = WorkstreamResult(name="Setup/Entry", status=status, score=score, metadata={"entry_verdict": "Enter Now"})
    return CandidateAssessment(
        stock_id=stock_id,
        strategy_mode=StrategyMode.TACTICAL_LONG_SHORT,
        industry=workstream,
        company=company,
        setup=setup,
        status=status,
        composite_score=score,
        thesis_stub=f"{stock_id} thesis",
    )


class RunTop200ScreenTests(unittest.TestCase):
    def test_fetch_live_universe_parses_ranked_top200(self) -> None:
        stock_ids = [f"{1000 + idx:04d}" for idx in range(screen.UNIVERSE_SIZE)]
        with patch.object(screen.requests, "get", return_value=FakeResponse(build_taifex_html(stock_ids))):
            parsed, metadata = screen.fetch_live_universe(url="https://example.com/taifex")

        self.assertEqual(parsed, stock_ids)
        self.assertEqual(metadata["universe_source"], "live")

    def test_build_universe_uses_snapshot_fallback_when_live_table_is_invalid(self) -> None:
        bad_ids = [f"{2000 + idx:04d}" for idx in range(screen.UNIVERSE_SIZE - 1)] + ["2000"]
        snapshot_ids = [f"{3000 + idx:04d}" for idx in range(screen.UNIVERSE_SIZE)]

        with tempfile.TemporaryDirectory() as tmp_dir:
            snapshot_path = Path(tmp_dir) / "taiex_top200_snapshot.json"
            snapshot_path.write_text(
                json.dumps(
                    {
                        "as_of": "2026-04-17",
                        "source_url": "https://example.com/snapshot",
                        "stock_ids": snapshot_ids,
                    }
                ),
                encoding="utf-8",
            )

            with patch.object(screen.requests, "get", return_value=FakeResponse(build_taifex_html(bad_ids))):
                with patch.object(screen, "SNAPSHOT_PATH", str(snapshot_path)):
                    parsed, metadata = screen.build_universe()

        self.assertEqual(parsed, snapshot_ids)
        self.assertEqual(metadata["universe_source"], "snapshot_fallback")

    def test_run_screen_preserves_v2_statuses_and_funnel(self) -> None:
        class DummyBootstrapClient:
            def __init__(self, token: str):
                self.token = token

            def usage(self):
                return type("Usage", (), {"remaining": 550, "api_request_limit": 600, "user_count": 50})()

            def stock_info(self):
                return pd.DataFrame()

        assessments = [
            make_assessment("2330", AssessmentStatus.PASSED, 88.0),
            make_assessment("2303", AssessmentStatus.MANUAL_REVIEW_REQUIRED, 82.0),
            make_assessment("1101", AssessmentStatus.FAILED, 20.0),
        ]

        with patch.object(screen, "FinMindClient", DummyBootstrapClient):
            with patch.object(screen, "_screen_single_stock", side_effect=assessments):
                payload = screen.run_screen(
                    ["2330", "2303", "1101"],
                    {"universe_source": "snapshot_fallback", "universe_as_of": "2026-04-17"},
                )

        self.assertEqual(payload.top10[0]["stock_id"], "2330")
        self.assertEqual(payload.top10[1]["status"], AssessmentStatus.MANUAL_REVIEW_REQUIRED.value)
        self.assertEqual(payload.funnel["final_failed"], 1)
        self.assertEqual(payload.funnel["ranked_non_failed"], 2)

    def test_main_writes_v2_results(self) -> None:
        payload = screen.ScreenResultsV2(
            run_date="2026-04-18",
            strategy_mode=StrategyMode.TACTICAL_LONG_SHORT,
            universe_source="snapshot_fallback",
            universe_as_of="2026-04-17",
            funnel={"started": 1},
            top10=[{"stock_id": "2330", "status": "passed"}],
            all_ranked=[{"stock_id": "2330", "status": "passed"}],
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            results_path = Path(tmp_dir) / "screen_results.json"
            with patch.object(screen, "build_universe", return_value=(["2330"], {"universe_source": "snapshot_fallback", "universe_as_of": "2026-04-17"})):
                with patch.object(screen, "run_screen", return_value=payload):
                    with patch.object(screen, "RESULTS_PATH", str(results_path)):
                        top10 = screen.main()

            saved = json.loads(results_path.read_text(encoding="utf-8"))
            self.assertEqual(top10[0]["stock_id"], "2330")
            self.assertEqual(saved["schema_version"], "v2")
            self.assertEqual(saved["top10"][0]["stock_id"], "2330")


if __name__ == "__main__":
    unittest.main()
