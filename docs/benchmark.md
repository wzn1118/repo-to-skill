# Benchmark methodology / 实测方法

The headline comes from actual pinned public source, not fixtures. See the
[measured report](../benchmark/report.md), [raw results](../benchmark/results.json), and
[official gh case study](case-studies/github-cli.md).

首页数字来自真实公共源码实测，受控 fixture 仅用于回归测试，不计入公共 benchmark。

## Corpus and denominator / 样本与分母

The saved `2026-09-14` [GitHub metadata](../benchmark/repository-metadata.json) contains 45 repositories:
36 High-Star Core (16 Tier A, 20 Tier B), six Rust challenges and three secondary edge cases.
The Core has 1,453,404 cumulative stars; this is not a count of unique users. Each record stores the
commit, stars, forks, default branch, archived status, primary language and SPDX license metadata.
No rendering step refreshes metadata. All 45 pinned source snapshots were downloaded or verified
against their Git tree. Existing directories alone never count as valid caches.

Core 的 36 个仓库均实际尝试分析，其中 34 个完成完整 pipeline；TypeScript 和 webpack 触发扫描文件数限制，
作为 REVIEW_REQUIRED 保留。结果为 25 STATIC_READY、4 REVIEW_REQUIRED、7 UNSUITABLE。
Rust challenge 同样实际扫描，结果为 4 REVIEW_REQUIRED、2 UNSUITABLE；bat 的 Go 测试辅助程序被错误生成为
Skill，已列入失败路线图，不能将这些结果宣传为完整 Rust 支持。Edge 结果单独统计，不进入 headline。

Star-weighted static-generation coverage is
`sum(stars of STATIC_READY Core repos) / sum(stars of all selected Core repos)` = **69.0%**.
Failures remain in the denominator. This is an operational generation metric, not supported-language
accuracy, semantic correctness, task success, or user coverage.

## Ground truth and runtime / 源码核查与运行实测

- [40 selected facts across 10 repositories](../benchmark/ground-truth-facts.json) have independently
  chosen source anchors. All 40 resolve at the pinned commits; nine occur in generated bundles.
- One of 30 tasks has all selected static prerequisites represented. This is not a task execution rate.
- [91 emitted Core facts](../benchmark/fact-audit.json) are indexed with traceable source. Targeted
  semantic review confirms four wrong Go executable names; the other 87 remain unreviewed.
- Ground truth was curated by an agent, with **zero human sign-offs**. Exhaustive CLI recall and a
  hallucination rate are not measured.
- [Python runtime](../benchmark/runtime-results.json) contains three black formatting cases and
  nine help/version cases across yt-dlp, pre-commit and Poetry, all passing.
- [Additional functional checks](../benchmark/functional-results.json) contain seven passing
  Prettier/ESLint/fzf cases. Together these are **10 functional checks across four projects**.
- [Build attempts](../benchmark/build-runtime-results.json) preserve three successes and three
  blockers: gh/Hugo need Go 1.27; webpack requires an external webpack-cli package.

源码哈希可追溯不等于语义正确。运行检查使用真实固定源码和合成输入；help/version、功能用例、静态事实覆盖率
分别统计。没有运行 with-skill / without-skill Agent 实验，不声称节省时间、Token 或提升任务成功率。

## Reproduce / 复现

Use Python 3.12+, a data disk with space for all source snapshots, GitHub access and optionally `gh`
authentication for Git-tree cache adoption. Discovery never imports or executes target code.

```bash
python -m pip install -e '.[dev,benchmark]'
python scripts/public_measure.py run --work /path/on/data-disk
python scripts/public_evaluate.py --work /path/on/data-disk
python scripts/public_fact_audit.py --work /path/on/data-disk
python scripts/public_report.py
```

`run` uses the committed metadata by default and writes separate results. `collect` combines completed
per-repository artifacts after checking their pins; it is useful after interrupted batches.
Snapshots include SHA-256 file inventories and recorded skipped links. Worker logs, discovery IR and
generated bundles stay on the data disk. GitHub receives summaries and evidence references, not
copies of the 45 upstream repositories.

To create a **new** metadata snapshot, choose an unused path; historical snapshots cannot be overwritten:

```bash
python scripts/benchmark_public.py metadata --output benchmark/metadata-next.json
python scripts/public_measure.py run --metadata benchmark/metadata-next.json --work /path/on/data-disk --output benchmark/results-next.json
```

A new source version also needs reviewed source anchors and compatible task fixtures. The committed
evaluation/report scripts target the current `benchmark/results.json`; do not mix reports from different runs.
The superseded `benchmark_public.py fetch/analyze/report` commands were removed to prevent unsafe cache
reuse, primary-language shortcuts and mutation of metadata by analysis results.

Runtime commands require Docker and explicit `--execute`:

```bash
python scripts/public_runtime.py --work /path/on/data-disk --image <python-image> --execute
python scripts/public_build_runtime.py --work /path/on/data-disk --go-image <go-image> --node-image <node-image> --execute
python scripts/functional_runtime.py --work /path/on/data-disk --execute
```

The Python runner expects a pre-downloaded `wheels/` directory, with filenames and SHA-256 recorded in
`runtime-results.json`. Container IDs are recorded per attempt. Node/Go dependency acquisition is a
separate network-enabled container step; npm lifecycle scripts are disabled. Build and execution use
no-network containers, read-only source, non-root processes, no host credentials and resource/time limits.
The build report records generated lockfile hashes. Dependency caches and images remain on the data
disk; reconstructing them from mirrors can depend on availability, so these runtime results are not a
claim of a fully hermetic public replay package. Host platform was Linux; Windows runtime was not measured.

运行报告记录源码 commit、容器 ID、wheel 哈希、命令及输出。这里提供实测记录，不将依赖源可用性或尚未
完成的 Windows Docker 验证包装成已通过。生产 CLI 的 `--verify sandbox` 集成仍未交付。

## Fixture regression / 受控回归

Ten fixtures exercise malicious README, unsafe entrypoints, conflicts, multiple commands and supported
language basics. They yield seven STATIC_READY, two REVIEW_REQUIRED and one UNSUITABLE, with eight
portable bundles. The [fixture chart](assets/benchmark.svg) retains its original 57 unittest count;
the full pytest suite now includes additional benchmark safety tests.

```bash
python -m pytest
ruff check .
mypy src
python scripts/measure_benchmark.py
```

CI runs pytest, Ruff and mypy on Ubuntu and Windows with Python 3.12. Public downloads and Docker
execution are intentionally separate explicit runs. Fixture successes never enter public headline metrics.

## Correction / 旧数据更正

The former 27.9% result used Python 3.10's limited TOML fallback, accepted incomplete caches and
marked Rust challenges unsupported before scanning. It is retained in
[history](../benchmark/history/2026-09-15-bootstrap-results.json) for audit and superseded by this rerun.
The compiler implementation is unchanged: this is a measurement correction, not an analyzer improvement claim.
