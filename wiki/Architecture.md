# Architecture

The platform separates judgment from execution:

```text
Agent ──selects──▶ Skill ──uses──▶ Workflow ──runs──▶ Harness
  ▲                                                     │
  └──────── findings and recommended follow-up ◀────────┘
                            │
                            ▼
                 JSON · screenshots · HTML · XLSX
```

## Layers

| Layer | Responsibility |
|---|---|
| Agent | Plan, interpret evidence, triage, and select justified follow-up |
| Skill | Describe a reusable verification procedure |
| Workflow | Declare order, dependencies, conditions, approval, retry, and resume |
| Harness | Perform deterministic API/browser operations and emit evidence |
| Profile | Describe product roles, routes, selectors, probes, and fixtures |

Product-specific behavior belongs in removable profiles and optional adapters.
Core execution semantics belong under `src/e2e_verification/`.

## Deterministic boundary

An agent may choose a declared procedure, but the harness owns interaction and
evidence serialization. The harness does not decide its own next task. A
workflow document cannot load arbitrary adapter code; executable adapters are
selected explicitly through the CLI.

## Major source modules

- `config.py`: profile validation and substitution
- `workflow.py`: planning, gates, retries, and resume
- `api_harness.py`: deterministic HTTP probes
- `browser_harness.py`: browser actions and observations
- `evidence.py`: result and status contracts
- `redaction.py`: persistence-time structured redaction
- `reporting.py`: human-readable reports

Schemas, portable agents, reusable skills, workflows, and synthetic examples
ship with the Python distribution as installed assets.
