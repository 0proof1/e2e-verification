from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


SUPPORTED_EXECUTION = {"agent", "harness", "hybrid"}
SUPPORTED_REASONING = {"standard", "high", "maximum"}


def load_model_plan(path: Path) -> dict[str, Any]:
    data = _load_document(path)
    errors = validate_model_plan(data)
    if errors:
        raise ValueError("\n".join(errors))
    data["_model_plan_path"] = str(path.resolve())
    return data


def validate_model_plan(plan: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if plan.get("version") != 1:
        errors.append("model plan version must be 1")
    if not str(plan.get("name", "")).strip():
        errors.append("model plan name is required")

    slots = plan.get("slots", [])
    if not isinstance(slots, list):
        return [*errors, "model plan slots must be an array"]
    slot_ids: set[str] = set()
    for index, slot in enumerate(slots):
        if not isinstance(slot, dict):
            errors.append(f"slots[{index}] must be an object")
            continue
        slot_id = str(slot.get("id", ""))
        if not slot_id:
            errors.append(f"slots[{index}].id is required")
        elif slot_id in slot_ids:
            errors.append(f"duplicate model slot: {slot_id}")
        else:
            slot_ids.add(slot_id)
        if not str(slot.get("purpose", "")).strip():
            errors.append(f"slot {slot_id or index}: purpose is required")
        if slot.get("reasoning") not in SUPPORTED_REASONING:
            errors.append(f"slot {slot_id or index}: unsupported reasoning level {slot.get('reasoning')}")
        capabilities = slot.get("capabilities")
        if not isinstance(capabilities, list) or not capabilities or not all(
            isinstance(value, str) and value.strip() for value in capabilities
        ):
            errors.append(f"slot {slot_id or index}: capabilities must be a non-empty string array")
        share = slot.get("max_share_percent")
        if not isinstance(share, int) or isinstance(share, bool) or not 1 <= share <= 100:
            errors.append(f"slot {slot_id or index}: max_share_percent must be between 1 and 100")

    providers = plan.get("providers", {})
    if not isinstance(providers, dict) or not providers:
        errors.append("model plan providers must be a non-empty object")
        providers = {}
    for provider, bindings in providers.items():
        if not isinstance(provider, str) or not provider.strip():
            errors.append("model provider names must be non-empty strings")
        if not isinstance(bindings, dict):
            errors.append(f"provider {provider}: bindings must be an object")
            continue
        unknown = set(bindings) - slot_ids
        if unknown:
            errors.append(f"provider {provider}: unknown slots {sorted(unknown)}")
        missing = slot_ids - set(bindings)
        if missing:
            errors.append(f"provider {provider}: missing slots {sorted(missing)}")
        for slot_id, binding in bindings.items():
            if not isinstance(binding, dict):
                errors.append(f"provider {provider} slot {slot_id}: binding must be an object")
                continue
            values = [key for key in ("model", "model_env") if str(binding.get(key, "")).strip()]
            if len(values) != 1:
                errors.append(f"provider {provider} slot {slot_id}: set exactly one of model or model_env")

    stages = plan.get("stages", [])
    if not isinstance(stages, list) or not stages:
        errors.append("model plan stages must be a non-empty array")
        stages = []
    stage_ids: set[str] = set()
    for index, stage in enumerate(stages):
        if not isinstance(stage, dict):
            errors.append(f"stages[{index}] must be an object")
            continue
        stage_id = str(stage.get("id", ""))
        if not stage_id:
            errors.append(f"stages[{index}].id is required")
        elif stage_id in stage_ids:
            errors.append(f"duplicate model-plan stage: {stage_id}")
        else:
            stage_ids.add(stage_id)
        execution = stage.get("execution")
        if execution not in SUPPORTED_EXECUTION:
            errors.append(f"stage {stage_id or index}: unsupported execution mode {execution}")
        slot = stage.get("model_slot")
        if execution in {"agent", "hybrid"} and slot not in slot_ids:
            errors.append(f"stage {stage_id or index}: agent execution requires a known model_slot")
        if execution in {"agent", "hybrid"} and not str(stage.get("agent", "")).strip():
            errors.append(f"stage {stage_id or index}: agent execution requires an agent")
        if execution == "harness" and slot:
            errors.append(f"stage {stage_id or index}: harness-only execution must not select a model_slot")
        if execution in {"harness", "hybrid"}:
            harnesses = stage.get("harnesses")
            if not isinstance(harnesses, list) or not harnesses or not all(
                isinstance(value, str) and value.strip() for value in harnesses
            ):
                errors.append(f"stage {stage_id or index}: deterministic execution requires harnesses")
        tasks = stage.get("tasks")
        if not isinstance(tasks, list) or not tasks or not all(
            isinstance(value, str) and value.strip() for value in tasks
        ):
            errors.append(f"stage {stage_id or index}: tasks must be a non-empty array")

    for index, rule in enumerate(plan.get("escalation_rules", [])):
        if not isinstance(rule, dict):
            errors.append(f"escalation_rules[{index}] must be an object")
            continue
        if rule.get("from_slot") not in slot_ids or rule.get("to_slot") not in slot_ids:
            errors.append(f"escalation rule {index}: from_slot and to_slot must reference known slots")
        if not str(rule.get("when", "")).strip():
            errors.append(f"escalation rule {index}: when is required")
    return errors


def materialize_model_plan(plan: dict[str, Any], provider: str | None = None) -> dict[str, Any]:
    errors = validate_model_plan(plan)
    if errors:
        raise ValueError("\n".join(errors))
    providers = plan["providers"]
    if provider is not None and provider not in providers:
        raise ValueError(f"unknown model provider {provider}; choose one of {sorted(providers)}")
    selected = providers.get(provider, {}) if provider else {}
    slot_map = {slot["id"]: slot for slot in plan["slots"]}
    stages: list[dict[str, Any]] = []
    unresolved: list[str] = []
    for stage in plan["stages"]:
        item = dict(stage)
        slot_id = stage.get("model_slot")
        if slot_id:
            item["requirements"] = slot_map[slot_id]
            if provider:
                binding = selected[slot_id]
                model = binding.get("model") or os.environ.get(binding.get("model_env", ""), "")
                item["binding"] = {
                    "provider": provider,
                    "model": model or None,
                    "modelEnv": binding.get("model_env"),
                    "resolved": bool(model),
                }
                if not model:
                    unresolved.append(slot_id)
        stages.append(item)
    return {
        "version": plan["version"],
        "name": plan["name"],
        "source": plan.get("_model_plan_path", ""),
        "provider": provider,
        "availableProviders": sorted(providers),
        "ready": bool(provider) and not unresolved,
        "unresolvedSlots": sorted(set(unresolved)),
        "stages": stages,
        "escalationRules": plan.get("escalation_rules", []),
    }


def _load_document(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        value = json.loads(text)
    elif path.suffix.lower() in {".yaml", ".yml"}:
        try:
            import yaml
        except ImportError as error:
            raise RuntimeError("YAML model plans require PyYAML") from error
        value = yaml.safe_load(text)
    else:
        raise ValueError("model plan must use .json, .yaml, or .yml")
    if not isinstance(value, dict):
        raise ValueError("model plan document must be an object")
    return value
