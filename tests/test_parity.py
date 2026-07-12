from __future__ import annotations

import argparse
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from e2e_verification.api_harness import run_api
from e2e_verification.harnesses import api_probes_harness
from e2e_verification.http import HttpResult
from e2e_verification.workflow import StepSpec


class ParityTest(unittest.TestCase):
    def test_legacy_api_result_and_registered_harness_counts_match(self) -> None:
        config = {
            "version": 1,
            "name": "parity",
            "defaults": {"api_base": "http://example.invalid"},
            "api_login": {"path": "/login", "body": {}, "token_path": "data.accessToken"},
            "roles": [{"name": "ADMIN", "account": {"id_env": "PARITY_ID", "password_env": "PARITY_PASSWORD"}}],
            "api_probes": [{"id": "API-1", "role": "ADMIN", "method": "GET", "path": "/users", "expected_status": [200]}],
        }

        def response(_client: object, _method: str, path: str, _body: object = None) -> HttpResult:
            if path == "/login":
                return HttpResult(200, {"data": {"accessToken": "synthetic"}}, {}, 1)
            return HttpResult(200, {"data": []}, {}, 1)

        with tempfile.TemporaryDirectory() as directory:
            profile = Path(directory) / "profile.json"
            profile.write_text(json.dumps(config), encoding="utf-8")
            with patch.dict(os.environ, {"PARITY_ID": "admin", "PARITY_PASSWORD": "password"}, clear=False):
                with patch("e2e_verification.http.HttpClient.request", autospec=True, side_effect=response):
                    legacy = run_api(config, argparse.Namespace(api_base=None), Path(directory) / "legacy")
                    outcome = api_probes_harness(
                        StepSpec(
                            "api",
                            "api-probes",
                            args={"config": str(profile), "preflight": False},
                        ),
                        Path(directory) / "new",
                    )
        self.assertEqual(legacy["summary"], outcome.summary)
        self.assertEqual("PASS", outcome.status)

if __name__ == "__main__":
    unittest.main()
