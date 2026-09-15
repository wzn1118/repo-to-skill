# Measured Benchmark / 实测基准

This page records the current in-repository regression snapshot. It is designed to make the
README numbers reproducible, not to present an external benchmark result.

本页记录仓库当前的回归实测结果，目标是让 README 中的数字可复现，而不是冒充公共仓库评测结果。

## Method / 方法

- Corpus: the 10 committed directories under `tests/fixtures/`.
- Corpus：`tests/fixtures/` 下提交进仓库的 10 个受控样例目录。
- Discovery uses the static pipeline and never imports, builds, or executes fixture code.
- 分析只调用静态 pipeline，不导入、构建或执行样例代码。
- Portable generation uses the same goal for every fixture: `use the discovered command`.
- 生成阶段对所有样例使用同一目标：`use the discovered command`。
- `STATIC_READY`, `REVIEW_REQUIRED`, and `UNSUITABLE` are the compiler's current readiness values.
- 这些状态是当前编译器的 readiness 值，不等同于产品契约中尚未实现的 runtime readiness。

Reproduce the chart and summary:

```bash
PYTHONPATH=src python scripts/measure_benchmark.py
python -m unittest discover -s tests -q
```

The first command rewrites [`assets/benchmark.svg`](assets/benchmark.svg). The second command
checks the 57 test cases; the chart script intentionally does not run target repository code.

## Aggregate / 汇总

| Metric / 指标 | Measured value / 实测值 |
| --- | ---: |
| Fixtures / 样例 | 10 |
| Test cases / 测试用例 | 57 |
| Evidence records / 证据记录 | 36 |
| Claim records / 断言记录 | 25 |
| Capabilities / 能力 | 10 |
| Portable Skill bundles / Skill 包 | 8 |
| `STATIC_READY` | 7 |
| `REVIEW_REQUIRED` | 2 |
| `UNSUITABLE` | 1 |

## Fixture results / 样例明细

| Fixture | Language | Capabilities | Claims | Evidence | Findings | Portable result | Bundles |
| --- | --- | ---: | ---: | ---: | ---: | --- | ---: |
| `go_cli` | Go | 1 | 3 | 4 | 0 | `STATIC_READY` | 1 |
| `go_false_positive` | Go | 0 | 1 | 2 | 0 | `UNSUITABLE` | 0 |
| `js_cli` | JavaScript | 1 | 2 | 3 | 0 | `STATIC_READY` | 1 |
| `js_conflict` | JavaScript | 2 | 3 | 5 | 1 | `REVIEW_REQUIRED` | 0 |
| `malicious_readme` | Python | 1 | 2 | 3 | 0 | `STATIC_READY` | 1 |
| `multi_cli` | Python | 2 | 5 | 7 | 0 | `STATIC_READY` | 2 |
| `python_cli` | Python | 1 | 4 | 5 | 0 | `STATIC_READY` | 1 |
| `python_unsafe` | Python | 0 | 1 | 1 | 1 | `REVIEW_REQUIRED` | 0 |
| `setup_cfg` | Python | 1 | 2 | 3 | 0 | `STATIC_READY` | 1 |
| `ts_cli` | TypeScript | 1 | 2 | 3 | 0 | `STATIC_READY` | 1 |

## Interpretation / 解读

The two review cases are intentional safety behavior: a conflicting JavaScript command name and an
unsafe Python entrypoint are not silently converted into Skills. The false-positive Go fixture has
no actionable CLI capability and therefore remains `UNSUITABLE`. The malicious README fixture still
produces a statically supported result because repository prose is data, not system instructions.

两个 `REVIEW_REQUIRED` 样例是有意保留的安全行为：JavaScript 命令冲突和不安全 Python 入口不会被静默
转换成 Skill。Go 误报样例没有可执行 CLI 能力，因此保持 `UNSUITABLE`。恶意 README 样例仍能得到静态支持
结果，因为仓库文档只被当作数据，不会成为系统指令。

