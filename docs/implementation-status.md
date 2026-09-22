# Implementation Status

Updated: 2026-09-22

The detailed U00–U22 ledger is in [upgrade-status.md](upgrade-status.md). The public benchmark section
below records the **legacy** measurement; the current compiler has a separate
[versioned report linked from the upgrade ledger](upgrade-status.md).

## Implemented

- Local bounded snapshot inventory with binary, oversized file, and symlink handling.
- Local Git and public GitHub Source Resolver with ref validation and detached commit pinning.
- Snapshot cache verification, isolated Git environment, and token/environment stripping.
- Sensitive file/directory exclusion without serializing secret values or per-file secret hashes.
- Commit-aware and Git-object-format-aware Evidence locations.
- Python CLI discovery from PEP 621, Poetry, and setup.cfg metadata.
- Static symbol and conservative option extraction without importing target code.
- JavaScript/TypeScript package bin discovery with target containment and existence checks.
- Go root/`cmd/*` CLI discovery with comment/string-resistant lexical main detection.
- Repository language/type classification and cross-language command conflict detection.
- Goal-based deterministic command selection and generated Skill-name collision prevention.
- Evidence, Claim, Capability, Procedure, portable Skill, and provenance chain.
- IR 1.6 parameter shapes, explicit workflow bindings and bounded source-backed regex/enum validators.
- Optional tree-sitter analysis for supported Commander, declarative JS tables, Go switches and Cobra graphs; complete language semantics remain unsupported.
- Multiple Skills from multiple entrypoints.
- Goal-independent Discovery Runs and reusable Compilation Runs.
- SQLite run/artifact index and append-only run events.
- Content-addressed Discovery envelopes with lock, split-IR, size, symlink, and indexed hash checks.
- Detached Discovery Run portability with explicit self-consistency-only verification.
- Versioned file and Capability drift reports with Claim/Evidence dependency fingerprints.
- Goal-aware affected-Capability delta builds and parent-scoped Compilation IDs.
- Local update re-authorization and public GitHub locator reuse.
- Loopback static workbench for inspect/build plus verified runs, capabilities, findings, updates
  and evidence; Host/Origin/session-token checks protect writes.
- Portable and Codex skill-only plugin adapters.
- Typed provenance, full file locks and deterministic document re-rendering during standalone validation.
- License-file presence gate and preview-first managed Codex installation with update/rollback API.
- Explicit local Docker execution with filtered source snapshots, image IDs, quotas and cleanup;
  process execution is not task evaluation or runtime readiness.

## Legacy public benchmark

- 45 verified commit-pinned public snapshots on a dedicated data disk: 36 Core, six Rust challenges,
  three secondary edge cases. Metadata and measurements are separate immutable inputs/results.
- Actual discovery, generation and internal validation on every source, including unsupported languages.
- Core outcomes: 25 STATIC_READY, four REVIEW_REQUIRED, seven UNSUITABLE. Scanner limits count as failures.
- Ten repositories with 40 source-verified, agent-curated facts: nine covered; no human sign-off.
- 91 emitted Core facts indexed and provenance checked; four wrong Go executable names confirmed.
- Isolated offline runtime: ten functional checks across four projects, plus help/version and build checks.
- Official GitHub CLI Skill comparison, raw reports, failure roadmap and bilingual presentation.

The [public report](../benchmark/report.md) records limitations and failed attempts. Static readiness
is not semantic accuracy. Those files remain unchanged; new measurements use separate run directories.

## Deferred

- Deep JavaScript/TypeScript AST option and route extraction.
- Native Go AST helper and multi-file flag-flow analysis.
- External Agent Skills reference validator.
- Complete task coverage, replay environment distribution and runtime readiness. Thirty reference
  tasks now have file/output oracles; no Agent trials or Skill uplift are measured. The local
  executor is implemented, but the Docker daemon itself is not asserted to be rootless.
- Secret, SBOM, license classification, and vulnerability tool adapters.
- Model-based evaluation and complete bundle reuse across incremental updates.

## Environment note

The public rerun uses Python 3.12.14 and verified GitHub archives/Git trees. The previous Python 3.10
bootstrap measurement is superseded, not a before/after analyzer improvement. Runtime execution was
measured on Linux containers only. Windows CI checks the compiler and harness unit tests, not Docker
runtime compatibility. The pinned gh source now has a successful isolated Go 1.27.1 build receipt;
its earlier toolchain, capacity and timeout failures remain recorded. Hugo's earlier failed build
has not been replaced by a successful new measurement. webpack delegates to an external webpack-cli
package absent from its measured runtime dependency set. Agent A/B evaluation remains unmeasured.
