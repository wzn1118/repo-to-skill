# Current static run: bounded JavaScript parser flow

All **45 pinned snapshots** complete: **36 high-star Core**, six unsupported-language challenges
and three secondary cases. Core outcomes remain **20 STATIC_READY / 10 REVIEW_REQUIRED /
6 UNSUITABLE**. The frozen star snapshot is not refreshed for report rendering.

The selected source-fact check covers **24/40** facts; **13/30** tasks have all selected static
prerequisites. **1,130** emitted facts have file-hash and source-pin checks. These measures do
not establish exhaustive CLI coverage, semantic precision, or task success. Full semantic
review and human sign-off remain incomplete.

## Implementation and retained diagnostics

The JS analyzer replaces the disconnected-table shortcut with a bounded entry/symbol/table/
parser/normalizer chain. It emits source-backed option names, types, selected aliases/choices
and positional consumption without executing the target repository.

The [v20 diagnostic](../2026-09-22-upgrade-v20/README.md) retains an over-conservative context
binding regression. The [v21 diagnostic](../../history/2026-09-22-v21-patterns.json) retains three
over-permissive structural matches. v22 preserves literal punctuation and array holes and
distinguishes generator methods. Both historical compiler inventories can be reconstructed
exactly using their retained patches in a separate checkout.

This run repeats every snapshot after the fixes; it does not relabel an old result. Its static
counts match v21, but its compiler fingerprint differs. See the [report](report.md), raw
`results.json`, source-fact evaluation, fact audit, local verification and write-last manifest.

Actual output-oracle tests are reported separately in the
[five-tool workflow measurement](../../workflow-runs/2026-09-22-v22-native/README.md). Expanded
scan budgets, environment repairs and authored inputs do not become default behavior or Agent
utility claims. [Implementation boundaries](../../../docs/javascript-option-flow.md).

中文：修复真实回归后，45 个固定快照全部重新测量。24/40 是选定事实覆盖，13/30 是静态前提覆盖，
1,130 条是哈希/提交核对；它们都不能替代完整语义审查或 Agent 效果评测。
