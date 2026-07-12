# Security policy

Please report suspected vulnerabilities through the repository host's private security-advisory channel rather than opening a public issue. Do not include live credentials, tokens, private URLs, customer data, screenshots, traces, downloads, or production reproduction targets in any report; use synthetic samples and coordinate sensitive transfer with the maintainers inside the advisory.

Supported security fixes target the latest released minor version and the current main branch.

## Safe operation

- Run against local or explicitly isolated test environments.
- Review `e2e-verify plan` output before execution.
- Keep credentials in environment variables or an external secret manager.
- Require named approval for downloads, writes, destructive behavior, and external sends.
- Inspect screenshot and download artifacts before sharing them; structured redaction cannot prove raster or file-content safety.
- Treat a cleanup failure as a failed mutating verification.

The redaction layer is defense in depth, not permission to point the harness at production or retain real personal information.
