# GitHub CLI: generated vs official Skill / 官方 Skill 对照实测

## Current workflow result (2026-09-22)

The [v19 run](../../benchmark/workflow-runs/2026-09-22-v19/README.md) passes **4/4 gh tasks**
with the expanded scan budget: Bash/Zsh completion, default protocol lookup and a two-step local
alias workflow. v17 passed 2/4 under the same budget. A structurally verified local string-enum
helper now supplies the completion shell flag's source-backed arity and choices. The completion
oracles check output-script markers; they do not exercise interactive completion inside shells.
The current standard scan passes 0/4 because its remaining scan gap blocks execution.
No Agent comparison against the official Skill is claimed.

## Retained workflow-stage update (2026-09-21)

The bounded Cobra analyzer now extracts substantially more scoped interface declarations, but
the four frozen gh workflow tasks all fail parameter binding: completion shell selection,
config positional input and local alias composition are not yet fully represented. gh's
partial source scan is also a separate readiness gate. [Five-tool task evidence](../../benchmark/workflow-runs/2026-09-21-v14/README.md).
This is a concrete limitation, not a claim that the official Skill was beaten. The post-fix
[v15 static comparison](../../benchmark/runs/2026-09-21-upgrade-v15/official-comparison.json)
uses the same upstream pin. No official-vs-generated Agent task experiment has run.

## Retained v13 comparison

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

## Retained v16 local tasks / 保留的 v16 本地任务

The [v16 retained task run](../../benchmark/workflow-runs/2026-09-22-v16/README.md) builds
the same pinned gh source using Go 1.27.1, then passes two generated workflows offline:
`gh config get git_protocol` returns the expected `https`, and `gh alias set pv 'pr view'`
followed by `gh alias list` exposes the saved alias. Home/config storage is isolated from the host.
Literal Cobra positional validators and source usage names provide the binding evidence.
The two completion tasks still cannot bind the custom wrapped shell flag; all four remain selected.

This uses the explicit expanded scan profile: the standard budget still leaves one oversized
test archive unscanned and blocks task preparation. The first two builds fail (tmpfs capacity,
then wall timeout); their receipts and the successful cached retry are retained. This is a local
task result, not a model comparison with the official Skill. No authenticated GitHub writes occur.

中文：生成的工作流已可完成本地配置读取和两步别名管理。需要扩大扫描预算，补全未扫描区域；
补全脚本的自定义参数包装仍未支持。上述结果不代表优于官方 Skill，也不替代 Agent 对照实验。

## Runtime and maintenance limitations / 运行与维护限制

In the legacy runtime attempt, the pinned source required Go 1.27.0 and the isolated builder had Go 1.26.0, so it refused to build;
the attempt is retained in [build-runtime-results.json](../../benchmark/build-runtime-results.json).
No authenticated issue/PR mutations occurred. No model-based A/B task experiment ran.

Repo-to-Skill has tested local drift/update mechanisms, but this case study has not regenerated two
real upstream versions. Official maintenance cadence is likewise not measured.

本案例不声称自动生成版优于官方版。可展示的结论是：溯源链已经存在，真实任务指导仍不足；
固定版本、体积、事实覆盖和构建失败都有可查记录。