`benchmark/corpus.yaml` is a candidate catalog for a future public-repository benchmark. Its
repositories are not included in the table above because this snapshot does not claim to have run
network-based measurements against them.

`benchmark/corpus.yaml` 是后续公共仓库基准集的候选目录。由于当前快照没有声称对这些仓库完成网络实测，
它们不计入上面的统计表。

## Public Repo Benchmark 1.0 / 公共仓库基准集

The public benchmark is now a pinned metadata corpus, separate from the local fixture regression
chart above. It contains 45 repositories: 36 High-Star Core repositories, six unsupported-language
challenge repositories, and three Tier C edge cases. The High-Star Core includes 16 Tier A
repositories (`>=30,000` stars) and 20 Tier B repositories (`>=10,000` stars).

公共基准现在是独立于上方 fixture 回归图的 commit-pinned 元数据 corpus，共 45 个仓库：36 个 High-Star Core、
6 个不支持语言 challenge、3 个 Tier C edge case。High-Star Core 包括 16 个 Tier A（`>=30,000` stars）和
20 个 Tier B（`>=10,000` stars）。

The snapshot at [`../benchmark/repository-metadata.json`](../benchmark/repository-metadata.json) was fetched from
the GitHub API on `2026-09-14`. It stores stars, forks, default branch, archived state, primary
language, license, and an exact commit SHA per repository. Rendering never refreshes GitHub data.

[`../benchmark/repository-metadata.json`](../benchmark/repository-metadata.json) 是 `2026-09-14` 从 GitHub API 获取的快照，
每条记录保存 stars、forks、默认分支、归档状态、主语言、许可证和精确 commit SHA；报告渲染不会重新请求当前 stars。

The current public report says **High-Star Public Repositories Tested: 36**. All 36 Core records
completed source classification and static analysis: 10 are `STATIC_READY`, 20 are
`REVIEW_REQUIRED`, and six are `UNSUPPORTED_LANGUAGE`. The star-weighted repository coverage is
27.9%. `scripts/benchmark_public.py analyze` only analyzes explicitly supplied local checkouts,
and its statuses preserve `NOT_TESTED`, `UNSUPPORTED_LANGUAGE`, `NO_ACTIONABLE_CAPABILITY`,
`REVIEW_REQUIRED`, and `STATIC_READY`. Unsupported Rust, C, Haskell, Perl, and Shell projects are
not mixed into supported-language accuracy.

当前公共报告明确写 **High-Star Public Repositories Tested: 36**。36 个 Core 已完成源码分类和静态分析：
10 个 `STATIC_READY`、20 个 `REVIEW_REQUIRED`、6 个 `UNSUPPORTED_LANGUAGE`，Star-weighted repository coverage 为
27.9%。`scripts/benchmark_public.py analyze` 只分析用户显式提供的本地 checkout，并保留 `NOT_TESTED`、
`UNSUPPORTED_LANGUAGE`、`NO_ACTIONABLE_CAPABILITY`、`REVIEW_REQUIRED`、`STATIC_READY` 等状态。Rust、C、Haskell、
Perl、Shell 项目不会混入受支持语言准确率。

Star-weighted repository coverage is defined only over completed High-Star Core analyses:
`sum(stars of STATIC_READY repositories) / sum(stars of tested repositories)`. It is not user
coverage. Hallucinated executable facts remain `pending` until the ground-truth task runner checks
every command and option against pinned source evidence.

Star-weighted repository coverage 只在完成分析的 High-Star Core 上计算：
`sum(STATIC_READY 仓库 stars) / sum(已测试仓库 stars)`，不代表用户覆盖率。ground-truth task runner 没有核对每个
命令和参数前，幻觉可执行事实保持 `pending`。

The corpus definition, task templates, and GitHub CLI official comparison are maintained in
[`../benchmark/corpus.yaml`](../benchmark/corpus.yaml),
[`../benchmark/ground-truth.yaml`](../benchmark/ground-truth.yaml), and
[`case-studies/github-cli.md`](case-studies/github-cli.md).
