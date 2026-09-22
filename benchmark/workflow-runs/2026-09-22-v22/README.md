# v22: same-environment source improvement

**33/36 expanded-scan tasks pass**, compared with v19's **32/36**. The JSON stdin-formatting
task is the new pass; no previous pass regresses. All six Prettier invocations now bind to the
source-backed parser flow, but three JavaScript tasks still fail on missing native modules.
Their original output and exit-code failures remain in `expanded.json`.

`version-comparison.json` checks the unchanged source/task/oracle identities, scan budget,
runner and recorded runtime environments. This is the source-improvement comparison. The
[separate native repair](../2026-09-22-v22-native/README.md) changes the dependency inventory
and must not be called same-environment analyzer uplift. Do not pool either attempt.

v22 also fixes three over-permissive AST matches found in
[v21 adversarial checks](../../history/2026-09-22-v21-patterns.json). The entire taskset runs
again after the fixes. The [45-snapshot static run](../../runs/2026-09-22-upgrade-v22/report.md)
is separate from these output-oracle checks. These are authored structured-input workflows,
not free-form planning or Agent trials.

Reproduce with the command in the native run, substituting the immutable **original** Prettier
dependency cache and fresh work/output paths. Keep the expanded scan and 1,024-open-file limit.
Ordinary product defaults remain standard scanning and 128 open files.

中文：原环境下实测 **32/36 → 33/36**。三个失败来自执行依赖，仍保留在分母；另一个目录单独
测量依赖修复。不能把两种变化合并为分析器提升，也不能把结构化任务通过当作 Agent 收益。
