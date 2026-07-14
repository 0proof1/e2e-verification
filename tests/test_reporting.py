from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from e2e_verification.reporting import write_html_report


class ReportingTest(unittest.TestCase):
    def state(self, directory: str) -> Path:
        path = Path(directory) / "run.json"
        path.write_text(json.dumps({
            "workflow": "<unsafe>",
            "status": "PASS",
            "started_at": "2026-07-12T00:00:00+00:00",
            "finished_at": "2026-07-12T00:00:01+00:00",
            "steps": {"api": {"harness": "api-probes", "status": "PASS", "summary": {"passed": 1}}},
        }), encoding="utf-8")
        return path

    def test_html_report_escapes_run_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = write_html_report(self.state(directory))
            text = output.read_text(encoding="utf-8")
        self.assertIn("&lt;unsafe&gt;", text)
        self.assertNotIn("<h1><unsafe>", text)

    def test_xlsx_report_when_optional_dependency_is_available(self) -> None:
        try:
            import openpyxl  # noqa: F401
        except ImportError:
            self.skipTest("openpyxl optional dependency is not installed")
        from e2e_verification.reporting import write_xlsx_report
        with tempfile.TemporaryDirectory() as directory:
            output = write_xlsx_report(self.state(directory))
            self.assertTrue(output.is_file())
            self.assertGreater(output.stat().st_size, 0)

    def test_html_report_links_thumbnail_to_original_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run_path = self.state(directory)
            state = json.loads(run_path.read_text(encoding="utf-8"))
            screenshot = Path(directory) / "shot.png"
            screenshot.write_bytes(b"synthetic")
            state["steps"]["api"]["functionalStatus"] = "PASS"
            state["steps"]["api"]["usabilityStatus"] = "PASS"
            state["steps"]["api"]["artifacts"] = [{
                "kind": "screenshot", "path": str(screenshot), "description": "viewport", "redacted": False,
            }]
            run_path.write_text(json.dumps(state), encoding="utf-8")
            text = write_html_report(run_path).read_text(encoding="utf-8")
        self.assertIn('<a class="artifact" href="shot.png">', text)
        self.assertIn('<img src="shot.png"', text)


if __name__ == "__main__":
    unittest.main()
