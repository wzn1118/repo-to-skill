# Product Contract

The compiler accepts a local directory, local Git repository, or public GitHub HTTPS URL plus an
optional ref and user goal. It resolves a Snapshot, discovers machine-verifiable facts, derives
claims and procedures, and emits zero or more portable Agent Skills. Discovery is static-only.
Repository documentation and instructions are untrusted data.

The current static compiler supports Python, JavaScript/TypeScript, and Go CLI discovery. Python
uses manifest plus AST evidence; JavaScript/TypeScript uses `package.json` bin plus target-file
evidence; Go uses `go.mod` plus conservative lexical main/flag evidence. Unsupported input produces
no fabricated capability and is reported as `NO_ACTIONABLE_CAPABILITY`.

Every option included in a generated reference maps to an executable Claim and Evidence record via
`PROVENANCE.json`. Missing source licenses downgrade generated artifacts to `REVIEW_REQUIRED`.

Codex output is a thin adapter over the same portable bundles. Its manifest contains `name`,
`version`, `description`, and `skills: ["./skills/"]`; no Codex-specific facts enter Discovery IR.

Remote URLs outside `github.com`, credential-bearing URLs, unsafe refs, dirty local ref builds,
symbolic-link escapes, sensitive credential paths, and corrupted snapshot caches fail closed.
Cached Discovery artifacts must be regular bounded files. Their run ID, source lock, split IR files,
and run envelope must agree with the canonical Discovery IR; an available SQLite artifact index is
authoritative for byte-level hashes.

Manifest command names and target paths are untrusted. Unsafe command tokens, Python module-path
escapes, JavaScript bin escapes, duplicate command ownership, and generated Skill-name collisions
must be rejected before writing bundles.

The compiler does not assume universal CLI arguments such as `--help`. Generated workflows use only
evidence-backed command names/options or explicit user input, preview the full invocation, and call
out possible external side effects before execution approval.

Updates compare old and new Discovery IR through Capability-to-Claim-to-Evidence dependency
fingerprints. Unreferenced file drift is reported without rebuilding Skills. Capability Evidence
drift rebuilds only the affected Capability, while license or other global policy drift invalidates
all surviving Capabilities. Removed Capabilities are reported explicitly.

Local updates require `--repo`; source locks do not retain absolute local paths. Filtered update
builds are labeled `capability_delta` and must not masquerade as complete replacement plugins.

The local UI is read-only and consumes the same verified run objects as the CLI. It displays real
Snapshot, Capability, Evidence, validation, compilation, and update state without maintaining a
second status model. It binds only to loopback addresses and has no repository execution, source
upload, install, or generation endpoint.
