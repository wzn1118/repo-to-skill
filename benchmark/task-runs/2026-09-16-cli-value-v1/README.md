# Reference task validation / 标准解法验证

**30/30 reference solutions pass against pinned source in offline containers. Agent trials: 0.**

| Repository | Tasks | First attempt | Corrected taskset |
| --- | ---: | ---: | ---: |
| psf/black | 10 | 9 | 10 |
| pre-commit/pre-commit | 10 | 10 | 10 |
| cookiecutter/cookiecutter | 10 | 10 | 10 |

The first attempt remains in [attempt-1.json](attempt-1.json), bound to
[cli-value-v1.json](../../tasks/cli-value-v1.json). `black-invalid` correctly returned 123 and left
the invalid file unchanged, but the oracle expected `Cannot parse`; this pinned source writes
`cannot parse`. Only that case-sensitive anchor changes in
[cli-value-v2.json](../../tasks/cli-value-v2.json). The complete second attempt is
[attempt-2.json](attempt-2.json), with all 30 tasks rerun. No failed record was overwritten.

第一轮 29/30：Black 错误文案大小写与断言不一致，退出码和文件保留均符合预期。新任务版本只修正
该文案断言后，全量重跑 30/30。首轮记录保留，不能把重测结果宣传成首测零失败。

The reference argv were authored with the tasks and are not outputs of the Planner or any model.
They are not injected into generated Skills. Assertions check expected files/contents and intentional
rejections rather than counting help/version or exit zero alone. Controlled oracle mutation tests
reject incorrect output. Dependencies and distribution metadata come from cached wheels; the main
module origin is checked against read-only pinned source. No target source executes on the host.

这些结果证明任务和标准解法可以执行，**不证明生成的 Skill 帮助 Agent 完成任务**。
三组模型对照、人工 Skill 签核和留出集效果仍未测量。任务集属于开发集，不能作为泛化成绩。

Reproduction and the planned three-arm protocol: [product-value-evaluation.md](../../../docs/product-value-evaluation.md).
Each report records image ID, taskset/runner/worker/wheel hashes, source locks, imported source origin,
resolved dependency versions, exit codes and bounded command output.

The [manifest](manifest.json) binds both attempts, both taskset versions and the tools. The original
runner is retained under `tool-snapshots/` because `--taskset` was added after attempt 1. It is an
archival copy; restore it at `scripts/run_task_oracles.py` in a separate checkout to replay that
attempt. Run attempt 2 with the current runner and explicit `--taskset` from the reproduction guide.
