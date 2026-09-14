# ADR 0009: Local Read-Only Run Dashboard

## Status

Accepted on 2026-09-01.

## Decision

The MVP UI is a standard-library HTTP server started with `r2s ui`. It serves one embedded,
zero-build dashboard and a narrow JSON API over the existing artifact store. The UI has no separate
domain state, no source upload, and no operation that discovers, generates, installs, or executes
repository code.

The server accepts only loopback host values: `127.0.0.1`, `localhost`, or `::1`. It defaults to
`127.0.0.1:8765`. Its API exposes only Discovery Run summaries, verified run details, capability
Claims, paginated Evidence metadata, compilation records, and bounded update reports. Run IDs are
strictly validated before locating artifacts.

Repository-derived text is rendered with browser text nodes rather than HTML interpolation. The
response uses a restrictive CSP, disables caching, blocks framing, and returns no CORS policy.

## Consequences

The dashboard immediately visualizes actual `run-output` state while preserving the compiler's
static-only security contract. It is suitable for local inspection and demos, but not for shared or
hosted access. The hosted phase should replace this transport with authenticated APIs, task queues,
and a policy-enforced artifact service.
