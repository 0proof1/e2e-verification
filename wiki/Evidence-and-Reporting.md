# Evidence and Reporting

Each run directory is a self-contained review unit. It contains `run.json`, one
`result.json` for every executed step, redacted logs, and selected artifacts.

## Status semantics

Evidence contract 1.1 records `functionalStatus` (`PASS`, `FAIL`, `BLOCKED`)
separately from `usabilityStatus` (`PASS`, `REVIEW`, `NOT_RUN`). The aggregate
workflow status below remains the orchestration result.

| Status | Meaning |
|---|---|
| `PASS` | The configured observable contract was proven |
| `FAIL` | Observed behavior contradicted the contract |
| `REVIEW` | Evidence exists but a human or policy decision remains |
| `BLOCKED` | A prerequisite, credential, fixture, environment, or approval is missing |
| `SKIP` | A declared condition did not select the step |

Missing evidence never becomes `PASS`. A safely blocked run preserves completed
evidence so the same workflow and run directory can resume later.

```bash
e2e-verify resume \
  --workflow workflows/read-only.json \
  --run-dir evidence/runs/first-run
```

## Reports

HTML is the default standalone report:

```bash
e2e-verify report --run-dir evidence/runs/first-run
```

XLSX is optional:

```bash
python -m pip install -e '.[xlsx]'
e2e-verify report \
  --run-dir evidence/runs/first-run \
  --format xlsx
```

Reports summarize evidence; they do not make unreviewed screenshots or raw
downloads safe. Inspect the run directory's publication classification before
sharing it outside the test team.

HTML reports display screenshot thumbnails linked to the original artifact.
The link is an index, not a redaction or publication approval.
