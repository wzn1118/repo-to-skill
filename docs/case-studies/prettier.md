# Prettier: from option names to parser-backed invocations

Prettier's CLI is not a simple chain of `.option(...)` calls. The fixed source uses a CLI
declaration table, a core API table, support-info assembly, API-to-CLI name conversion, a
minimist configuration builder and vnopts schema normalization. A filename list also travels
through the parser's `_` field before becoming the context's file patterns.

Source pin: `0017ecf34df0b6a0bdd156bb02fe62603d4aa682`. The important source boundaries are
[`get-context-options.js`](https://github.com/prettier/prettier/blob/0017ecf34df0b6a0bdd156bb02fe62603d4aa682/src/cli/options/get-context-options.js),
[`support.js`](https://github.com/prettier/prettier/blob/0017ecf34df0b6a0bdd156bb02fe62603d4aa682/src/main/support.js),
[`parse-cli-arguments.js`](https://github.com/prettier/prettier/blob/0017ecf34df0b6a0bdd156bb02fe62603d4aa682/src/cli/options/parse-cli-arguments.js)
and [`normalize-options.js`](https://github.com/prettier/prettier/blob/0017ecf34df0b6a0bdd156bb02fe62603d4aa682/src/main/normalize-options.js).

## Why the old implementation was insufficient

v19 passes the two file-classification tasks but cannot bind the four formatting/configuration
tasks. The old table recognizer sees only part of the interface. More importantly, a nearby
name-normalization expression could unlock an unrelated table without proving CLI consumption.

The replacement first establishes a reachable entry, then follows actual symbol/export and
table transformations into the parser and schema constructors. It uses a bounded structural
rule family, not repository-name checks, documentation regexes or guessed familiar flags.
Unrecognized transformations remain unsupported. See the
[precise implementation boundary](../javascript-option-flow.md).

## Independent task checks

The frozen tasks distinguish capability binding from observable behavior:

| Task | Independent check |
| --- | --- |
| JavaScript and JSON file information | Parse reported file classification |
| JSON stdin formatting | Compare the formatted output with the frozen oracle |
| JavaScript stdin formatting | Check the output selected by the supplied stdin filename |
| Write a JavaScript file | Compare the resulting file contents |
| Apply a supplied configuration | Verify the independently expected formatting result |

The original input files, source pin and oracles are not edited to fit the implementation.
Runtime dependencies and the actual Node executable are bound by hash; execution is offline
with read-only source and no host credentials. Expanded scanning is explicitly required here:
the normal scan budget still excludes source content and blocks execution.

For example, the generated JSON-formatting Skill now contains an actual invocation, not just
a flag list:

```json
["prettier", "--parser", "json"]
```

It supplies `{"a":1}` on stdin and records the requested exact-format check. The Skill calls this
check **not yet observed** at generation time; the separate execution report records whether it
passes. Installation is still a prerequisite, and a failed output check requires stopping rather
than pretending exit-code success means the task succeeded.

The intermediate [v20 static run](../../benchmark/runs/2026-09-22-upgrade-v20/README.md)
also exposes a real false negative: assigning `context.logger` was mistakenly treated as
replacing the entire context. Its regression and reduced coverage are preserved. The fixed
compiler repeats all public snapshots rather than editing that result.

Later mutation tests reveal three overly broad v21 structural matches, involving an array hole,
a punctuation literal and an async generator method. The
[diagnostic](../../benchmark/history/2026-09-22-v21-patterns.json) is preserved; v22 distinguishes
these syntax cases and repeats both public-source discovery and actual task execution. A successful
task run does not exempt the analyzer from negative testing.

## Measured outcomes

| Fixed taskset | Prettier | All five tools | Interpretation |
| --- | ---: | ---: | --- |
| v19, original dependencies, expanded scan | 2/6 | 32/36 | Previous compiler |
| v22, original dependencies, expanded scan | 3/6 | 33/36 | Same recorded environment; JSON formatting is newly passing |
| v22, repaired dependencies, expanded scan | 6/6 | 36/36 | Two native-package additions; same compiler and oracles |
| v22, repaired dependencies, standard scan | 0/6 | 26/36 | Source-budget gate retained |

The original dependency cache has musl bindings; the frozen task image uses glibc. Supplying only
OXC's declared GNU/Linux binding reveals a second missing yuku binding. Both failed attempts are
retained. The final preparation adds five files for two exact manifest-declared packages and
preserves all 10,199 original regular files. Complete native loading is checked offline, then
all 36 task outputs are independently verified again. The
[checked transitions and reproduction commands](../../benchmark/workflow-runs/2026-09-22-v22-native/README.md)
separate analyzer improvement from this runtime repair.

## What this does not prove

These tasks are authored structured inputs, not natural-language planning trials. They do not
cover every Prettier option, arbitrary plugins, experimental CLI behavior, later business-level
conflicts, all dependency versions or all similar repositories. Renamed synthetic fixtures test
structural matching; they are not an unseen-project holdout study. No superiority over a human
or official Skill is inferred, and no zero-hallucination claim follows.

中文：关键改进不是“补几个熟悉的参数”，而是追踪参数表如何变成实际解析规则。源码推导、任务
输出、跨仓库泛化和 Agent 效果是四类证据。这里保留反例、旧失败与预算门槛，不把受控任务通过
包装成通用 JS 支持或 Agent 收益。
