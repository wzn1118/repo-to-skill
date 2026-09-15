# Implementation Status

Updated: 2026-09-15

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
- Multiple Skills from multiple entrypoints.
- Goal-independent Discovery Runs and reusable Compilation Runs.
- SQLite run/artifact index and append-only run events.
- Content-addressed Discovery envelopes with lock, split-IR, size, symlink, and indexed hash checks.
- Detached Discovery Run portability with explicit self-consistency-only verification.
- Versioned file and Capability drift reports with Claim/Evidence dependency fingerprints.
- Goal-aware affected-Capability delta builds and parent-scoped Compilation IDs.
- Local update re-authorization and public GitHub locator reuse.
- Loopback-only, read-only dashboard for verified runs, capabilities, findings, updates, and
  evidence.
- Portable and Codex skill-only plugin adapters.
- Standalone structural and embedded provenance validation.
- License-file presence gate and preview-first plugin installation.

## Measured public benchmark

- 45 verified commit-pinned public snapshots on a dedicated data disk: 36 Core, six Rust challenges,
  three secondary edge cases. Metadata and measurements are separate immutable inputs/results.
- Actual discovery, generation and internal validation on every source, including unsupported languages.
- Core outcomes: 25 STATIC_READY, four REVIEW_REQUIRED, seven UNSUITABLE. Scanner limits count as failures.
- Ten repositories with 40 source-verified, agent-curated facts: nine covered; no human sign-off.
- 91 emitted Core facts indexed and provenance checked; four wrong Go executable names confirmed.
- Isolated offline runtime: ten functional checks across four projects, plus help/version and build checks.
- Official GitHub CLI Skill comparison, raw reports, failure roadmap and bilingual presentation.

The [public report](../benchmark/report.md) records limitations and failed attempts. Static readiness
is not semantic accuracy. These measurements leave the compiler unchanged to preserve the baseline.

## Deferred

- Deep JavaScript/TypeScript AST option and route extraction.
- Native Go AST helper and multi-file flag-flow analysis.
- External Agent Skills reference validator.
- Product-integrated execution sandbox and runtime readiness. Benchmark containers use non-root
  processes with network disabled; the Docker daemon itself is not asserted to be rootless.
- Secret, SBOM, license classification, and vulnerability tool adapters.
- Model-based evaluation and complete bundle reuse across incremental updates.

## Environment note

The public rerun uses Python 3.12.14 and verified GitHub archives/Git trees. The previous Python 3.10
bootstrap measurement is superseded, not a before/after analyzer improvement. Runtime execution was
measured on Linux containers only. Windows CI checks the compiler and harness unit tests, not Docker
runtime compatibility. gh/Hugo builds require an unavailable Go 1.27 toolchain; webpack delegates to
an external webpack-cli package absent from its runtime dependency set. Agent A/B evaluation remains
unmeasured.
