from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from e2e_verification.evidence import Risk, Status
from e2e_verification.harnesses import _ui_case_findings, api_probes_harness, browser_probes_harness, default_registry, ui_audit_harness
from e2e_verification.workflow import StepSpec


class HarnessSafetyTest(unittest.TestCase):
    def test_default_registry_includes_ui_audit(self) -> None:
        self.assertIn("ui-audit", default_registry().names())

    def test_ui_audit_rejects_non_read_only_step(self) -> None:
        with self.assertRaisesRegex(ValueError, "read-only"):
            ui_audit_harness(StepSpec("ui", "ui-audit", risk=Risk.WRITE), Path("."))

    def test_ui_audit_emits_scroll_reset_functional_finding(self) -> None:
        findings = _ui_case_findings({
            "case_id": "UI-BUDGETS-DATA",
            "artifacts": {"viewport": "steps/ui/screenshots/budget.png"},
            "measurements": {
                "title_visible": True,
                "menu_scroll_reset": {
                    "status": "FAIL", "menu": "예산",
                    "before_scroll_y": 490, "after_scroll_y": 474,
                },
            },
        })
        self.assertEqual("UI-BUDGETS-DATA-scroll-reset", findings[0].id)
        self.assertEqual("navigation", findings[0].category)
        self.assertEqual(Status.FAIL, findings[0].status)

    def profile(self, directory: str, **values: object) -> Path:
        payload = {"version": 1, "name": "test", "roles": [{"name": "ADMIN"}], **values}
        path = Path(directory) / "profile.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_api_adapter_rejects_write_method_before_contacting_target(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            profile = self.profile(directory, api_probes=[{
                "id": "WRITE-1", "role": "ADMIN", "method": "POST", "path": "/users",
            }])
            step = StepSpec("api", "api-probes", args={"config": str(profile)}, risk=Risk.READ_ONLY)
            with self.assertRaisesRegex(ValueError, "read-only probes only"):
                api_probes_harness(step, Path(directory) / "out")

    def test_browser_adapter_rejects_declared_write_probe_before_launch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            profile = self.profile(directory, browser_probes=[{
                "id": "WRITE-1", "role": "ADMIN", "route": "/users", "selector": "button",
                "risk": "write",
            }])
            step = StepSpec("browser", "browser-probes", args={"config": str(profile)}, risk=Risk.READ_ONLY)
            with self.assertRaisesRegex(ValueError, "read-only probes only"):
                browser_probes_harness(step, Path(directory) / "out")


if __name__ == "__main__":
    unittest.main()
