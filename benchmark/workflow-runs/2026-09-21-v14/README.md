# Bound workflow measurement — 2026-09-21

**24/36 frozen tasks pass using generated invocations.**

`attempt-2.json` reruns all 36 inputs after the TypeScript conflict-propagation fix and also
passes **24/36**, retaining the same twelve failures. Both compiler identities and all records
are preserved. This is a post-fix reproducibility check, not repeated Agent trials or an estimate
of stochastic-model variance. The table below describes both attempts; the older 19/20
Python-only pilot stays separately in `../2026-09-16-v14/attempt-1.json` and is not pooled here.
For historical reconstruction, `benchmark/history/2026-09-21-v14-compiler.patch` converts the
published post-fix compiler back to the first attempt's source. Every compiler-file hash was
checked against v14 before archiving this patch. Use a separate checkout, not the current install.

Agent-authored structured inputs, generated argv, fixed upstream SHA, offline Docker and independent file/content oracles. **Not natural-language planning accuracy, Agent success or uplift.**

![Task results](tasks.svg)

| Repository | Passed / selected | Retained failures |
| --- | ---: | --- |
| psf/black | 9/10 | PARAMETER_SEMANTICS_UNKNOWN × 1 |
| pre-commit/pre-commit | 10/10 | none |
| junegunn/fzf | 5/6 | PARAMETER_SEMANTICS_UNKNOWN × 1 |
| prettier/prettier | 0/6 | TASK_BUNDLE_INVALID × 2; WORKFLOW_PARAMETER_UNKNOWN_OR_WRONG_OWNER × 4 |
| cli/cli | 0/4 | WORKFLOW_PARAMETER_UNKNOWN_OR_WRONG_OWNER × 4 |

Inputs: existing Black/pre-commit tasks from `benchmark/tasks/cli-value-v2.json`, plus `benchmark/tasks/cross-language-v1.json`. Oracles were fixed before this run; no failures were removed. Prettier's two valid bindings cannot enter execution because its source scan is incomplete. The other four Prettier tasks and all four gh tasks lack supported bindings. Black custom callbacks and fzf custom argument consumption remain unknown. A blocked task is included in the selected denominator, not called executed.

## Comparisons and boundaries

- v13 validated authored reference argv only. This run compiles explicit task inputs into a Skill and executes the generated Procedure; those measurements are **not** a before/after Agent score.
- Skill Seekers **3.9.0** generated output for all five identical source snapshots, using its `analyze_codebase` API, deep defaults and enhancement level 0. Its broader documentation product is not a CLI-only compiler. No correctness or superiority conclusion follows from file size or generation alone.
- `skill-seekers-summary.json` retains file hashes, sizes, elapsed time, stderr, package identity and the complete raw-output hash. Copied upstream generated text remains local, not republished here.
- Budget: competitor 1 CPU / 1 GiB / 180 seconds per repository; our task runner 1 CPU / 768 MiB / 120-second outer limit per task. Generation and task-execution times are different operations: **no speed ranking**.
- Two real upstream commits each for Black and pre-commit: the unchanged sample workflow and oracle pass on both versions (4/4 checks). Capability drift is conservative; this does not establish minimal rebuild precision or a repair success.
- Registered holdouts: dbt-core UNSUITABLE, AWS CLI REVIEW_REQUIRED, Ansible REVIEW_REQUIRED. First outcomes are retained, no tuning against this cohort preceded this run. They are excluded from the 36-Core headline; the cohort is now exposed.
- Model-enhanced Skill Seekers, upstream-docs Agent, v13 Agent and upgraded Agent arms: **NOT_RUN**, no authorized experimental model gateway configuration. Actual model usage and uplift are null. Loopback gateway contract tests are not model trials.
- Complete 200-fact semantic gold, human sign-off and native-client loading remain pending. Failure taxonomy drives the next work; no zero-hallucination claim.

## Reproduction

```bash
python scripts/measure_bound_workflows.py --snapshots /data/snapshots --wheels /data/wheels \
  --work /data/new-run --output new-attempt.json --image sha256:<installed-image-id> \
  --cross-language benchmark/tasks/cross-language-v1.json --node /path/to/node \
  --node-dependencies /data/prettier/node_modules --fzf-binary /data/fzf/program \
  --fzf-build-report benchmark/build-runtime-results.json --execute
python scripts/measure_skill_seekers.py --snapshots /data/snapshots \
  --dependencies /data/skill-seekers-3.9.0/deps --image sha256:<installed-image-id> \
  --output new-competitor-attempt.json --execute
```

Images, Python wheel set, runtime binaries and JS dependency preparation must precede execution. Hashes and actual argv are in `attempt-1.json`; the fzf build receipt must match. No host target-code execution or dependency downloads happen during tasks.

## 中文结论

已有三种工具的具体任务可由生成调用完成：格式化、配置/manifest 校验、筛选和输出文件。并非五个工具都已经支持完整任务。12 个失败全部保留，尤其不绕过 Prettier 的扫描门槛，也不为 gh 编造参数。模型、人工签核、200 条语义金标和原生客户端链路尚未完成。
