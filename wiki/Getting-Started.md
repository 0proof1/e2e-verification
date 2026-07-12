# Getting Started

## Install

Python 3.11 or newer is required.

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
python -m playwright install chromium
```

On PowerShell, activate with `.venv\Scripts\Activate.ps1`. API-only checks do
not require a browser installation.

## Validate without contacting a target

```bash
e2e-verify validate --config examples/project.example.json
e2e-verify plan --workflow workflows/read-only.json
e2e-verify run --workflow workflows/read-only.json --dry-run
```

Validation checks the profile contract. Planning resolves the workflow and its
gates. A dry run must not be treated as application evidence.

## Inspect the environment

```bash
e2e-verify doctor \
  --config examples/project.example.json \
  --target-mode host \
  --connect
```

Choose `host` or container target mode explicitly. Loopback addresses inside a
container are not guessed.

## Run against an isolated test application

Keep credentials in environment variables:

```bash
export E2E_ADMIN_ID='test-admin'
export E2E_ADMIN_PASSWORD='...'
export E2E_API_BASE='http://127.0.0.1:8080/api'

e2e-verify run \
  --workflow workflows/read-only.json \
  --run-dir evidence/runs/first-run
```

Then generate a report:

```bash
e2e-verify report --run-dir evidence/runs/first-run
```

Before adding write steps, read [[Safety Model]].
