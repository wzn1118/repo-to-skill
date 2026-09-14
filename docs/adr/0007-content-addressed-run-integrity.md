# ADR 0007: Content-Addressed Discovery Run Integrity

## Status

Accepted on 2026-09-01.

## Decision

A Discovery Run ID binds the IR schema version, the Repository Snapshot digest, and the canonical
SHA-256 of the complete Discovery IR. The run envelope stores the same Discovery digest in both
`run.json` and `source.lock.json`.

Loading a cached run always performs self-contained consistency checks:

- the directory name must equal the recomputed content-addressed run ID;
- `source.lock.json` must equal the Snapshot embedded in `discovery.json`;
- split inventory, evidence, claim, and capability artifacts must equal their IR sections;
- `run.json` must identify the expected stage, outcome, tree hash, input digest, and IR digest;
- required artifacts must be regular, bounded files rather than symbolic links.

When the sibling `runs.sqlite3` index exists, loading additionally requires every required artifact
to match its indexed path and byte-level SHA-256. A copied run directory remains usable without the
index, but receives only the self-contained consistency checks.

## Consequences

Changing analyzer output for the same Snapshot produces a new Discovery Run instead of silently
reusing an older run ID. Semantic tampering is detected by redundant artifact comparisons and run-ID
recomputation. Formatting-only tampering is detected when the external SQLite index is present.

This is local integrity detection, not a digital signature. An attacker who can coherently rewrite
both the run directory and its SQLite index remains outside this control. Hosted deployments must
anchor artifact manifests in an append-only or signed service-side store.
