---
name: discover-project
description: Inspect an application before E2E verification and create or update a portable project profile. Use when onboarding a new repository, identifying login and role surfaces, inventorying API and browser targets, or preparing a safe verification workflow without embedding product knowledge in the platform core.
---

# Discover a project

1. Read the target repository's local instructions before inspecting source or running commands.
2. Identify runtime commands, local-only URLs, authentication modes, active roles, API surfaces, browser routes, stable selectors, and existing test fixtures.
3. Classify every candidate action as `read-only`, `download`, `write`, `destructive`, or `external-send`.
4. Create a profile from `examples/project.example.json`. Store credentials only as environment-variable names.
5. Keep framework-specific discovery in a profile adapter. Do not add product names, selectors, endpoints, or role names to platform modules.
6. Add observable expectations for status, redirect, DOM state, network binding, download structure, or cleanup.
7. Run `e2e-verify validate --config <profile>` and `e2e-verify plan --workflow <workflow>`.
8. Report missing fixtures, unsafe actions, and assumptions as `BLOCKED` or `REVIEW`; do not invent them.

Do not execute write, destructive, notification, payment, or external-send behavior during discovery.

