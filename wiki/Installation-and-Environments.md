# Installation and Environments

Choose the smallest installation that supports the verification question.

| Use | Install | Additional requirement |
|---|---|---|
| API and workflow checks | `pip install -e .` | PyYAML only |
| Browser verification | `pip install -e '.[browser]'` | Matching Playwright Chromium bundle |
| Development | checkout installer with `--extras dev` | Test and schema dependencies |
| XLSX reporting | `pip install -e '.[xlsx]'` | openpyxl |
| Docker verifier | included Dockerfile/Compose | Docker Engine with Compose |
| Offline host | preloaded wheelhouse and browser bundle | Compatible build backend and platform artifacts |

Playwright is not a base dependency. API-only environments therefore avoid its
Python package, browser download, and browser operating-system packages.

## Repeated checkout installation

Use the repository installer for development, CI, or any checkout whose package
version may be unchanged:

```bash
.venv/bin/python tools/install_checkout.py --extras dev
```

In CI, `GITHUB_SHA` is checked automatically. Clean release jobs should also
reject local modifications:

```bash
.venv/bin/python tools/install_checkout.py --extras dev --require-clean
```

The installer reads dependencies from `pyproject.toml`, installs only the
selected sets, and then performs one `--force-reinstall --no-deps -e .` for the
project. It verifies package version, checkout module path, console entry-point
path, and the current model-plan CLI commands. This prevents a previous install
of the same version from silently supplying an older CLI.

`--expected-sha` can provide an explicit full or unambiguous short revision.
It does not replace `--require-clean`: a dirty checkout can have the expected
HEAD while containing uncommitted code.

## Docker provenance and caching

The verifier base image is digest-pinned. Its direct Playwright and PyYAML
versions are exact build arguments. Supply the source revision when building:

```bash
docker compose build --build-arg SOURCE_SHA="$GITHUB_SHA"
docker compose run --rm verifier
```

`doctor` reports the image's `E2E_SOURCE_SHA`; unstamped host installs report
`unknown`. The revision is applied after the pinned browser-dependency layer,
so a new source revision reuses unchanged browser dependencies but always
reinstalls and smoke-tests the project layer.

## Portability boundary

The package matrix covers Python 3.11-3.13 on Linux and Python 3.12 on macOS and
Windows. Full API, Chromium, and Docker integration is currently verified on
Linux. ARM64, Alpine/musl, WSL, proxy, and private-CA environments must pass
`e2e-verify doctor` and a synthetic smoke run before being treated as validated
deployment targets.

Environment-independent contracts do not mean dependency-free execution.
Offline environments must preload the declared dependencies, a compatible
build backend, and the Playwright browser bundle for the target platform.
