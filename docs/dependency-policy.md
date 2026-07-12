# Dependency Policy

Runtime dependencies must support the currently tested Python versions and have
a compatible open-source license. Browser automation remains isolated behind
Playwright; optional report formats remain extras.

Dependabot tracks Python and GitHub Actions dependencies. High or critical
advisories block a release unless a documented, time-bounded exception is
approved by maintainers.

Container base images are pinned by digest. Updating the Python base tag or
Playwright version requires rebuilding the Compose smoke test and reviewing the
resulting operating-system packages.
