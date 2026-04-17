import unittest

from taiwan_equity_toolkit.manual_workflows import workflow_sections


class ManualWorkflowTests(unittest.TestCase):
    def test_required_manual_workflows_are_present(self) -> None:
        names = {section["name"] for section in workflow_sections()}
        self.assertIn("management_forensic", names)
        self.assertIn("channel_check_protocol", names)
        self.assertIn("pre_mortem", names)
        self.assertIn("decision_journal", names)
        self.assertIn("post_mortem", names)


if __name__ == "__main__":
    unittest.main()
