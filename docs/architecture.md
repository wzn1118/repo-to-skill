# Architecture

The data path is `Snapshot -> Inventory -> Evidence -> Claim -> Capability -> Procedure -> Bundle`.
Discovery is goal-independent; compilation consumes a goal and Client Profile without changing
source facts. IDs and JSON artifacts are content-derived and deterministic. The generator consumes
procedures rather than raw source.

## Current module boundaries

- `source.py`: local/GitHub resolution, ref validation, commit pinning, isolated Git environment.
- `scanner.py`: bounded, no-follow inventory and policy-filtered analysis tree hashing.
- `analyzers.py`: common Discovery initialization, Python AST extraction, analyzer orchestration,
  classification, and cross-language conflict resolution.
- `javascript_analyzer.py`: package bin extraction with safe target containment checks.
- `go_analyzer.py`: conservative comment/string-aware lexical extraction for main packages and
  common flag declarations.
- `drift.py`: inventory diff, policy fingerprint, and Capability dependency invalidation.
- `planner.py`: deterministic Capability-to-Procedure compilation.
- `generator.py`: portable Skill and Codex plugin adapters plus standalone validation.
- `storage.py`: canonical artifacts, SQLite run index, parent-child run relationships.
- `cli.py`: orchestration only; it does not contain extraction or generation rules.
- `ui.py`: loopback-only read-only HTTP adapter over verified Discovery artifacts.

Discovery Runs are keyed by source tree and schema version. Compilation Runs are children keyed by
goal, target, and client-profile generation. A compilation can therefore run from cached IR after
the original source directory is unavailable.

The Discovery Run key also includes the canonical SHA-256 of the complete IR. Loading verifies the
directory key, run envelope, source lock, and all split IR projections before returning domain
objects. If `runs.sqlite3` is adjacent to the run, its artifact hashes add byte-level verification;
detached copies retain semantic cross-checks without pretending to have an external trust anchor.
Discovery indexing is intentionally non-recursive so child Compilation artifacts remain owned by
their Compilation Run.

Update Runs compare logical Capability keys and dependency fingerprints over Claims and Evidence.
The report separates added, removed, changed, and unchanged Capabilities from raw file drift. Global
policy fingerprint changes invalidate every surviving Capability. Compilation IDs include their
parent Discovery Run ID, preventing equal goals on different snapshots from colliding in SQLite.
Filtered generation writes `generation-scope.json`; Codex delta output has a non-replacement plugin
name.

The dashboard reads the artifact store through the same `load_discovery` integrity checks used by
CLI cache reuse. It exposes a bounded JSON projection, never raw artifact paths or file serving, and
renders repository-derived values as text nodes in a single local page.

The Snapshot stores both Git identity and analysis identity. `resolved_commit_sha` identifies a
clean Git source when available; `tree_sha256` identifies the exact policy-filtered inputs consumed
by analyzers. Evidence from a dirty worktree retains content and blob hashes but does not falsely
claim the base commit.

## Analyzer confidence boundary

Python uses the standard-library AST. JavaScript/TypeScript currently treats package manifests and
existing target files as authoritative only for executable names; it does not infer runtime flags.
Go uses a newline-preserving lexical masker to reject comments and string literals before detecting
`package main` and `func main`. Extracted Go flags carry lower confidence than manifest facts. A
future tree-sitter or native Go helper can replace these adapters without changing the IR.

All language analyzers merge into one Discovery IR. Command names are compared case-insensitively;
conflicting targets invalidate the relevant Claims. Generator slug collisions are checked again as
defense in depth before any bundle directory is written.
