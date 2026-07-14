# Migrating from 0.1 to 0.2

Version 0.2 keeps profile version 1 and workflow version 1, but changes the
persisted evidence contract from 1.0 to 1.1.

## Existing run directories

Do not resume a 1.0 run with a 0.2 executable. Version 0.2 rejects the resume
with an evidence-contract error so a run cannot silently combine incompatible
step documents.

- Keep the 0.1 environment available when an old run must be reported or
  inspected.
- Start a new run directory with 0.2 when verification must continue.
- Do not edit an old `contract_version` value to bypass the guard; the required
  step fields and finding rules also changed.

## Step evidence

Evidence 1.1 adds two required fields:

```json
{
  "functionalStatus": "PASS",
  "usabilityStatus": "NOT_RUN"
}
```

`functionalStatus` accepts `PASS`, `FAIL`, or `BLOCKED`.
`usabilityStatus` accepts `PASS`, `REVIEW`, or `NOT_RUN`. Aggregate `status`
remains available for workflow ordering, exit codes, and closeout.

Finding severity is no longer free-form. Use `P0`, `P1`, `P2`, or `P3`, and
provide at least one artifact path or other evidence reference in `evidence`.

## Harness adapters

The existing `HarnessOutcome` fields retain their positional order. New harness
code should set `functional_status` and `usability_status` by keyword when it
assesses them. Legacy API harnesses default to functional `PASS` and usability
`NOT_RUN` unless their summary indicates failure, blocking, or UX review.

## Profiles and workflows

Existing version-1 profiles remain valid when they omit `visual_verification`.
To opt into the visual pilot, declare a viewport, capture types, mechanical
checks, and a title selector as shown in `examples/docker.project.json`.

Existing version-1 workflows remain valid. Model plans are optional and do not
authorize execution. `agent-task` output is a handoff for an external model
runtime; any proposed action must still become a validated, approval-bounded
workflow.
