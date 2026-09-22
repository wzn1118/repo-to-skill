# Retained v21 full native-dependency repair

The complete cache adds the two manifest-declared GNU/Linux native bindings. This attempt
passes **36/36 expanded-scan tasks** and **26/36 standard-scan tasks**. The compiler, runner,
source pins, inputs, oracles and resource limits are unchanged from the original v21 arm.
`runtime-repair-comparison.json` verifies that the only TaskSpec change is the bound dependency
inventory, with five added files and all original regular files preserved.

The three new passes are Prettier JavaScript stdin, write-file and supplied-configuration tasks.
They are **dependency repair**, not analyzer uplift. See the [original 33/36 run](../2026-09-22-v21/README.md)
and [OXC-only 33/36 failure](../2026-09-22-v21-glibc/README.md). Binding, native-load preflight
and independent output-oracle results remain distinct.

## Why this is not the final compiler result

Subsequent adversarial tests find three over-permissive structural matches: dropping an array
destructuring hole, changing an empty literal to a comma, and turning an async method into an
async generator. The matcher should reject all three. These defects do not falsify the observed
task outputs, but they weaken its source-flow justification. The diagnostic record is
[`benchmark/history/2026-09-22-v21-patterns.json`](../../history/2026-09-22-v21-patterns.json).

v22 fixes the matcher and repeats the entire public corpus and workflow arms in new directories.
Use the [new measurement](../2026-09-22-v22-native/README.md) for the current compiler. This
attempt, all earlier failures and their manifests are retained. No Agent comparison, complete
semantic accuracy, or general repository-success claim follows from 36 selected tasks.

中文：补齐两个原生模块后，本次扩大扫描任务实测为 **36/36**。这不是分析器单独提升。
后续对抗测试发现 AST 匹配过宽，故本次保留为历史记录，修复后的 v22 必须重新跑完整语料和任务。
