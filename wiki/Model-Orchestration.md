# Model Orchestration

AI is the adaptive control plane; deterministic harnesses remain the execution
and measurement plane. A model can set criteria, interpret evidence, select a
bounded follow-up, or escalate ambiguity. It does not replace Playwright for
screenshots, DOM measurements, retries, or assertions.

`examples/model-plan.example.json` defines adjudicator, implementer, and
collector capability slots. Codex, Claude, and custom runtimes bind concrete
model names through environment variables, so the workflow does not depend on
a vendor generation name.

```bash
e2e-verify model-plan \
  --model-plan examples/model-plan.example.json \
  --provider codex
```

After deterministic collection, render a redacted task packet for an external
model runner:

```bash
e2e-verify agent-task \
  --model-plan examples/model-plan.example.json \
  --provider codex \
  --stage first-ux-review \
  --run-dir evidence/runs/pilot
```

Version 0.2 does not include vendor API clients or claim autonomous production
exploration. A model response must become a reviewable workflow and pass the
same risk, approval, cleanup, and resume contracts.
