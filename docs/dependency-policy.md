# Dependency Policy

Runtime dependencies must support the currently tested Python versions and have
a compatible open-source license. Browser automation remains isolated behind
Playwright; optional report formats remain extras.

The base install depends only on PyYAML. Playwright is provided by the
`browser` extra and is also included in `dev`; openpyxl remains in `xlsx`.
API-only users therefore do not install the Playwright Python package or a
browser bundle.

Library metadata uses compatible lower bounds so downstream applications can
resolve their own environment. The Docker verifier is different: its base
image is digest-pinned and its direct Playwright and PyYAML versions are exact
build arguments. CI records and verifies SHA-256 hashes for wheel and source
archives before smoke installation.

For repeated installs from a checkout whose package version has not changed,
use `tools/install_checkout.py`. It resolves requested extras first, then runs
`pip --force-reinstall --no-deps -e .`, verifies the imported module points to
that checkout, checks the installed console entry point exposes the current
model-plan commands, and checks `GITHUB_SHA` when present. This prevents pip's
same-version satisfaction logic from leaving an older CLI installed.

The installer reads the selected dependency lists directly from
`pyproject.toml`; it does not install the project once merely to discover its
extras. The project is therefore built only for the final forced editable
install. Offline environments still need the declared dependencies and build
backend preloaded in a wheelhouse or package cache.

The source revision is applied after the Docker browser-dependency layer. A new
commit therefore force-reinstalls and smoke-tests the project while reusing the
unchanged, exactly pinned Playwright layer.

Dependabot tracks Python and GitHub Actions dependencies. High or critical
advisories block a release unless a documented, time-bounded exception is
approved by maintainers.

Container base images are pinned by digest. Updating the Python base tag or
Playwright version requires rebuilding the Compose smoke test and reviewing the
resulting operating-system packages.
