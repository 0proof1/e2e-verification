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
                "kind": "screenshot", "path": "shot.png", "description": "viewport", "redacted": False,
            }]
            run_path.write_text(json.dumps(state), encoding="utf-8")
            text = write_html_report(run_path).read_text(encoding="utf-8")
        self.assertIn('<a href="shot.png"><img', text)
        self.assertIn('src="shot.png"', text)

    def test_v2_report_separates_verdicts_and_links_safe_images(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); image = root / "screenshots" / "한 장.png"
            image.parent.mkdir(); image.write_bytes(b"png")
            path = root / "run.json"
            path.write_text(json.dumps({
                "workflow": "audit", "status": "PASS", "steps": {"ui": {
                    "harness": "ui-audit", "status": "PASS", "functional_status": "PASS",
                    "usability_status": "REVIEW", "summary": {}, "artifacts": [{
                        "kind": "screenshot", "path": "screenshots/한 장.png", "description": "First view",
                        "role": "EDITOR", "state": "data", "variant": "viewport",
                    }],
                }},
            }), encoding="utf-8")
            text = write_html_report(path).read_text(encoding="utf-8")
        self.assertIn("<strong>Functional</strong><br>PASS", text)
        self.assertIn("<strong>Usability</strong><br>REVIEW", text)
        self.assertIn("loading=\"lazy\"", text)
        self.assertIn("screenshots/%ED%95%9C%20%EC%9E%A5.png", text)

    def test_unsafe_and_missing_images_warn_without_embedding(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "run.json"
            path.write_text(json.dumps({"workflow": "audit", "steps": {"ui": {
                "harness": "ui-audit", "status": "PASS", "summary": {}, "artifacts": [
                    {"kind": "screenshot", "path": "/absolute/private.png"},
                    {"kind": "screenshot", "path": "missing.png"},
                    {"kind": "screenshot", "path": "../escape.png"},
                ],
            }}}), encoding="utf-8")
            text = write_html_report(path).read_text(encoding="utf-8")
        self.assertIn("Artifact warnings", text)
        self.assertNotIn("<img", text)
        self.assertNotIn('href="/absolute/private.png"', text)

    def test_full_report_aggregates_case_axes_and_filters_by_page_and_shard(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("core.png", "finance.png"):
                (root / name).write_bytes(b"png")
            path = root / "run.json"
            path.write_text(json.dumps({
                "workflow": "full", "status": "PASS", "steps": {
                    "ui-core": {
                        "harness": "ui-audit", "functional_status": "PASS", "usability_status": "REVIEW",
                        "summary": {"total": 1, "passed": 1, "review": 1},
                        "metadata": {"ui_audit": {"cases": [{
                            "functional_status": "PASS", "usability_status": "REVIEW",
                        }]}},
                        "artifacts": [{
                            "kind": "screenshot", "path": "core.png", "page": "command",
                            "shard": "core", "role": "EDITOR", "state": "data",
                            "viewport": {"name": "office-laptop"},
                        }],
                    },
                    "ui-finance": {
                        "harness": "ui-audit", "functional_status": "PASS", "usability_status": "PASS",
                        "summary": {"total": 1, "passed": 1, "review": 0},
                        "metadata": {"ui_audit": {"cases": [{
                            "functional_status": "PASS", "usability_status": "PASS",
                        }]}},
                        "artifacts": [{
                            "kind": "screenshot", "path": "finance.png", "page": "dashboard",
                            "shard": "finance", "role": "SETTLEMENT_OPERATOR", "state": "data",
                            "viewport": {"name": "desktop-reference"},
                        }],
                    },
                },
            }), encoding="utf-8")
            text = write_html_report(path).read_text(encoding="utf-8")
        self.assertIn("2/2 PASS · FAIL 0 · BLOCKED 0 · SKIP 0", text)
        self.assertIn("1/2 PASS · REVIEW 1 · BLOCKED 0 · SKIP 0", text)
        self.assertIn('data-filter="page"', text)
        self.assertIn('data-filter="shard"', text)
        self.assertIn('data-page="dashboard"', text)
        self.assertIn('data-shard="finance"', text)


if __name__ == "__main__":
    unittest.main()
