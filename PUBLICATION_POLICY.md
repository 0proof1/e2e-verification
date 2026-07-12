# Publication Policy

The public project is the reusable verification platform: core Python code,
schemas, agents, skills, generic workflows, synthetic examples, tests, and
documentation covered by the Apache License 2.0.

Committed reference profiles must be synthetic and product-neutral. Private
product adapters, source extracts, and organization-specific contracts must stay
outside this repository and outside release archives.

The Docker build context applies the same boundary through `.dockerignore`.
Public container examples may contain only synthetic targets, credentials, and
evidence.

Do not publish credentials, tokens, cookies, personal information, customer or
institution identities, private hosts, internal paths, screenshots, traces,
downloads, workbooks, or historical evidence.

Release candidates must pass `python3 tools/release_check.py`, tests, package
build and installation checks, artifact-content inspection, and a manual review
of Git history and redistribution rights.

Changing the repository itself to public additionally requires
`python3 tools/public_repo_gate.py` to pass and the manual checks in
`PUBLICATION_BLOCKERS.md` to be completed for the candidate commit.
