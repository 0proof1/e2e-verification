from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CliTest(unittest.TestCase):
    def command(self, *args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT / "src")
        return subprocess.run(
            [sys.executable, "-m", "e2e_verification.cli", *args],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_legacy_validate_remains_available(self) -> None:
        result = self.command("validate", "--config", "examples/project.example.json")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue(json.loads(result.stdout)["valid"])

    def test_assets_reports_checkout_resources(self) -> None:
        result = self.command("assets")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue(Path(json.loads(result.stdout)["assetRoot"]).is_dir())

    def test_doctor_without_profile_reports_runtime(self) -> None:
        result = self.command("doctor")
        self.assertEqual(0, result.returncode, result.stderr)
        payload = json.loads(result.stdout)
        self.assertIn("runtime", payload)
        self.assertEqual(0, payload["summary"]["blocked"])

    def test_doctor_blocks_missing_credentials_without_exposing_values(self) -> None:
        result = self.command(
            "doctor",
            "--config",
            "examples/project.example.json",
            "--target-mode",
            "host",
        )
        self.assertEqual(3, result.returncode, result.stderr)
        payload = json.loads(result.stdout)
        self.assertGreater(payload["summary"]["blocked"], 0)
        self.assertNotIn("synthetic-password", result.stdout)

    def test_timeout_must_be_positive(self) -> None:
        result = self.command("doctor", "--timeout-seconds", "0")
        self.assertEqual(2, result.returncode)
        self.assertIn("at least 1", result.stderr)

    def test_legacy_direct_execution_rejects_write_probe(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "write.json"
            config.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "name": "write-test",
                        "defaults": {"api_base": "http://example.invalid"},
                        "roles": [{"name": "ADMIN"}],
                        "api_probes": [
                            {"id": "WRITE-1", "role": "ADMIN", "method": "POST", "path": "/items"}
                        ],
                    }
                ),
                encoding="utf-8",
            )
            result = self.command("api", "--config", str(config), "--target-mode", "external")
        self.assertEqual(3, result.returncode)
        self.assertIn("legacy-risk-boundary", result.stderr)

    def test_plan_materializes_without_execution(self) -> None:
        result = self.command("plan", "--workflow", "workflows/read-only.json")
        self.assertEqual(0, result.returncode, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(["validate-profile", "api-contracts"], [item["id"] for item in payload["steps"]])

    def test_run_and_html_report_work_without_live_api_when_dependency_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run = self.command(
                "run", "--workflow", "workflows/read-only.json", "--run-dir", directory,
            )
            self.assertEqual(3, run.returncode, run.stderr)
            state = json.loads((Path(directory) / "run.json").read_text(encoding="utf-8"))
            self.assertEqual("BLOCKED", state["status"])
            report = self.command("report", "--run-dir", directory)
            self.assertEqual(0, report.returncode, report.stderr)
            self.assertTrue((Path(directory) / "report.html").is_file())


if __name__ == "__main__":
    unittest.main()
