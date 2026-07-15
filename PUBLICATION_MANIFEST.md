# Publication manifest

This file separates publishable source from generated verification evidence.

## Publish

- `src/`, `schemas/`, `agents/`, `skills/`, `workflows/`, synthetic `examples/`, and `wiki/`
- Product-neutral profile code and documentation that passes the checks below
- License, security, contribution, changelog, and architecture documentation

## Regenerate, do not publish

- `evidence/runs/`
- `profiles/*/evidence/*.xlsx`
- Screenshots, traces, browser storage, raw downloads, and generated reports
- Evidence-derived agent task packets such as `*.task.json`
- Local virtual environments, build output, and dependency directories

## Profile release checks

1. Confirm redistribution rights for source-derived adapters and documentation.
2. Search for credentials, tokens, personal information, private hosts, and absolute home paths.
3. Recreate examples with synthetic identities and fixtures.
4. Verify every mutating probe has named approval and independently verified cleanup.
5. Run the test suite and skill validators.
6. Confirm the changelog describes every versioned contract change.
7. Create release artifacts from a clean checkout so ignored local evidence cannot enter the archive.

Generated evidence is never a source asset. Reproduce it from a synthetic or explicitly authorized target and review it separately before any publication.
