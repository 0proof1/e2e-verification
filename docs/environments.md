# Environment and Target Modes

e2e-verification never guesses and silently changes an execution target. The
`doctor` command reports the runtime, resolves endpoint sources, checks required
credentials and browser dependencies, and optionally tests TCP reachability.

```bash
e2e-verify doctor --config examples/project.example.json
e2e-verify doctor --config examples/project.example.json --connect
```

Endpoint precedence is CLI option, environment variable, then profile default.
The diagnosis records that source without exposing credential values.

| Mode | Verifier location | Target location | Typical hostname |
|---|---|---|---|
| `host` | Host | Host | `127.0.0.1` |
| `docker-published` | Host | Published container port | `127.0.0.1` |
| `same-network` | Container | Same Compose/network | Service name such as `target` |
| `host-from-container` | Container | Host | Explicit host alias |
| `container-local` | Container | Same container | `127.0.0.1` |
| `external` | Any | Remote isolated target | HTTPS DNS name |
| `auto` | Any | Unknown | Diagnose only; ambiguous container loopback is blocked |

`host-from-container` rewrites a configured loopback hostname only because the
mode was explicitly selected. Docker Desktop normally provides
`host.docker.internal`. On Linux, add
`--add-host=host.docker.internal:host-gateway` or choose another explicit alias
with `--host-alias`.

The included Compose service defines that Linux host-gateway mapping, so the
same verifier image can also be exercised with `host-from-container` against a
host-published test port.

## Compose Example

The repository includes a synthetic target and a non-root Playwright verifier:

```bash
docker compose build
docker compose run --rm verifier
```

Evidence is written to the Compose-managed `evidence` volume so UID differences
between Linux, macOS, Windows, and the non-root container do not break writes.
Inspect or export that volume deliberately; do not commit its contents. No real
credentials, customer data, or production endpoints are used.

## Safety

Execution commands perform DNS and TCP preflight before legacy API/browser
runs. A missing credential, unresolved host, unreachable port, missing browser,
or ambiguous container loopback exits as `BLOCKED` before probes run. TCP
preflight opens a connection but does not send an HTTP request.

The resolved endpoints, value sources, runtime facts, and check results are
written to `preflight.json` beside the run summary. Legacy direct commands reject
every non-read-only probe; mutations must use a declared workflow with named
approval and verified cleanup.
