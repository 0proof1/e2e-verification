# Readiness and Validation Claims

Readiness is reported as evidence levels, not a self-awarded maturity score.

| Level | Meaning |
|---|---|
| **Designed** | A contract and implementation exist and are reviewed locally. |
| **Synthetic-verified** | Automated tests exercise the behavior against repository-owned synthetic data or targets. |
| **Project-verified** | A documented, reproducible application of the behavior to a non-synthetic project exists. |
| **Externally-verified** | Independent users, maintainers, audits, or published releases provide corroborating evidence. |

## Current evidence

| Area | Current level | Evidence and limit |
|---|---|---|
| Workflow safety, approval, cleanup, redaction, and resume | Synthetic-verified | Unit and synthetic integration coverage exists; no independent security audit has been published. |
| API, Chromium, and Docker execution | Synthetic-verified on Linux | Other browsers and production applications are not yet demonstrated. |
| macOS and Windows packaging | Designed and CI-tested | Full browser/API/Docker integration is not claimed on those platforms. |
| ARM64, Alpine/musl, WSL, private CA, and proxy environments | Designed diagnostics only | Run `doctor` and a synthetic smoke test before treating any of these as validated. |
| Profiles and adapters | Synthetic-verified | No public Spring, Django, Rails, or production case study is currently included. |
| Provider-neutral AI work plans and evidence handoffs | Synthetic-verified | Model invocation remains an external orchestrator responsibility; autonomous production exploration is not yet a published result. |
| Releases and external adoption | Unverified | No PyPI release, independent adoption report, or stable release history is claimed here. |
| Governance and bus factor | Maintainer-led | Multiple active maintainers and external contributors are not yet demonstrated. |

The repository can prove that its own synthetic contracts run. It cannot yet
prove production fitness, broad ecosystem adoption, or independent assurance.
Those claims require public case studies, external audits, releases, and a wider
maintainer base.
