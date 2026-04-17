import unittest

from taiwan_equity_toolkit.states import Status, StatusedResult, combine_statuses


class StatusTests(unittest.TestCase):
    def test_status_enum_values_are_stable(self) -> None:
        self.assertEqual(Status.PASSED.value, "passed")
        self.assertEqual(Status.FAILED.value, "failed")
        self.assertEqual(Status.NOT_ASSESSED.value, "not_assessed")
        self.assertEqual(
            Status.MANUAL_REVIEW_REQUIRED.value,
            "manual_review_required",
        )

    def test_combine_statuses_uses_worst_case_precedence(self) -> None:
        self.assertEqual(
            combine_statuses([Status.PASSED, Status.NOT_ASSESSED]),
            Status.NOT_ASSESSED,
        )
        self.assertEqual(
            combine_statuses([Status.PASSED, Status.MANUAL_REVIEW_REQUIRED]),
            Status.MANUAL_REVIEW_REQUIRED,
        )
        self.assertEqual(
            combine_statuses([Status.NOT_ASSESSED, Status.MANUAL_REVIEW_REQUIRED]),
            Status.MANUAL_REVIEW_REQUIRED,
        )
        self.assertEqual(
            combine_statuses([Status.PASSED, Status.FAILED]),
            Status.FAILED,
        )
        self.assertEqual(
            combine_statuses(
                [
                    Status.PASSED,
                    Status.NOT_ASSESSED,
                    Status.MANUAL_REVIEW_REQUIRED,
                    Status.FAILED,
                ]
            ),
            Status.FAILED,
        )

    def test_combine_statuses_defaults_empty_input_to_not_assessed(self) -> None:
        self.assertEqual(combine_statuses([]), Status.NOT_ASSESSED)

    def test_statused_result_helper_methods_follow_status(self) -> None:
        result = StatusedResult(status=Status.MANUAL_REVIEW_REQUIRED)

        self.assertFalse(result.is_passed())
        self.assertFalse(result.is_failed())
        self.assertTrue(result.needs_analyst())
        self.assertFalse(result.is_not_assessed())


if __name__ == "__main__":
    unittest.main()
