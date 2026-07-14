from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from e2e_verification.agent_task import build_agent_task
from e2e_verification.model_plan import load_model_plan


ROOT = Path(__file__).resolve().parents[1]


class AgentTaskTest(unittest.TestCase):
    def test_task_combines_model_stage_agent_skills_and_redacted_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            (run_dir / "run.json").write_text(json.dumps({
                "contract_version": "1.1",
                "run_id": "pilot",
                "workflow": "pilot-visual-verification",
                "status": "PASS",
                "steps": {
                    "collect": {
                        "status": "PASS", "functionalStatus": "PASS", "usabilityStatus": "PASS",
                        "summary": {"passed": 1},
                        "metadata": {"token": "must-not-leak"},
                        "artifacts": [{
                            "kind": "screenshot", "path": "shot.png", "description": "viewport", "redacted": False,
                        }],
                    }
                },
            }), encoding="utf-8")
            plan = load_model_plan(ROOT / "examples" / "model-plan.example.json")
            with patch.dict(os.environ, {"E2E_CODEX_IMPLEMENTER_MODEL": "reviewer"}, clear=False):
                task = build_agent_task(plan, "codex", "first-ux-review", run_dir, ROOT)
        self.assertEqual("reviewer", task["binding"]["model"])
        self.assertEqual("ux-reviewer", task["agent"]["name"])
        self.assertGreater(len(task["skills"]), 0)
        self.assertNotIn("must-not-leak", json.dumps(task))
        self.assertEqual("shot.png", task["evidence"]["steps"]["collect"]["artifacts"][0]["path"])

    def test_harness_stage_cannot_be_rendered_as_an_agent_task(self) -> None:
        plan = load_model_plan(ROOT / "examples" / "model-plan.example.json")
        plan["stages"].append({"id": "machine", "execution": "harness", "harnesses": ["browser-probes"], "tasks": ["capture"]})
        with self.assertRaisesRegex(ValueError, "deterministic"):
            build_agent_task(plan, "codex", "machine", root=ROOT)


if __name__ == "__main__":
    unittest.main()
