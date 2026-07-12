# Public Repository Blockers

The automated source gate can establish that the current tree satisfies its
machine-checkable publication policy. A maintainer must still complete these
checks for the exact candidate commit before changing repository visibility.

- [ ] Confirm provenance and redistribution rights for every tracked file.
- [ ] Review Git history for removed secrets, private source, personal data, and
      internal paths; publish from a clean orphan history or perform a reviewed
      history rewrite when necessary.
- [ ] Confirm all committed identities, URLs, roles, selectors, and fixtures are
      synthetic and product-neutral.
- [ ] Confirm generated evidence, screenshots, traces, downloads, and local
      environment files are untracked.
- [ ] Run the full unit, network, browser, Docker, package, and dependency audits.
- [ ] Run `python3 tools/public_repo_gate.py` successfully on a clean candidate.

This checklist records human release controls that static scanning cannot prove.
