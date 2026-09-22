# Retained diagnostic workflow run

The source-validator compiler passes 26/36 tasks with standard scans and 32/36 with expanded
scans, using the same fixed inputs and independent oracles as v17. The four remaining expanded
failures are Prettier parameter bindings; none is removed from the denominator.

This compiler still has the independently reproduced 1.5 discovery-directory migration gap.
See the [diagnostic regression](../../runs/2026-09-22-upgrade-v18/README.md). It is not the final
compiler's release validation. Final results are repeated under v19 after the storage fix;
these attempts are preserved, not pooled into the final task count.

No source pin, task, oracle or environment limit changed. Standard and expanded JSON retain
compiler/runner identities, per-task hashes, real command output and execution policies.
Use the v17 reproduction command with fresh output paths to repeat each arm. These are
generated invocations from authored structured inputs, not model trials or Agent uplift.
