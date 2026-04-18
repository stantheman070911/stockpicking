import json
import os
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from taiwan_equity_toolkit import universe
from taiwan_equity_toolkit.universe import (
    SectorTiltConfig,
    apply_sector_tilt,
    build_universe,
    fetch_live_universe,
    load_snapshot_universe,
    _normalize_stock_ids,
    _parse_taifex_top200_from_table,
    _validate_universe,
)


def _valid_stock_ids(n: int) -> list[str]:
    # Use deterministic 4-digit codes starting at 1000 — avoids collision with
    # curated anchors.
    return [f"{1000 + i:04d}" for i in range(n)]


class NormalizeAndValidateTests(unittest.TestCase):
    def test_normalize_filters_non_four_digit_entries(self) -> None:
        raw = ["2330", 2317, "  2454  ", "abcd", "12", "12345", None, ""]
        out = _normalize_stock_ids(raw)
        self.assertEqual(out, ["2330", "2317", "2454"])

    def test_validate_accepts_exact_size_and_rejects_duplicates(self) -> None:
        ids = _valid_stock_ids(200)
        self.assertEqual(_validate_universe(ids), ids)

        with self.assertRaises(ValueError):
            _validate_universe(ids[:199])

        dupes = ids[:199] + [ids[0]]
        with self.assertRaises(ValueError):
            _validate_universe(dupes)


class ParseTaifexTableTests(unittest.TestCase):
    def test_parses_rank_and_code_pair(self) -> None:
        ranks = list(range(1, 201))
        codes = _valid_stock_ids(200)
        table = pd.DataFrame({"rank": ranks, "code_name": [f"{c} Foo" for c in codes]})
        parsed = _parse_taifex_top200_from_table(table)
        self.assertEqual(parsed, codes)

    def test_raises_when_no_rank_column_matches(self) -> None:
        # Only 5 ranks — well short of 200.
        table = pd.DataFrame({"rank": list(range(1, 6)), "code_name": ["2330 Foo"] * 5})
        with self.assertRaises(ValueError):
            _parse_taifex_top200_from_table(table)


class SnapshotLoaderTests(unittest.TestCase):
    def test_load_snapshot_returns_ids_and_metadata(self) -> None:
        ids = _valid_stock_ids(200)
        payload = {
            "stock_ids": ids,
            "as_of": "2026-01-15",
            "source_url": "https://example.invalid/taifex",
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "snap.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(payload, fh)
            stock_ids, meta = load_snapshot_universe(path)
        self.assertEqual(stock_ids, ids)
        self.assertEqual(meta["universe_source"], "snapshot_fallback")
        self.assertEqual(meta["universe_as_of"], "2026-01-15")
        self.assertEqual(meta["source_url"], "https://example.invalid/taifex")

    def test_load_snapshot_requires_as_of(self) -> None:
        payload = {"stock_ids": _valid_stock_ids(200)}
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "snap.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(payload, fh)
            with self.assertRaises(ValueError):
                load_snapshot_universe(path)


class FetchLiveUniverseTests(unittest.TestCase):
    def test_fetch_live_universe_parses_html_table(self) -> None:
        codes = _valid_stock_ids(200)
        html_rows = "".join(
            f"<tr><td>{rank}</td><td>{code} Foo</td></tr>"
            for rank, code in enumerate(codes, start=1)
        )
        html = f"<table><tr><th>rank</th><th>code_name</th></tr>{html_rows}</table>"

        class DummyResponse:
            def __init__(self, text: str):
                self.text = text
                self.status_code = 200

            def raise_for_status(self) -> None:
                return None

        with patch("taiwan_equity_toolkit.universe.requests.get", return_value=DummyResponse(html)):
            stock_ids, meta = fetch_live_universe(url="https://example.invalid/taifex")
        self.assertEqual(stock_ids, codes)
        self.assertEqual(meta["universe_source"], "live")
        self.assertEqual(meta["source_url"], "https://example.invalid/taifex")


class BuildUniverseFallbackTests(unittest.TestCase):
    def test_falls_back_to_snapshot_when_live_fails(self) -> None:
        ids = _valid_stock_ids(200)
        snapshot = (ids, {
            "universe_source": "snapshot_fallback",
            "universe_as_of": "2026-02-01",
            "source_url": "https://example.invalid/taifex",
        })

        with patch(
            "taiwan_equity_toolkit.universe.fetch_live_universe",
            side_effect=RuntimeError("no internet"),
        ), patch(
            "taiwan_equity_toolkit.universe.load_snapshot_universe",
            return_value=snapshot,
        ):
            stock_ids, meta = build_universe()

        self.assertEqual(stock_ids, ids)
        self.assertEqual(meta["universe_source"], "snapshot_fallback")
        self.assertIn("fallback_reason", meta)
        self.assertIn("no internet", meta["fallback_reason"])

    def test_raises_when_both_paths_fail(self) -> None:
        with patch(
            "taiwan_equity_toolkit.universe.fetch_live_universe",
            side_effect=RuntimeError("live down"),
        ), patch(
            "taiwan_equity_toolkit.universe.load_snapshot_universe",
            side_effect=OSError("snapshot missing"),
        ):
            with self.assertRaises(RuntimeError):
                build_universe()


class ApplySectorTiltTests(unittest.TestCase):
    def test_disabled_tilt_returns_universe_unchanged_and_empty_notes(self) -> None:
        uni = ["2330", "2317", "2454"]
        out, notes = apply_sector_tilt(uni, tilt=None)
        self.assertEqual(out, uni)
        self.assertEqual(notes, {})

        disabled = SectorTiltConfig(enabled=False, caution_buckets={"x": ["2330"]})
        out2, notes2 = apply_sector_tilt(uni, tilt=disabled)
        self.assertEqual(out2, uni)
        self.assertEqual(notes2, {})

    def test_enabled_tilt_never_excludes_but_annotates(self) -> None:
        uni = ["2330", "2317", "2454", "2603"]
        tilt = SectorTiltConfig(
            enabled=True,
            caution_buckets={"shipping cyclicality": ["2603"]},
            favor_ids=["2330"],
            favor_reason="AI capex tailwind",
        )
        out, notes = apply_sector_tilt(uni, tilt=tilt)

        # Universe is preserved — V2 sector view is annotative, never exclusionary.
        self.assertEqual(out, uni)

        # Only stocks mentioned in a bucket carry an annotation.
        self.assertEqual(set(notes.keys()), {"2603", "2330"})
        self.assertEqual(notes["2603"]["tilt"], "caution")
        self.assertEqual(notes["2603"]["reason"], "shipping cyclicality")
        self.assertEqual(notes["2330"]["tilt"], "favor")
        self.assertEqual(notes["2330"]["reason"], "AI capex tailwind")


if __name__ == "__main__":
    unittest.main()
