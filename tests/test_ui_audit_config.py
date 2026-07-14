from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from e2e_verification.ui_audit_config import load_state_fixture, load_ui_audit_config, validate_state_fixture


class UiAuditConfigTest(unittest.TestCase):
    def valid_config(self) -> dict:
        return {
            "draft_contract_version": "ui-audit-v1",
            "name": "synthetic-audit",
            "read_only": True,
            "viewports": [{"name": "laptop", "width": 1366, "height": 768}],
            "artifacts": ["viewport", "full_page"],
            "roles": {"EDITOR": {"first_route": "/#/command"}},
            "cases": [{
                "page": "command", "role": "EDITOR", "route": "/#/command",
                "title": "Command", "states": ["data", "empty"],
            }],
            "state_contract": {
                "data": {"action": "passthrough"},
                "empty": {"fixture_pattern": "fixtures/{page}/empty.json"},
            },
        }

    def test_loads_fixture_and_rejects_mutating_intercept(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "pyproject.toml").write_text("[project]\nname='test'\nversion='0'\n", encoding="utf-8")
            fixture_dir = root / "fixtures" / "command"
            fixture_dir.mkdir(parents=True)
            fixture = {"state": "empty", "intercepts": [{
                "method": "GET", "url": "**/api/items", "action": "fulfill", "body": {"data": []},
            }]}
            (fixture_dir / "empty.json").write_text(json.dumps(fixture), encoding="utf-8")
            path = root / "audit.json"
            path.write_text(json.dumps(self.valid_config()), encoding="utf-8")
            old_cwd = Path.cwd()
            try:
                import os
                os.chdir(root)
                config = load_ui_audit_config(path)
                self.assertEqual("empty", load_state_fixture(config, "command", "empty")["state"])
            finally:
                os.chdir(old_cwd)

        invalid = {"state": "error", "intercepts": [{"method": "POST", "url": "**/api/items", "action": "abort"}]}
        self.assertIn("mutating method", "\n".join(validate_state_fixture(invalid)))

    def test_requires_paired_screenshots_and_known_states(self) -> None:
        config = self.valid_config()
        config["artifacts"] = ["viewport"]
        config["cases"][0]["states"] = ["unknown"]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audit.json"
            path.write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "full_page"):
                load_ui_audit_config(path)

    def test_valid_config_matches_published_schema(self) -> None:
        root = Path(__file__).resolve().parents[1]
        schema = json.loads((root / "schemas" / "ui-audit-v1.schema.json").read_text(encoding="utf-8"))
        Draft202012Validator(schema).validate(self.valid_config())


if __name__ == "__main__":
    unittest.main()
