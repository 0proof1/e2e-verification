from __future__ import annotations

import unittest

from e2e_verification.accessibility import (
    axe_asset_sha256,
    audit_keyboard_navigation,
    load_axe_source,
    run_accessibility_audit,
    run_axe_audit,
)


class FakeKeyboard:
    def __init__(self) -> None:
        self.keys: list[str] = []

    def press(self, key: str) -> None:
        self.keys.append(key)


class FakePage:
    def __init__(self, focus_steps: list[dict[str, object]] | None = None, *, axe_error: Exception | None = None) -> None:
        self.keyboard = FakeKeyboard()
        self.focus_steps = iter(focus_steps or [])
        self.injected = ""
        self.axe_error = axe_error

    def add_script_tag(self, *, content: str) -> None:
        self.injected = content

    def evaluate(self, script: str, argument: object = None) -> object:
        if "globalThis.axe.run" in script:
            if self.axe_error:
                raise self.axe_error
            return {
                "testEngine": {"version": "4.10.3"},
                "violations": [{
                    "id": "color-contrast", "impact": "serious", "tags": ["wcag2aa"],
                    "description": "contrast", "help": "fix contrast", "helpUrl": "https://example.test",
                    "nodes": [{"impact": "serious", "target": ["p"], "html": "<p>private</p>", "failureSummary": "low"}],
                }],
                "incomplete": [], "passes": [], "inapplicable": [],
            }
        if script.startswith("document.activeElement"):
            return None
        return next(self.focus_steps)


def focus_step(key: str, *, indicator: bool = True, tab_index: int = 0) -> dict[str, object]:
    return {
        "key": key, "selector": f"#{key}", "tag": "BUTTON", "role": "", "name": key,
        "tab_index": tab_index, "focus_visible": True, "indicator_detected": indicator, "visible": True,
        "rect": {"x": 0, "y": 0, "width": 10, "height": 10},
        "focused_style": {}, "unfocused_style": {},
    }


class AccessibilityUnitTest(unittest.TestCase):
    def test_bundled_axe_asset_is_pinned_and_local(self) -> None:
        source = load_axe_source()
        self.assertIn("axe v4.10.3", source[:200])
        self.assertEqual("880970c081707360e64f34cea25ff91892f5bc95675b0776925b9709dd8a68bb", axe_asset_sha256())

    def test_axe_normalizes_findings_without_node_html(self) -> None:
        page = FakePage()
        result = run_axe_audit(page)
        self.assertIn("axe v4.10.3", page.injected[:200])
        self.assertEqual("color-contrast", result["violations"][0]["id"])
        self.assertNotIn("html", result["violations"][0]["nodes"][0])
        self.assertEqual("PASS", result["functional_status"])
        self.assertEqual("REVIEW", result["usability_status"])

    def test_axe_runtime_failure_is_blocked_not_pass(self) -> None:
        result = run_axe_audit(FakePage(axe_error=RuntimeError("execution failed")))
        self.assertEqual("BLOCKED", result["functional_status"])
        self.assertEqual("BLOCKED", result["usability_status"])
        self.assertEqual("axe-execution-failed", result["issues"][0]["id"])

    def test_keyboard_uses_tab_only_and_detects_cycle(self) -> None:
        page = FakePage([focus_step("one"), focus_step("two"), focus_step("one")])
        result = audit_keyboard_navigation(page, max_tabs=10)
        self.assertEqual(["Tab", "Tab", "Tab"], page.keyboard.keys)
        self.assertTrue(result["cycle_complete"])
        self.assertEqual(["one", "two"], [step["key"] for step in result["steps"]])
        self.assertEqual("PASS", result["usability_status"])

    def test_keyboard_flags_positive_tabindex_and_missing_indicator_as_review(self) -> None:
        page = FakePage([focus_step("one", indicator=False, tab_index=2), focus_step("one")])
        result = audit_keyboard_navigation(page, max_tabs=3)
        self.assertEqual({"positive-tabindex", "focus-indicator-not-detected"}, {row["id"] for row in result["issues"]})
        self.assertEqual("REVIEW", result["usability_status"])

    def test_combined_contract_separates_keyboard_and_focus(self) -> None:
        page = FakePage([focus_step("one", indicator=False), focus_step("one")])
        result = run_accessibility_audit(page)
        self.assertEqual("PASS", result["functional_status"])
        self.assertEqual("REVIEW", result["usability_status"])
        self.assertEqual([], result["keyboard"]["issues"])
        self.assertEqual("focus-indicator-not-detected", result["focus"]["issues"][0]["id"])
        self.assertEqual(1, result["summary"]["axe_violations"])

    def test_combined_contract_propagates_blocked_audit(self) -> None:
        page = FakePage([focus_step("one"), focus_step("one")], axe_error=RuntimeError("no axe"))
        result = run_accessibility_audit(page)
        self.assertEqual("BLOCKED", result["functional_status"])
        self.assertEqual("BLOCKED", result["usability_status"])

    def test_rejects_invalid_limits_and_tags(self) -> None:
        with self.assertRaisesRegex(ValueError, "positive integer"):
            audit_keyboard_navigation(FakePage(), max_tabs=0)
        with self.assertRaisesRegex(ValueError, "non-empty"):
            run_axe_audit(FakePage(), tags=[])
        with self.assertRaisesRegex(ValueError, "non-empty"):
            run_axe_audit(FakePage(), tags="wcag2aa")


if __name__ == "__main__":
    unittest.main()
