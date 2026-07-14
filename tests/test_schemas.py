from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, RefResolver

from e2e_verification.evidence import Status, StepResult
from e2e_verification.workflow import HarnessOutcome, HarnessRegistry, StepSpec, WorkflowRunner, WorkflowSpec, load_workflow


ROOT = Path(__file__).resolve().parents[1]


def schema(name: str) -> dict:
    return json.loads((ROOT / "schemas" / name).read_text(encoding="utf-8"))


class SchemaTest(unittest.TestCase):
    def test_example_workflows_match_published_schema(self) -> None:
        validator = Draft202012Validator(schema("workflow-v1.schema.json"))
        for path in (ROOT / "workflows").glob("*"):
            if path.suffix not in {".json", ".yaml", ".yml"}:
                continue
            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
            validator.validate(payload)
            load_workflow(path)

    def test_agent_definitions_match_published_schema(self) -> None:
        validator = Draft202012Validator(schema("agent-v1.schema.json"))
        for path in (ROOT / "agents").glob("*.yaml"):
            validator.validate(yaml.safe_load(path.read_text(encoding="utf-8")))

    def test_example_model_plan_matches_published_schema(self) -> None:
        validator = Draft202012Validator(schema("model-plan-v1.schema.json"))
        payload = json.loads((ROOT / "examples" / "model-plan.example.json").read_text(encoding="utf-8"))
        validator.validate(payload)

    def test_step_and_run_output_match_published_schemas(self) -> None:
        evidence_schema = schema("evidence-v2.schema.json")
        run_schema = schema("run-v2.schema.json")
        resolver = RefResolver.from_schema(run_schema, store={
            evidence_schema["$id"]: evidence_schema,
            run_schema["$id"]: run_schema,
        })
        step = StepResult(
            step_id="read",
            harness="pass",
            status=Status.PASS,
            started_at="2026-07-12T00:00:00+00:00",
            finished_at="2026-07-12T00:00:01+00:00",
        )
        Draft202012Validator(evidence_schema).validate(step.to_dict())

        registry_harness = HarnessRegistry()
        registry_harness.register("pass", lambda _step, _out: HarnessOutcome(status=Status.PASS))
        with tempfile.TemporaryDirectory() as directory:
            state = WorkflowRunner(registry_harness).run(
                WorkflowSpec("schema-test", [StepSpec("read", "pass")]),
                Path(directory),
            )
        Draft202012Validator(run_schema, resolver=resolver).validate(state)


if __name__ == "__main__":
    unittest.main()
