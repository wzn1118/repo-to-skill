# First native-dependency repair: a retained failure

Adding the declared OXC GNU/Linux binding is **not sufficient**: standard scanning remains
**26/36**, expanded scanning **33/36**. All six Prettier calls bind, but the same three
JavaScript tasks still fail. Their retained stderr now identifies a second missing native
module: `@yuku-parser/binding-linux-x64-gnu/yuku-parser.node`. No failed attempt is replaced
or pooled with a later pass.

This run uses the same compiler, runner, task inputs, source pins, oracles and resource limits
as [v21 with original dependencies](../2026-09-22-v21/README.md). It differs only in the three
OXC package files described by that run's `native-dependency-addition.json`.
`runtime-repair-comparison.json` checks the additive file inventories and the otherwise
identical bound TaskSpecs. This is an environment repair, not analyzer uplift or Agent testing.

## Second preparation, recorded before the next run

The installed `yuku-parser` manifest declares its GNU/Linux optional package at `0.10.1`.
`native-dependency-attempt-2.json` records a separate download with npm lifecycle scripts
disabled. The original dependency cache remains untouched. In a new symlink-preserving cache,
all **10,199** original regular files remain unchanged; the complete repair adds five regular
files across the two declared native packages. The receipt binds the old/new inventories,
preparation reports and package lock.

`complete-native-addition.json` also records an offline native-load preflight in the same
digest-pinned glibc image. Both modules load, but this check is **not a task oracle** and is not
counted as task success. The [subsequent full-task rerun](../2026-09-22-v21-native/README.md)
uses this new cache. Native preparation has explicitly authorized network access; task execution
is offline, non-root, resource-limited, with read-only source and no host credentials.

中文：第一次只补齐 OXC，实测仍为 **33/36**；另外三个任务暴露了 yuku 原生模块缺失。
这里保留失败、stderr、第二次依赖准备回执与离线加载检查。最终结果必须由新一轮完整任务执行
确定，不能以“模块能加载”代替任务通过，也不能把环境修复当作源码分析提升。
