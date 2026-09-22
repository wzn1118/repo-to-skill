# Retained diagnostic run — over-conservative context binding

This intermediate compiler replaces the old disconnected JS-table shortcut, but incorrectly
treats a write to `context.logger` as replacement of the entire context object. The real
Prettier entry contains such a logging update, so its valid parameter flow is rejected.

All 45 pinned snapshots complete. Selected fact coverage drops to 20/40 and static task
prerequisites to 10/30. These regressions are retained, not hidden or substituted for the final
compiler's result. The subsequent regression test isolates an unrelated logger-field update;
the fix distinguishes object identity/argument-source replacement from that field update.

This is static-only diagnostic evidence. No workflow score is inferred from it. The final
compiler is rerun in v21 using the unchanged corpus, tasksets and independent oracles. To
reconstruct this intermediate compiler from the final commit, apply
`benchmark/history/2026-09-22-v20-context.patch` to a separate checkout. Its fingerprint is in
`results.json`. Old results and source pins remain unchanged; manifests are written last.
