# Threat Model

## Trust boundaries

- Repository files, documentation, symlinks, manifests, and comments are untrusted.
- Discovery never imports or executes target code.
- Symlinks escaping the source root fail closed.
- File count and individual file size are bounded.
- `.env`, SSH, cloud credential, package credential, and similar paths are excluded from analyzer
  inputs; their values are never serialized.
- Generated commands must be backed by supported claims.

## Git source controls

- Remote sources are restricted to public GitHub HTTPS URLs without embedded credentials.
- Refs reject option-like, reflog, whitespace, traversal-like, and repeated-separator forms.
- Git runs with a temporary HOME, system config disabled, hooks disabled, submodules disabled,
  prompts disabled, LFS smudging disabled, and file protocol disabled.
- Remote checkouts are detached at a resolved commit. Cached snapshots are reused only after HEAD
  and clean-worktree verification.
- GitHub tokens and host cloud credentials are not inherited by the Git process.
- Dirty local trees record their base commit but Evidence does not claim that commit.

## Cached artifact controls

- Discovery Run IDs bind the Snapshot and canonical complete Discovery IR.
- Run metadata, source lock, and split IR artifacts are cross-checked on every cached load.
- Required cache artifacts reject symbolic links and files larger than 32 MiB.
- When `runs.sqlite3` is present, indexed paths and byte-level SHA-256 values must match.
- Detached run copies remain portable but have no external byte-level trust anchor.
- Local source locks omit absolute paths; updates require the caller to re-authorize a local path.
- Capability delta plugins use a distinct name and scope marker to avoid silent full-plugin
  replacement.

## Local dashboard controls

- The dashboard binds only to `127.0.0.1`, `localhost`, or `::1`; non-loopback hosts fail closed.
- It has read-only GET endpoints and never invokes discovery, generation, installation, or sandbox
  execution.
- API run IDs are fixed-format and path traversal attempts are rejected.
- Repository-derived values are returned as JSON and rendered as text nodes under a restrictive CSP.
- Evidence and update reports are bounded and paginated; arbitrary artifact files are never served.

## Residual risks

- A remote Git fetch can consume disk or bandwidth before post-checkout file limits run. Hosted
  execution must add filesystem quotas and process-level resource limits before private beta.
- License handling currently detects root license-file presence, not SPDX identity or compatibility.
- A host attacker able to rewrite both a run directory and its SQLite index can forge local
  integrity state. Hosted operation requires signed or append-only service-side manifests.

## Deferred controls

Archive ingestion, sandbox execution, content-aware secret scanning, dependency installation, and
private repository authorization remain disabled until their dedicated phases are implemented.
