from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import patch

from e2e_verification.model_plan import load_model_plan, materialize_model_plan, validate_model_plan


ROOT = Path(__file__).resolve().parents[1]


class ModelPlanTest(unittest.TestCase):
    def test_example_is_provider_neutral_and_materializes_from_environment(self) -> None:
        plan = load_model_plan(ROOT / "examples" / "model-plan.example.json")
        with patch.dict(os.environ, {
            "E2E_CODEX_ADJUDICATOR_MODEL": "principal",
            "E2E_CODEX_IMPLEMENTER_MODEL": "builder",
            "E2E_CODEX_COLLECTOR_MODEL": "worker",
        }, clear=False):
            result = materialize_model_plan(plan, "codex")
        self.assertTrue(result["ready"])
        self.assertEqual("principal", result["stages"][0]["binding"]["model"])
        self.assertEqual("browser-probes", result["stages"][2]["harnesses"][0])

    def test_missing_provider_models_are_visible_without_invalidating_the_plan(self) -> None:
        plan = load_model_plan(ROOT / "examples" / "model-plan.example.json")
        with patch.dict(os.environ, {}, clear=True):
            result = materialize_model_plan(plan, "claude")
        self.assertFalse(result["ready"])
        self.assertEqual(["adjudicator", "collector", "implementer"], result["unresolvedSlots"])

    def test_harness_only_stage_cannot_consume_a_model_slot(self) -> None:
        errors = validate_model_plan({
            "version": 1,
            "name": "bad",
            "slots": [{
                "id": "worker", "purpose": "test", "reasoning": "standard",
                "capabilities": ["collect"], "max_share_percent": 80,
            }],
            "providers": {"custom": {"worker": {"model": "local"}}},
            "stages": [{
                "id": "collect", "execution": "harness", "model_slot": "worker", "tasks": ["capture"],
            }],
            "escalation_rules": [],
        })
        self.assertTrue(any("harness-only" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
