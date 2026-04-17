import json
import re
import unittest
from pathlib import Path
from typing import Any, Set

from taiwan_equity_toolkit.config import INDUSTRY_ANCHORS


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
TEMPLATES_DIR = DATA_DIR / "templates"


def _load_yaml_like_json(path: Path) -> Any:
    # Phase 1 stores YAML artifacts in YAML-1.2-compatible JSON syntax so we
    # can parse them with the standard library and avoid adding a PyYAML dep.
    return json.loads(path.read_text(encoding="utf-8"))


def _collect_stock_ids(node: Any) -> Set[str]:
    found: Set[str] = set()
    if isinstance(node, dict):
        for value in node.values():
            found.update(_collect_stock_ids(value))
    elif isinstance(node, list):
        for value in node:
            found.update(_collect_stock_ids(value))
    elif isinstance(node, str) and node.isdigit():
        found.add(node)
    return found


class CuratedDataTests(unittest.TestCase):
    def test_curated_yaml_files_parse(self) -> None:
        supply_chain = _load_yaml_like_json(DATA_DIR / "taiwan_supply_chain.yaml")
        governance = _load_yaml_like_json(DATA_DIR / "taiwan_governance_redflags.yaml")

        self.assertIn("as_of", supply_chain)
        self.assertIn("clusters", supply_chain)
        self.assertIn("as_of", governance)
        self.assertIn("patterns", governance)

    def test_every_industry_anchor_stock_is_present_in_supply_chain_map(self) -> None:
        supply_chain = _load_yaml_like_json(DATA_DIR / "taiwan_supply_chain.yaml")
        stock_ids = _collect_stock_ids(supply_chain["clusters"])
        expected = {stock_id for stocks in INDUSTRY_ANCHORS.values() for stock_id in stocks}

        self.assertTrue(
            expected.issubset(stock_ids),
            msg=f"Missing supply-chain coverage for: {sorted(expected - stock_ids)}",
        )

    def test_governance_keyword_yaml_has_minimum_pattern_depth(self) -> None:
        governance = _load_yaml_like_json(DATA_DIR / "taiwan_governance_redflags.yaml")
        patterns = governance["patterns"]

        self.assertGreaterEqual(len(patterns), 12)
        for pattern in patterns:
            with self.subTest(pattern=pattern["id"]):
                self.assertIn("keywords", pattern)
                self.assertGreaterEqual(len(pattern["keywords"]), 2)

    def test_templates_exist_and_have_parseable_required_markers(self) -> None:
        expected_templates = {
            "variant_perception.md",
            "scenario_ev.md",
            "position_sizing.md",
            "catalyst_path.md",
            "invalidation.md",
            "pre_mortem.md",
            "decision_journal.md",
            "post_mortem.md",
            "sell_discipline.md",
            "management_forensic_checklist.md",
            "scuttlebutt_call_log.md",
            "red_flag_screen.md",
            "cb_manual_review.md",
        }

        actual_templates = {path.name for path in TEMPLATES_DIR.glob("*.md")}
        self.assertEqual(actual_templates, expected_templates)

        for name in sorted(expected_templates):
            text = (TEMPLATES_DIR / name).read_text(encoding="utf-8")
            markers = re.findall(r"<<REQUIRED>>\s*([^:\n]+):", text)
            with self.subTest(template=name):
                self.assertIn("## Purpose", text)
                self.assertIn("## Required Fields", text)
                self.assertIn("## Guidance", text)
                self.assertIn("## Example", text)
                self.assertGreater(len(markers), 0)

    def test_variant_perception_template_requires_all_phase_one_fields(self) -> None:
        text = (TEMPLATES_DIR / "variant_perception.md").read_text(encoding="utf-8")

        self.assertIn("<<REQUIRED>> Market expectation:", text)
        self.assertIn("<<REQUIRED>> Analyst thesis:", text)
        self.assertIn(
            "<<REQUIRED>> Error type {behavioral / analytical / informational / technical}:",
            text,
        )
        self.assertIn("<<REQUIRED>> Evidence gap:", text)


if __name__ == "__main__":
    unittest.main()
