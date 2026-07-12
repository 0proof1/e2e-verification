# Contributing

Contributions should keep the core framework-neutral and preserve the separation between agents, skills, workflows, harnesses, and profiles.

## Before submitting

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
PYTHONPATH=src .venv/bin/python -m compileall -q src tests
```

- Add tests for contract, safety, resume, and exit-code changes.
- Put product-specific endpoints, roles, selectors, and fixtures in a removable profile or adapter.
- Do not commit credentials, personal information, raw customer evidence, or internal paths.
- Keep skills concise and validate them with `quick_validate.py` from the Codex skill creator when available.
- Document compatibility changes in `CHANGELOG.md`.

Mutating harness contributions must require named approval, synthetic fixtures, finalization cleanup, and independent cleanup verification.
