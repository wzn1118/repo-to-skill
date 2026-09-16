# Benchmark results / 实测结果

**Current qualified static run / 当前静态实测： [upgrade-v12](runs/2026-09-16-upgrade-v12/report.md).**

High-Star Public Repositories Tested: **36**, plus 6 Rust challenges and 3 secondary cases.
All 45 pinned snapshots completed; Core represents 1,453,404 cumulative GitHub stars, not unique users.

| Metric / 指标 | v10 rescored / 同口径重算 | v12 |
| --- | ---: | ---: |
| Selected source facts / 所选源码事实 | 13/40 | 16/40 |
| Static task prerequisites / 静态任务前提 | 3/30 | 6/30 |
| Emitted Core facts / 生成事实 | 114 | 275 |

Static generation outcomes remain 20 STATIC_READY, 10 REVIEW_REQUIRED and 6 UNSUITABLE.
All 275 facts await complete semantic review. No runtime task uplift or zero-hallucination claim.
静态前提不是执行成功率，源码哈希可追溯不等于语义正确；275 条事实仍待完整语义审计。

- [Source metadata snapshot / 固定仓库元数据](repository-metadata.json)
- [Versioned scoped gold input / 带命令归属的评测输入](ground-truth-facts-v2.json)
- [Same-input baseline / 同一输入重算基线](runs/2026-09-16-upgrade-v12/baseline-ground-truth-results.json)
- [Verification / 工程验证](runs/2026-09-16-upgrade-v12/verification.json)
- [Manifest / 工件摘要](runs/2026-09-16-upgrade-v12/manifest.json)

The original [report.md](report.md) is an immutable legacy measurement, not the latest compiler result.
[v11](runs/2026-09-15-upgrade-v11/qualification.json) retains an invalid evaluation and mismatching
post-manifest artifacts for audit; it is excluded from headline metrics.
旧报告保留原始字节；v11 的错误评测记录保留并明确排除，不能引用为当前成绩。
