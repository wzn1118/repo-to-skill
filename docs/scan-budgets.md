# Workspace content budgets / 按工作区分配扫描预算

Large repositories now retain a bounded file inventory and return partial discovery when their
content budget is exhausted. A test corpus can no longer consume every content slot before
product source is considered. Partial discovery remains `REVIEW_REQUIRED`, including when a
generated bundle is validated or installed independently of its original discovery directory.

## Selection and limits

The scanner first enumerates paths without reading file content, rejects unsafe links/special
files and enforces separate metadata limits. It identifies workspace roots from manifest filenames,
without executing configuration or importing repository modules. Files are ordered by path role,
then manifests/licenses, source extensions and other files. Workspaces at the same priority take
turns receiving slots. This is a deterministic heuristic, not a complete package-manager workspace graph.

| Default bound | Value |
| --- | ---: |
| Enumerated entries, including directories | 100,000 |
| Directories | 25,000 |
| Relative path depth | 64 |
| Files whose contents may be read | 10,000 |
| Files per workspace | 6,000 |
| Files per non-product role, across all workspaces | 1,000 |
| Bytes per file | 2 MiB |
| Total admitted content bytes | 128 MiB |
| Admitted bytes per workspace | 64 MiB |
| Admitted bytes per non-product role | 16 MiB |

Use `r2s inspect REPO --scan-profile expanded` (also available for fresh `plan`/`build`),
or choose **Large repository** in the UI, when a standard scan reports budget exclusions.
The expanded profile allows 40,000 files, 30,000 per workspace, 20,000 per non-product role,
16 MiB per file, 512 MiB total content, 384 MiB per workspace and 256 MiB per non-product role.
Metadata/depth limits and sensitive-file protections stay in force. This is an explicit larger
resource budget, not a guarantee of complete semantic analysis. Any remaining exclusion still
blocks static readiness. The selected limits contribute to scan identity; reusing an existing run
with a different profile is rejected. Rescan the source to obtain a new run.
Task execution and `verify` recover the known profile from the locked bundle and rescan under
that budget; the independent 64 MiB source-pack bound still applies. Custom SDK policies without
a known execution profile are rejected. `update` currently uses standard discovery; for an
expanded scan, inspect the new source explicitly and compare the two runs.

CLI 示例：`r2s inspect /data/project --scan-profile expanded --json`。UI 选择“大型仓库”即可；
扩大预算会读取更多文件，任何仍未覆盖的区域继续阻断就绪状态，旧运行与报告不会被改写。

These are content admission bounds, not peak process memory or total parser CPU limits. Parsing,
serialization and repeated consistency checks need additional resources. The benchmark worker
has a separate wall-clock timeout; process-level CPU/RSS limits for every product analysis are
still open work. Hard metadata limits reject the scan instead of returning an unbounded inventory.

Within the enumerated scope, budget-excluded files retain path, size and reason with no fabricated
content hash. A `SCAN_INCOMPLETE` error describes this unknown region. Path roles prioritize exact
components such as `tests` and `__fixtures__`; `packages/test-runner` remains a product candidate.
Go programs under `tools`/`scripts` are marked development candidates. These heuristics can miss
unusual product layouts and are not a semantic proof of entrypoint identity.

Ignored dependency/build directories are recorded as exclusions. For a local Git source with a
verified tracked-file map, a tracked directory is retained even when its name is normally ignored.
Sensitive directories and `.git` remain excluded. Public archive and Git resolvers are not yet
unified: archives without a tracked-file map retain ordinary exclusions. `.gitignore` execution,
LFS/submodule traversal and arbitrary repository configuration are not enabled.

## Evidence and reporting

Analyzers read source only through the scanner's admitted-file index. Each read is bounded and
its content hash must match the scan. Excluded Python manifests and module targets are no longer
read through a separate unrestricted path. Symlink and special-file checks also apply when the
content budget has already been exhausted. This does not establish a race-free hostile-filesystem
snapshot: upstream snapshot isolation and complete directory-handle traversal remain separate work.

New runs contain `scan.json`, a deterministic projection of inventory and scan policy. The SQLite
index records it; loading compares it with the IR and checks its recorded hash when an index exists.
CLI inspect JSON and the local UI expose the same projection. `analyzed_files` currently counts
text files admitted for analysis, not files for which every language/framework parser succeeded.

`PROVENANCE.json` carries a compact `scan_scope`, including the inventory digest, policy, excluded
count and completeness within that policy. Skill text displays this boundary. Independent validation
refuses a partial or unknown scope; installation cannot silently upgrade it to static success.
The full inventory stays in the discovery run, avoiding a large duplicated inventory in every Skill.

Old discovery envelopes remain readable without a `scan.json`. Old bundles without an explicit
scan scope now require review or fresh generation. Existing artifacts and benchmark reports are
not rewritten. Scope claims embedded in a bundle remain unsigned internal consistency information,
not independent source authentication or complete CLI coverage.

The policy identity includes numeric limits, filename/role rules, exclusions and whether a tracked
map was available. It also contributes to the analysis digest. Changes in unscanned content cannot
be claimed as detected when file metadata is unchanged; skipped content is explicitly unknown.

## 中文说明

The [upgrade-v8 measurement](../benchmark/runs/2026-09-15-upgrade-v8/report.md) retains all 45
pinned repositories. TypeScript admits 2,113 text files and records 64,412 budget-excluded files;
webpack admits 2,742 and excludes 15,699. Both return partial discoveries, with TypeScript retaining
the conflicting `tsc` definitions and emitting no product Skill. Core selected fact coverage rises
from 9/40 to 10/40 through webpack's entrypoint, while static readiness falls from 26/36 to 20/36
under the stricter scope rule. Runtime and semantic conclusions remain unverified.

新扫描器将“列出文件”和“读取内容”分开限额，并在工作区之间轮流分配内容预算。
大型测试集不会优先占满所有名额；超限文件仍保留路径、大小和原因，不伪造内容摘要。
部分结果带有阻断性的 `SCAN_INCOMPLETE`，生成物、独立校验与安装入口都保持“需审查”。

分析器统一从已准入的文件索引读取内容，并重新核对字节摘要。CLI、UI 和 `scan.json`
显示同一份范围信息。这里的“分析文件数”指准入的文本文件数，不代表所有文件均已完成语义分析。
目录角色与 workspace 识别仍是保守规则；完整命令图、Git/archive 统一快照、进程资源配额仍未完成。
