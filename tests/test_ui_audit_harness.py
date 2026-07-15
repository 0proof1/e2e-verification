from __future__ import annotations

import unittest
from types import SimpleNamespace

from e2e_verification.ui_audit_harness import (
    _aggregate_axis,
    _browser_auth_request_path,
    _case_id,
    _measure_menu_scroll_reset,
    _operation_timeout_ms,
    _summarize_cases,
)


class UiAuditHarnessTest(unittest.TestCase):
    def test_case_id_includes_role_state_and_viewport(self) -> None:
        value = _case_id(
            {"page": "settlements", "role": "SETTLEMENT_OPERATOR"},
            "empty",
            {"name": "office-laptop"},
        )
        self.assertEqual("UI-SETTLEMENTS-EMPTY-SETTLEMENT_OPERATOR-OFFICE-LAPTOP", value)

    def test_usability_review_does_not_fail_functional_axis(self) -> None:
        cases = [{"functional_status": "PASS", "usability_status": "REVIEW"}]
        self.assertEqual("PASS", _aggregate_axis(cases, "functional_status", review=False))
        self.assertEqual("REVIEW", _aggregate_axis(cases, "usability_status", review=True))
        self.assertEqual({"total": 1, "passed": 1, "failed": 0, "blocked": 0, "review": 1}, _summarize_cases(cases))

    def test_failure_and_blocked_precedence(self) -> None:
        cases = [
            {"functional_status": "BLOCKED", "usability_status": "BLOCKED"},
            {"functional_status": "FAIL", "usability_status": "REVIEW"},
        ]
        self.assertEqual("FAIL", _aggregate_axis(cases, "functional_status", review=False))
        self.assertEqual("BLOCKED", _aggregate_axis(cases, "usability_status", review=True))

    def test_scroll_reset_skips_when_navigation_is_not_applicable(self) -> None:
        self.assertEqual(
            "SKIP",
            _measure_menu_scroll_reset(object(), "http://example.test", None, "/#/command", 0)["status"],
        )

    def test_operation_timeout_is_capped_by_project_request_timeout(self) -> None:
        config = {"defaults": {"request_timeout_seconds": 30}}
        self.assertEqual(30_000, _operation_timeout_ms(config, SimpleNamespace(timeout_seconds=600)))
        self.assertEqual(12_000, _operation_timeout_ms(config, SimpleNamespace(timeout_seconds=12)))

    def test_browser_auth_request_path_requires_an_explicit_absolute_path(self) -> None:
        self.assertEqual(
            "/api/auth/login",
            _browser_auth_request_path({"browser_login": {"request_path": "/api/auth/login"}}),
        )
        self.assertEqual("", _browser_auth_request_path({"browser_login": {"request_path": "auth/login"}}))
        self.assertEqual("", _browser_auth_request_path({}))


if __name__ == "__main__":
    unittest.main()
