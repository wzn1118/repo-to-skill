# Bound workflows / 可执行工作流

Discovery 1.5 connects scoped parameter facts to structured inputs, multi-step Procedures,
portable Skills, client projections and independent task checks. This is a product capability,
not a claim that arbitrary natural-language goals are understood.

## Start with a discovered command

```bash
python -m pip install -e '.[dev,analysis]'
r2s inspect tests/fixtures/python_cli --output run-output --json
r2s build run_<id> --goal "write a selected output" --workflow workflow.json \
  --target codex --output run-output
```

For the existing `demo` fixture, `workflow.json` can contain:

```json
{
  "format": "r2s-workflow-v1",
  "title": "Use an explicit output path",
  "origin": "user_input",
  "steps": [{
    "command": "demo",
    "path": [],
    "parameters": {"--output": ["result.json"]},
    "expected_observation": "Check the requested output; the fixture only parses arguments"
  }]
}
```

This example demonstrates binding, not a file-producing task: the fixture intentionally only
parses arguments. The Docker tests use a separate synthetic exporting CLI and assert JSON content.
Real formatting/configuration/filtering results live in the versioned workflow measurement.

In the UI, select a discovered command/subcommand and its parameters rather than guessing a goal
string. Unknown parameter semantics are disabled. Jobs persist in SQLite, report stages, support
cooperative cancellation at phase boundaries and preserve attempts on retry. Expired worker leases
become `INTERRUPTED` after 30 seconds and can be retried. Refreshing the page reconnects to the last
job. This is not resumable execution halfway through an analyzer. Downloads recheck the generation
lock and bundle validators; a modified artifact is not silently exported.

## What binding checks

- Exact command path and parameter ownership; no flattening child options to the root.
- Required arguments, recognized arity/types/choices and supported argparse exclusive groups.
- Cobra positionals with matching literal `<name>` tokens and `cobra.ExactArgs(N)`; ambiguous
  usage strings, custom validators and mismatched counts do not supply positional bindings.
- Alias collisions, ambiguous option-like positional values and unknown custom conversion.
- One to sixteen steps of the same executable, with JSON argv rather than shell interpolation.
- Explicit `stdin` and `stdout_file`; supplied inputs and expected observations are not source facts.

Each step includes the CLI interface claims it uses. Parameters come from source evidence;
values have `user_input` or `model_candidate` origin. Runtime observations are separate TaskSpec
results. Defaults are declarations, not a guarantee that later callbacks/configuration cannot
override them. Unknown effects, custom wrappers, inherited parameters and dynamic registration
are not guessed. Cross-executable workflows and inferred error recovery remain unsupported.

`SKILL.md` contains the bound quickstart and output checks. Detailed parameter constraints,
source lines and commit identity are loaded through references. Inventory-only Skills remain
available; they are not accepted as executable task procedures.

For CLIs that open many modules concurrently, `r2s task run ... --open-files 1024` and
`r2s verify ... --open-files 1024` select a bounded file-descriptor allowance. The default remains
128; supported values are 128, 256, 512 and 1024. Task reports record the actual execution policy.
CPU, memory, process, network and source-write restrictions remain independently enforced.

## Independent task validation

Create a definition with `id`, initial `files`, one `expected_exit_codes` item per step, an
`oracle`, and optional exact-version `python_dependencies`. Oracle fields include `files_exact`,
`files_contains`, `json_files`, `absent`, `stdout_exact`, `stdout_contains`, `stderr_contains`.
Empty substring assertions are rejected. Exit zero alone never passes a task.

```bash
r2s task prepare /path/to/portable/tool --definition task-definition.json --report task.json
r2s task run /path/to/portable/tool --definition task.json --source /path/to/pinned/source \
  --image sha256:<installed-image-id> --wheels /path/to/cached/wheels --report preview.json
# Use a new report path and add --execute only after reviewing the task and environment.
```

The prepared task binds source commit, compiler, bundle and Procedure digests. Python dependency
installation is offline, binary-wheel-only, isolated from the host and recorded separately.
Node/native profiles additionally bind the supplied executable, source inventory and dependency
hashes; `--executable` and `--dependencies` supply their already-prepared artifacts. This is a local
identity check, not cryptographic proof that an arbitrary binary was built from that source.
The fzf measurement additionally verifies the retained build receipt. Preparing these artifacts
is separate from analysis; the runner never downloads dependencies or mounts host credentials.

`r2s.repair.repair_workflow` provides a two-attempt default / three-attempt maximum SDK loop.
The candidate callback may change bindings, but cannot remove steps or change tools. Inputs,
expected exits, dependencies and output oracle stay fixed; each failed attempt is retained.
This loop currently supports Python profiles, not an automatic general-purpose repair agent.

## Optional model gateway

```bash
r2s propose run_<id> --goal "export JSON" --config model.json --report proposal-preview.json \
  --output run-output
```

The config specifies `endpoint`, exact `model`, optional `api_key_env`, `timeout_seconds` and
`max_output_tokens`. It is a **custom JSON gateway protocol**, not an assertion of direct OpenAI,
Anthropic or Codex API compatibility. The adapter sends a schema, goal and supported executable
claims only. Execution requires both `--execute` and `--allow-metadata-transfer`. Private metadata
must not be sent without authorization. Redirects, credentials embedded in URLs, oversized replies,
wrong model identities, invented flags and invalid bindings are rejected. Reported token usage is
labelled gateway-reported, not independently metered. Tests use a loopback mock gateway, not a model.

No model or paid API was used for the published task measurements. Goal understanding, contextual
recovery and four-arm Agent utility comparisons remain unmeasured.

## 中文边界

现在可把**明确输入**编译成带参数、多步骤、输入输出检查的 Skill，再运行其实际 argv 验收结果。
不是把标准答案直接塞进文档，也不再仅生成空参数的根命令。
自然语言目标仍需明确参数或可选模型候选；没有已授权配置时不调用外部模型。
任务成功、静态就绪、来源自洽、Agent 收益分别统计；不会用退出码、测试数量或提取数量替代产品效果。
