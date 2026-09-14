# GitHub CLI Official Skill Comparison / GitHub CLI 官方 Skill 对照

This case study is a reproducible comparison protocol for `cli/cli`, not a claim that the
automatically generated Skill is better than GitHub's official Skill.

本案例是针对 `cli/cli` 的可复现对照协议，不预先声称 Repo-to-Skill 自动生成版本优于 GitHub 官方版本。

## Fixed inputs / 固定输入

- Repository: `cli/cli`
- Source: the `trunk` commit recorded in [`repository-metadata.json`](../../benchmark/repository-metadata.json)
- Official reference: [`cli/cli/skills/gh/SKILL.md`](https://github.com/cli/cli/blob/trunk/skills/gh/SKILL.md)
- Generated reference: the Repo-to-Skill bundle built from the same pinned source commit
- Tasks: repository status, issue creation/listing, and pull-request data queries

Both Skills must be evaluated against the same task prompts and isolated environment. The official
Skill is treated as a comparison artifact, not as an instruction source for the compiler.

两个 Skill 必须使用相同任务提示和隔离环境评测。官方 Skill 只是对照物，不会成为编译器的指令来源。

## Dimensions / 评测维度

| Dimension | Measurement |
| --- | --- |
| Executable command coverage | Ground-truth commands and required options exercised by task fixtures |
| Unsupported or hallucinated facts | Facts not present in the pinned source or official Skill evidence |
| Provenance | Percentage of executable facts with path, line, commit, hash, and confidence |
| Bundle size | Bytes and files in the installable Skill bundle |
| Task guidance | Task pass rate, clarification rate, and unsafe invocation rate |
| Maintenance | Regeneration after a source commit change and changed evidence references |
| Version pinning | Whether the bundle names the exact source commit used for generation |

## Result status / 结果状态

The repository currently contains the fixed inputs and evaluation protocol. Numeric comparison
results remain `PENDING` until the sandbox and ground-truth task runner execute all three tasks for
both variants. This avoids turning source metadata or bundle size into a fabricated quality claim.

当前仓库已保存固定输入和评测协议。两种版本完成三个任务的沙箱评测前，数值结果保持 `PENDING`；不能把
源码元数据或包大小冒充质量结论。

| Variant | Command coverage | Unsupported facts | Provenance | Task pass rate |
| --- | ---: | ---: | ---: | ---: |
| Repo-to-Skill generated `gh` Skill | PENDING | PENDING | PENDING | PENDING |
| GitHub official `gh` Skill | PENDING | PENDING | PENDING | PENDING |

When results are available, update this file from the benchmark report and retain the pinned
source metadata. Do not report `zero hallucinations` unless every executable fact has been checked
against the task ground truth and its provenance.
