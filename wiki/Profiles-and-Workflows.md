# Profiles and Workflows

## Profiles describe a product

Start from the synthetic example:

```bash
mkdir -p profiles/my-project
cp examples/project.example.json profiles/my-project/project.json
e2e-verify validate --config profiles/my-project/project.json
```

A profile may declare accounts, roles, route permissions, menus, login
requests, browser selectors, API probes, expected responses, and fixture
lifecycle settings. Use environment-variable references for credentials; never
store live secrets in the profile.

Supported substitutions include `${account.id}`, `${account.password}`,
`${account.mode}`, `${role}`, and `${env:NAME}`.

## Workflows describe safe execution

Workflows select declared operations and add dependencies, conditions, retry
rules, resume behavior, and named approvals. Review the resolved plan before
contacting a target:

```bash
e2e-verify plan \
  --workflow profiles/my-project/workflow.yaml
```

A step that writes a fixture might declare `approval: fixture-write`; the
operator must then supply the matching `--approve fixture-write` token.

## Adapters discover framework-specific facts

Controllers, URL tables, generated OpenAPI, or proprietary fixture formats may
require executable code:

```bash
e2e-verify plan \
  --adapter profiles/my-project/adapter.py \
  --workflow profiles/my-project/workflow.yaml
```

Adapters are trusted Python selected explicitly by the operator. Removing a
product profile should not require changes to the platform core.

## Portable procedures

The bundled skills cover project discovery, RBAC APIs, browser routes, UI
bindings, error UX, exports, safe writes, and evidence closeout. Compose the
smallest set needed for the question being verified.
