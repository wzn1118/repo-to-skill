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
