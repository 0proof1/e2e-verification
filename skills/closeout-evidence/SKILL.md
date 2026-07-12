---
name: closeout-evidence
description: Review completed verification evidence, reconcile statuses and cleanup, and produce a concise closeout report. Use after workflow execution, when triaging incomplete runs, preparing JSON or HTML reports, comparing legacy and new harness parity, or deciding justified follow-up steps.
---

# Close out verification evidence

1. Read the run state and every referenced step result from the same run directory.
2. Confirm contract versions, workflow identity, timestamps, artifact existence, and redaction flags.
3. Reconcile `PASS`, `FAIL`, `REVIEW`, `BLOCKED`, and `SKIP` without converting missing evidence into success.
4. Confirm every mutating step has required and verified cleanup.
5. Group findings by product defect, policy ambiguity, missing fixture, environment failure, and harness failure.
6. Generate the JSON state and HTML report. Generate XLSX only when a profile explicitly enables its exporter.
7. Recommend the smallest follow-up workflow justified by unresolved findings.
8. State coverage limits and excluded surfaces plainly.

Do not publish artifacts marked unredacted or of unknown provenance.

