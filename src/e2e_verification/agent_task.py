from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from .assets import asset_root
from .evidence import write_json_atomic
from .model_plan import materialize_model_plan
from .redaction import redact


def build_agent_task(
    model_plan: dict[str, Any],
    provider: str,
    stage_id: str,
    run_dir: Path | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    materialized = materialize_model_plan(model_plan, provider)
    stages = {stage["id"]: stage for stage in materialized["stages"]}
    if stage_id not in stages:
        raise ValueError(f"unknown model-plan stage {stage_id}; choose one of {sorted(stages)}")
    stage = stages[stage_id]
    if stage["execution"] == "harness":
        raise ValueError(f"stage {stage_id} is deterministic and does not produce an agent task")
    binding = stage.get("binding", {})
    if not binding.get("resolved"):
        name = binding.get("modelEnv") or stage.get("model_slot", "model")
        raise ValueError(f"stage {stage_id}: model binding is unresolved; set {name}")

    root = root or asset_root()
    agent_name = stage.get("agent")
    if not agent_name:
        raise ValueError(f"stage {stage_id}: agent is required")
    agent_path = root / "agents" / f"{agent_name}.yaml"
    if not agent_path.is_file():
        raise ValueError(f"stage {stage_id}: agent definition does not exist: {agent_path}")
    agent = yaml.safe_load(agent_path.read_text(encoding="utf-8"))
    skills = []
    for name in agent.get("skills", []):
        path = root / "skills" / name / "SKILL.md"
        if not path.is_file():
            raise ValueError(f"agent {agent_name}: skill definition does not exist: {path}")
        skills.append({"name": name, "path": str(path), "instructions": path.read_text(encoding="utf-8")})

    evidence = _evidence_summary(run_dir) if run_dir else None
    return redact({
        "contractVersion": "1.0",
        "kind": "e2e-verification-agent-task",
        "plan": {"name": materialized["name"], "source": materialized["source"]},
        "stage": {
            "id": stage["id"],
            "execution": stage["execution"],
            "tasks": stage["tasks"],
            "harnesses": stage.get("harnesses", []),
            "modelSlot": stage["model_slot"],
        },
        "binding": binding,
        "agent": agent,
        "skills": skills,
        "evidence": evidence,
        "guardrails": [
            "Use only the supplied evidence and declared skill procedures.",
            "Do not broaden role, route, state, viewport, target, or risk scope silently.",
            "Do not execute product mutations from this task packet.",
            "Keep functional and usability judgments independent.",
            "Every P0-P3 finding must cite at least one supplied artifact path.",
            "Prefer a bounded follow-up workflow over an unstructured action.",
        ],
        "responseContract": {
            "status": "COMPLETE | REVIEW | BLOCKED",
            "summary": "string",
            "findings": [{
                "id": "string",
                "severity": "P0 | P1 | P2 | P3",
                "functionalStatus": "PASS | FAIL | BLOCKED",
                "usabilityStatus": "PASS | REVIEW | NOT_RUN",
                "evidence": ["artifact path"],
            }],
            "proposedFollowUp": [{
                "workflow": "declared workflow or proposed bounded workflow id",
                "reason": "evidence-backed reason",
                "risk": "read-only | download | write | destructive | external-send",
                "requiresApproval": "boolean",
            }],
            "escalation": {
                "required": "boolean",
                "toSlot": "model slot or null",
                "reason": "string",
            },
        },
    })


def write_agent_task(task: dict[str, Any], path: Path) -> Path:
    write_json_atomic(path, task)
    return path


def _evidence_summary(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "run.json"
    if not path.is_file():
        raise ValueError(f"run evidence does not exist: {path}")
    state = json.loads(path.read_text(encoding="utf-8"))
    steps = {}
    for step_id, step in state.get("steps", {}).items():
        steps[step_id] = {
            "status": step.get("status"),
            "functionalStatus": step.get("functionalStatus"),
            "usabilityStatus": step.get("usabilityStatus"),
            "summary": step.get("summary", {}),
            "findings": step.get("findings", []),
            "artifacts": [
                {
                    "kind": artifact.get("kind"),
                    "path": artifact.get("path"),
                    "description": artifact.get("description"),
                    "redacted": artifact.get("redacted"),
                }
                for artifact in step.get("artifacts", [])
            ],
        }
    return {
        "runId": state.get("run_id"),
        "workflow": state.get("workflow"),
        "status": state.get("status"),
        "contractVersion": state.get("contract_version"),
        "steps": steps,
    }
