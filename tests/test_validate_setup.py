import unittest
from unittest.mock import patch

from taiwan_equity_toolkit import validate_setup


class ValidateSetupTests(unittest.TestCase):
    def test_main_returns_zero_when_only_warning_class_issues_exist(self) -> None:
        class DummyClient:
            def __init__(self, token: str):
                self.token = token

        def add_warning(_client, _stock_id, status):
            status.add_warning("warning only")

        with patch.object(validate_setup, "check_token", return_value="token"):
            with patch.object(validate_setup, "FinMindClient", DummyClient):
                with patch.object(validate_setup, "check_quota", return_value=None):
                    with patch.object(validate_setup, "check_datasets", side_effect=add_warning):
                        with patch.object(validate_setup, "check_parser_ledgers", return_value=None):
                            with patch.object(validate_setup, "check_triage_and_gate3", return_value=None):
                                with patch("sys.argv", ["validate_setup.py"]):
                                    exit_code = validate_setup.main()

        self.assertEqual(exit_code, 0)

    def test_main_returns_one_when_a_fatal_dataset_issue_is_recorded(self) -> None:
        class DummyClient:
            def __init__(self, token: str):
                self.token = token

        def add_fatal(_client, _stock_id, status):
            status.add_fatal("fatal dataset issue")

        with patch.object(validate_setup, "check_token", return_value="token"):
            with patch.object(validate_setup, "FinMindClient", DummyClient):
                with patch.object(validate_setup, "check_quota", return_value=None):
                    with patch.object(validate_setup, "check_datasets", side_effect=add_fatal):
                        with patch.object(validate_setup, "check_parser_ledgers", return_value=None):
                            with patch.object(validate_setup, "check_triage_and_gate3", return_value=None):
                                with patch("sys.argv", ["validate_setup.py"]):
                                    exit_code = validate_setup.main()

        self.assertEqual(exit_code, 1)


if __name__ == "__main__":
    unittest.main()
