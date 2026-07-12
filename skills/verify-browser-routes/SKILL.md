---
name: verify-browser-routes
description: Verify role-based browser login, menus, redirects, allowed routes, and forbidden routes with screenshot evidence. Use for navigation contracts, route guards, role-specific surfaces, responsive route smoke tests, or browser regression verification.
---

# Verify browser routes

1. Validate selectors and role home paths before launching the browser.
2. Run configured login, menu, and route checks through the `browser-probes` harness.
3. Keep route navigation read-only. Move controls that may mutate state into an approval-gated workflow.
4. Compare the observed path and DOM state with the configured contract; do not infer authorization from menu visibility alone.
5. Capture the smallest useful screenshot and mark whether it has been reviewed or redacted.
6. Record unexpected HTTP 5xx responses separately from route failures.
7. Return precise findings for login, menu, route guard, rendering, and server behavior.

Stop when the target redirects outside the configured origin or requests an unapproved external interaction.

