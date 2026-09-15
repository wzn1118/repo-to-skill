# Threat Model

## Trust boundaries

- Repository files, documentation, symlinks, manifests, and comments are untrusted.
- Discovery never imports or executes target code.
- Symlinks escaping the source root fail closed.
- File count and individual file size are bounded.
- Named pipes and other special files are rejected before content reads.
- `.env`, SSH, cloud credential, package credential, and similar paths are excluded from analyzer
  inputs; their values are never serialized.
- Generated commands must be backed by supported claims.

## Git source controls

- Remote sources are restricted to public GitHub HTTPS URLs without embedded credentials.
- Refs reject option-like, reflog, whitespace, traversal-like, and repeated-separator forms.
- Git runs with a temporary HOME, system config disabled, hooks disabled, submodules disabled,
  prompts disabled, LFS smudging disabled, and file protocol disabled.
- Repository-configured clean/smudge/process filters and fsmonitor commands are disabled before Git
  inspects the worktree. Raw file hashes and committed blob IDs are stored separately.
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
- Inspect, plan and build POST endpoints require an exact loopback Host/Origin and a per-process
  session token. GET endpoints also validate Host to prevent DNS rebinding from exposing that token.
- Local source paths are restricted to explicitly configured roots (the current directory by default).
- Request bodies, request duration and write rate are bounded; writes are serialized. This is a
  single-user local workbench, without persistent jobs, cancellation or multi-tenant isolation.
- Installation and sandbox execution are CLI operations, not UI write endpoints.
- API run IDs are fixed-format and path traversal attempts are rejected.
- Repository-derived values are returned as JSON and rendered as text nodes under a restrictive CSP.
- Evidence and update reports are bounded and paginated; arbitrary artifact files are never served.

## Residual risks

- A remote Git fetch can consume disk or bandwidth before post-checkout file limits run. Hosted
  execution must add filesystem quotas and process-level resource limits before private beta.
- License handling currently detects root license-file presence, not SPDX identity or compatibility.
- A host attacker able to rewrite both a run directory and its SQLite index can forge local
  integrity state. Hosted operation requires signed or append-only service-side manifests.
- Role inference still uses path heuristics, and lexical Go extraction does not prove full command
  ownership. Source traceability does not prove semantic correctness.
- The local Docker daemon is trusted; its rootless status is not asserted. This executor is not a
  multi-tenant sandbox. Dependency installation and image acquisition are separate operations.
- Only referenced evidence files are checked against the generated bundle before execution. The
  full filtered input set used for that execution is hashed and recorded, but unreferenced helpers
  are not independently authenticated against the original repository commit.
- Local install transactions retain history and reject modified files. Recovery is incomplete for
  all crash points and Windows file-lock cases; do not infer a production-grade package manager.

## Bundle and installation controls

- Strict typed provenance, safe YAML, duplicate-key checks, bounded inventory, path and case-collision
  checks, full file locks and deterministic re-rendering bind generated documents to their claims.
- A bundle-owned lock proves self-consistency only. Source authenticity remains
  `not_independently_authenticated` unless an external trusted binding is supplied.
- Installation defaults to preview. Explicit execution stages captured bytes, validates them,
  journals the change and records the installed digest. Updates reject unmanaged or modified files.
- History supports rollback through the distribution API; broader recovery and client loading tests
  are tracked as incomplete in the upgrade status.

## Local execution controls

- Execution is explicit and requires a locally installed Linux image. The resolved image ID is
  recorded and used for the container; the runner does not pull images or install dependencies.
- A filtered temporary source copy is mounted read-only. Container networking is disabled, the
  process runs as UID/GID 65534, capabilities are dropped and privilege escalation is disabled.
- CPU, memory, swap, process, file, temporary storage, output and wall-clock limits are enforced.
  Timeout and excessive output trigger container removal, followed by a cleanup probe.
- Host tokens and Docker configuration are not inherited. Filename exclusions and limited token/key
  patterns supplement isolation; these checks are not a complete secret detector.
- Execution reports retain image/source/bundle hashes and raw output. Exit success alone never
  promotes a bundle to runtime readiness or proves that an independent task oracle passed.

## Deferred controls

Product archive ingestion, comprehensive secret/SBOM/license analysis, dependency approvals, private
repository transfer authorization, signed releases and hosted isolation remain separate work packages.
The public benchmark archive adapter already has traversal, link and expansion checks; this does not
mean the product resolver supports all archive inputs.
