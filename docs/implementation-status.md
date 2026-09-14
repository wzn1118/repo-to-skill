# Implementation Status

Updated: 2026-09-01

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

## Deferred

- Deep JavaScript/TypeScript AST option and route extraction.
- Native Go AST helper and multi-file flag-flow analysis.
- External Agent Skills reference validator.
- Rootless execution sandbox and runtime readiness.
- Secret, SBOM, license classification, and vulnerability tool adapters.
- Model-based evaluation and complete bundle reuse across incremental updates.

## Environment note

Two attempts to install uv failed because downloading the wheel timed out on the available network.
The formal project baseline remains Python 3.12 and uv, while the current standard-library core is
also exercised with the available Python 3.10 interpreter.

The GitHub resolver is covered by offline command-sequence and filesystem simulation. A real public
GitHub clone has not been used as a release assertion in this environment because network transfers
remain unreliable.
