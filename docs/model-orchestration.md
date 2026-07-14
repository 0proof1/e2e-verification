# Model Orchestration and the Adaptive Loop

AI is the adaptive control plane; harnesses remain the deterministic data
plane. The project is intentionally useful without a model, but its distinctive
behavior comes from repeating an evidence-bounded loop:

```text
criteria → bounded hypothesis/workflow → deterministic run → evidence
   ▲                                                       │
   └──── agent interpretation, triage, and next action ─────┘
```

An agent may choose what to investigate next, interpret usability, reconcile
conflicting evidence, or stop. It may not silently expand target, role, route,
state, viewport, risk, or approval scope. API calls, DOM measurements,
screenshots, retries, and persisted results remain harness responsibilities.

## Provider-neutral routing

`examples/model-plan.example.json` defines three capability slots:

| Slot | Purpose | Suggested ceiling |
|---|---|---:|
| `adjudicator` | Criteria and high-impact/conflicting final decisions | 5% |
| `implementer` | Collector implementation and first UX review | 25% |
| `collector` | Bounded execution coordination and evidence organization | 80% |

The plan does not hard-code a vendor generation. Codex, Claude, or another
runtime supplies concrete model names through environment bindings.

```bash
export E2E_CODEX_ADJUDICATOR_MODEL='your-principal-model'
export E2E_CODEX_IMPLEMENTER_MODEL='your-implementation-model'
export E2E_CODEX_COLLECTOR_MODEL='your-collection-model'

e2e-verify model-plan \
  --model-plan examples/model-plan.example.json \
  --provider codex
```

## Evidence-backed model tasks

`agent-task` packages the selected stage, resolved binding, portable agent,
complete skill instructions, a minimal redacted run summary, guardrails, and a
structured response contract. It can be passed to any external model runner.

```bash
e2e-verify agent-task \
  --model-plan examples/model-plan.example.json \
  --provider codex \
  --stage first-ux-review \
  --run-dir evidence/runs/pilot \
  --output evidence/runs/pilot/first-ux-review.task.json
```

Generating a task does not invoke a model or authorize a mutation. Applying a
model response must still materialize a reviewable workflow and pass normal
risk, approval, cleanup, and resume rules. This keeps adaptive exploration
auditable instead of turning the model into an unrestricted browser driver.

## Current limit

Version 0.2 defines and tests routing and handoff contracts. Vendor API clients
and autonomous production-project exploration are not included or claimed.
External orchestrators are responsible for model invocation, authentication,
cost controls, and response transport.
