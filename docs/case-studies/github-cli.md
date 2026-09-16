# GitHub CLI: generated vs official Skill / 官方 Skill 对照实测

**The generated Skill traces the gh entrypoint but misses its workflows.** The official Skill
contains substantially more task guidance. Smaller output does not demonstrate better quality.

**自动生成版能追溯 gh 入口，但缺少实际工作流。** 官方版包含更多任务指导；不能把体积小当作质量优势。

Both artifacts use source commit `38316c1c4f275030e3df6666382922e75410d68b`.
The [official Skill](https://github.com/cli/cli/blob/38316c1c4f275030e3df6666382922e75410d68b/skills/gh/SKILL.md)
is comparison data, never compiler instructions. The generated artifact is measured before editorial changes.
[Current machine-readable comparison](../../benchmark/runs/2026-09-16-upgrade-v13/official-comparison.json).
The table uses the upgrade-v13 compiler. The [legacy comparison](../../benchmark/official-comparison.json)
is retained separately; the source commit is unchanged.

| Measurement | Generated gh | Official gh |
| --- | ---: | ---: |
| Files | 5 | 1 |
| Total file bytes | 5,351 | 11,958 |
| Selected facts present | 1 / 5 | 4 / 5 |
| Explicit source commit in artifact text/metadata | Yes | No |
| Runnable task pass rate | Not measured | Not measured |
| Unsupported / hallucinated facts | No exhaustive semantic audit | No exhaustive semantic audit |

The official artifact is pinned by this benchmark even though its body does not contain that SHA.
This measures artifact self-description, not whether GitHub maintains version history.

| Preselected fact | Generated structured claim | Official textual mention |
| --- | --- | --- |
| gh | Yes | Yes |
| gh status | No | No |
| gh issue create | No | Yes |
| gh pr list | No | Yes |
| --json | No | Yes |

The denominator is five source-verified facts, not the complete command surface. Text mentions and
structured claims are different representations: the table measures presence, not equivalent execution
quality. The generated gh bundle has one executable fact, with its source hash and commit checked.
The legacy run also emitted a gen-docs helper; upgrade-v10 excludes it from product Skills.
The current gh bundle includes its file lock and explicit scan scope. This run requires review
because source content was excluded by budget; extracting one entrypoint is not full CLI coverage.

官方内容还讨论交互、JSON、分页、仓库定位、搜索、API 回退和副作用。生成版只有通用预览步骤和入口溯源，
没有提取这些业务流程。下一步应补跨文件 Cobra 子命令、选项归属及开发工具过滤。

## Runtime and maintenance limitations / 运行与维护限制

In the legacy runtime attempt, the pinned source required Go 1.27.0 and the isolated builder had Go 1.26.0, so it refused to build;
the attempt is retained in [build-runtime-results.json](../../benchmark/build-runtime-results.json).
No authenticated issue/PR mutations occurred. No model-based A/B task experiment ran.

Repo-to-Skill has tested local drift/update mechanisms, but this case study has not regenerated two
real upstream versions. Official maintenance cadence is likewise not measured.

本案例不声称自动生成版优于官方版。可展示的结论是：溯源链已经存在，真实任务指导仍不足；
固定版本、体积、事实覆盖和构建失败都有可查记录。
