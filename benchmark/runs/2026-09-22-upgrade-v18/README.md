# Retained diagnostic run — IR 1.6 migration gap

This run records the source-validator implementation before the 1.5 directory-envelope
compatibility fix. It is not the final published compiler's acceptance result.

- All 45 pinned repositories complete static analysis; all failures remain selected.
- The separate migration check imports 45 standalone 1.5 JSON files with review required.
- A real retained 1.5 discovery directory fails with `DISCOVERY_ARTIFACT_MISMATCH: run directory`.
  See `directory-migration-regression.json`. Standalone import success did not exercise the
  directory's version-bound digest, split files and SQLite index.
- A new regression test reproduces the failure before the fix. The fix restores the old
  schema only while authenticating its existing envelope and keeps its positional graph.
- Final-compiler tests and corpus measurements are repeated under `upgrade-v19`; these
  diagnostic results are not pooled with that run or used as its validation evidence.

The compiler identity is recorded in `results.json`. To reconstruct this diagnostic compiler
from the final commit, apply `benchmark/history/2026-09-22-v18-storage.patch` to a separate
checkout; source-validator changes otherwise match the final compiler. Historical source
pins, tasks and oracles are unchanged. The manifest is generated after all diagnostic files.
