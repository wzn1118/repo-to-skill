# Repo-to-Skill

<a id="english"></a>

**Evidence-driven Repo → Agent Skill compiler.** Turn a local directory, Git repository, or public
GitHub snapshot into portable Skills and a thin Codex skill-only plugin without importing or
executing the target repository.

[![CI](https://github.com/wzn1118/repo-to-skill/actions/workflows/ci.yml/badge.svg)](https://github.com/wzn1118/repo-to-skill/actions/workflows/ci.yml)
[![Python 3.12](https://img.shields.io/badge/python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Static analysis](https://img.shields.io/badge/analysis-static--only-22c55e)](#safety-boundary)

> **Status:** experimental. The compiler has deterministic artifact re-rendering,
> managed install receipts and rollback, isolated `verify` preview/execute policy, a loopback UI for static
> runs, structured workflows, independent task checks and thin client projections. Claude/Cursor native loading is not verified. Agent A/B evidence and
> private/hosted workflows remain incomplete.

[English](#english) · [Latest static run](benchmark/runs/2026-09-21-upgrade-v15/report.md) · [Generated workflow tasks](benchmark/workflow-runs/2026-09-21-v14/README.md) · [Upgrade progress](docs/upgrade-status.md) · [Official gh comparison](docs/case-studies/github-cli.md)

## From command lists to usable workflows

Provide explicit inputs, choose a discovered command/subcommand, and generate a Skill containing
the complete invocation, multi-step instructions, input/output checks and source references.
The CLI and UI share one compiler. Background jobs support phase progress, cancellation/retry
and validated ZIP download. See the [workflow guide](docs/bound-workflows.md).

**Measured: 24/36 five-tool tasks pass with generated invocations**, fixed source commits and
independent output oracles: Black **9/10**, pre-commit **10/10**, fzf **5/6**, Prettier **0/6**,
GitHub CLI **0/4**. All 12 failures are retained, including incomplete scan and unknown binding
failures. These are **structured-input tests, not Agent trials or measured task uplift**.

![Generated task outcomes including failures](benchmark/workflow-runs/2026-09-21-v14/tasks.svg)

The same five snapshots also run through **Skill Seekers 3.9.0**, offline and without model
enhancement. It generates output for all five; this is not a correctness ranking. Two-version
sample workflows and registered holdouts have real results. [Raw measurements and limits](benchmark/workflow-runs/2026-09-21-v14/README.md).

**Latest static benchmark:** all **45** pinned snapshots complete, including **36 high-star Core**
repositories. Selected fact coverage rises from **16/40 → 23/40**; static task prerequisites from
**6/30 → 12/30**. **1,085** emitted facts have hash/pin checks, but full semantic review remains
pending. Core static readiness stays **20/36**. [v15 report](benchmark/runs/2026-09-21-upgrade-v15/report.md).

## Public Repo Benchmark 1.0 — retained v13 baseline

This section preserves the v13 comparison point; use the linked v15 report and workflow results
for the current upgrade. Static generation and task execution are deliberately separate metrics.

**High-Star Public Repositories Tested: 36** — plus 6 Rust challenges and 3 secondary edge cases.
All 45 source snapshots are pinned and verified. The Core represents **1,453,404 cumulative GitHub
stars**, using the saved `2026-09-14` snapshot; stars are not unique users.

| Measured result | Value |
| --- | ---: |
| Core static generation | 20 STATIC_READY · 10 REVIEW_REQUIRED · 6 UNSUITABLE |
| Star-weighted coverage, using static-generation status | 53.5% |
| Ground truth across 10 repositories | **16 / 40 selected facts covered** |
| Tasks with all selected static prerequisites covered | **6 / 30** |
| Generated executable facts indexed / hash-and-pin checked | 275 / 275; full semantic review pending |
| Four known Go module-suffix name regressions | 4 / 4 corrected against pinned source |

STATIC_READY does not guarantee correct commands or successful tasks. The audit caught Go module
suffixes becoming executable names (`v2`, `v4`), test fixtures becoming Skills, and missing subcommands.
The ground truth is **agent-curated**, not human sign-off. No zero-hallucination or
with/without-skill improvement claim is made. Failures are published alongside successes.

The versioned [upgrade-v13 report](benchmark/runs/2026-09-16-upgrade-v13/report.md) contains the
compiler fingerprint, raw static results, targeted name checks and explicit limits. All 45 runs now
complete; TypeScript and webpack return partial discoveries with unknown regions. Selected fact recall
remains **16/40**, unchanged from v12. The current improvement is richer option declarations, not
a claimed recall or task-success increase. The
older headline remains in `benchmark/report.md` as a legacy measurement; it is not overwritten.

The v13 baseline's Discovery IR 1.4 retains the bounded Python command-path graph: imports, aliases, direct delegation
and supported argparse helper calls preserve evidence chains. On the fixed corpus it retains 16
`pre-commit` child paths and 108 path-owned options, plus 39 options across mypy's auxiliary CLIs.
Child options stay off the root command. All **275 emitted facts remain pending complete semantic
review**. It adds explicit source parameter declarations to 132 emitted options, including 95 across
Black/blackd, pre-commit and Cookiecutter. Missing fields and effective runtime semantics remain unknown.
[Workspace scan budgets](docs/scan-budgets.md) still require partial discoveries to remain under review.
The [v11 preliminary record](benchmark/runs/2026-09-15-upgrade-v11/qualification.json) retains an
evaluation error and a manifest-ordering failure. It is excluded from the headline. v12 reruns all
45 snapshots with corrected scope matching and write-once evaluation artifacts.

**Product-value milestone:** [30 reference tasks](benchmark/task-runs/2026-09-16-cli-value-v1/README.md)
now run against pinned source in offline containers. The first attempt passed 29/30; correcting one
oracle's error-message casing produced 30/30 on a full rerun. These are authored reference solutions,
**not generated-Skill or Agent success rates**. Agent trials and human sign-offs remain zero.
Task-specific goals such as “use demo to export results” now return NEEDS_INPUT instead of a generic
empty-argument procedure. See the [three-arm evaluation protocol and held-out registry](docs/product-value-evaluation.md).

![Explicit parameter declarations and separately measured reference task checks, not Agent uplift](docs/assets/product-value.png)

```bash
python scripts/public_measure.py run --work /path/on/data-disk/new-run --output benchmark/runs/new-run/results.json
python scripts/public_evaluate.py --work /path/on/data-disk/new-run --results benchmark/runs/new-run/results.json --output-dir benchmark/runs/new-run
python scripts/public_fact_audit.py --work /path/on/data-disk/new-run --results benchmark/runs/new-run/results.json --output benchmark/runs/new-run/fact-audit.json
python scripts/render_run_report.py --run benchmark/runs/new-run
```

Python 3.12+ is required; chart export also needs `matplotlib`. Full reproduction, runtime policy,
per-repository failures and raw JSON are in the [benchmark report](benchmark/report.md).
Install benchmark tooling with `python -m pip install -e '.[dev,benchmark]'`.
The historical v13 [official gh comparison](docs/case-studies/github-cli.md) finds 1/5 selected facts in the generated
Skill versus 4/5 textual mentions in the official Skill. The former 27.9% bootstrap report is
[retained and superseded](benchmark/history/2026-09-15-bootstrap-results.json).

## Why this exists

Repository-to-Skill conversion is easy to make look intelligent and hard to make trustworthy. A
model can invent a flag, mistake README prose for an API contract, or silently package a command
from the wrong commit. Repo-to-Skill makes the trust boundary explicit:

```text
Snapshot → Inventory → Evidence → Claim → Capability → Procedure → Skill bundle
```

Every executable fact in a generated bundle must point back to source evidence with a path, line
range when available, content hash, commit/blob identity, extractor, and confidence. The planner
and generator consume the IR; they do not inspect raw repository text to invent new facts.

## What works now

| Area | Current implementation |
| --- | --- |
| Sources | Local directories, clean local Git snapshots, public GitHub HTTPS URLs |
| Static analyzers | Python, JavaScript/TypeScript, Go CLI entrypoints |
| Python | PEP 621/Poetry/`setup.cfg`, bounded static import/delegation graph, parsed argparse command paths/helper bindings and Click command options |
| JavaScript/TypeScript | Manifest bins and optional bounded AST analysis: Commander and selected declarative option tables |
| Go | Root/`cmd` main packages, bounded AST calls/argv switches and direct Cobra factories; dynamic/inherited scope remains unknown |
| Outputs | Portable Skills, Codex plugin; experimental Claude/Cursor directory projections |
| Integrity | Strict nested IR/schema, source and graph checks, scoped compiler identities, generation locks and SQLite artifact index |
| Scan scope | Workspace budgets, explicit skipped regions, indexed scan.json, CLI/UI and bundle scope; partial scans require review |
| Updates | File/Capability drift reports and goal-scoped capability delta builds |
| UI | Persisted jobs, command/parameter selection, build, phase cancel/retry, validation and locked ZIP download |
| Execution | Explicit local Docker, identity-bound TaskSpec, independent output oracles and bounded Python repair SDK |
| Installation | Codex destination receipts, conflict checks, staged update and rollback library API |

Complete JavaScript/TypeScript and Go framework coverage, independent external Skills validation,
model-based evaluation and hosted/private workflows remain incomplete. The full scope
is tracked in [`docs/implementation-status.md`](docs/implementation-status.md) and
[`docs/upgrade-status.md`](docs/upgrade-status.md).

## Quickstart

### 1. Install

```bash
git clone https://github.com/wzn1118/repo-to-skill.git
cd repo-to-skill
python -m venv .venv

# macOS/Linux
. .venv/bin/activate

# Windows PowerShell
# .venv\Scripts\Activate.ps1

python -m pip install -e '.[dev,analysis]'
```

The editable install provides the `r2s` command, strict validation dependencies and development checks.

### 2. Inspect once

```bash
r2s inspect tests/fixtures/python_cli --output run-output --json
r2s runs --output run-output
```

`inspect` creates a goal-independent Discovery Run. Reuse its `run_<id>` for multiple goals and
client targets without rescanning the source.

Historical 1.2/1.3 records can be explicitly imported with `r2s migrate old-run/discovery.json --output migrated-runs`.
This preserves the source and produces a new review-required run; see the [migration contract](docs/discovery-contract.md).

### 3. Plan and build

```bash
r2s plan run_<id> --goal "Use the demo CLI" --output run-output --json
r2s build run_<id> \
  --goal "Use the demo CLI" \
  --target codex \
  --output run-output
```

The build emits portable Skills plus a Codex wrapper under the compilation directory. A generated
workflow previews a command and uses only evidence-backed options or arguments explicitly supplied
by the user.

### 4. Validate and inspect locally

```bash
r2s validate run-output/run_<id>/compilations/<compile-id>/codex-plugin
r2s explain run_<id> --claim <claim-id> --output run-output
r2s ui --output run-output --open
```

The workbench defaults to `http://127.0.0.1:8765/`. Enter a local source or public GitHub URL,
inspect capabilities, provide a goal and build a Skill. Local sources are restricted to the current
directory; add `--source-root /path/to/projects` to allow another root. Installation and execution
use the CLI. Static jobs now persist progress and support phase cancellation, retry and ZIP download.

![Browser-tested workflow selection and validated download using the local Python fixture](docs/assets/workbench-workflows.png)

For a generated Python Skill, preview an explicit invocation with an already installed Linux image:

```bash
r2s verify /path/to/portable/demo --source tests/fixtures/python_cli \
  --image python:3.12-slim --arg=--output --arg=value
```

Add `--execute --report /path/to/new-execution.json` to run it. The runner resolves the local image
to its digest, copies filtered source into a temporary snapshot, disables container networking and
records output, limits and cleanup. It never pulls images or installs dependencies. A zero exit code
does not prove a task passed; Go/build-dependent entrypoints still require a supported build profile.

### 5. Try a public GitHub snapshot

```bash
r2s inspect https://github.com/owner/repo --ref main --output run-output --json
r2s update run_<old-id> \
  --repo https://github.com/owner/repo \
  --ref main \
  --goal "Use changed commands" \
  --target codex \
  --output run-output
```

Remote resolution pins a detached commit. Only public `https://github.com/<owner>/<repo>` URLs are
accepted by the current walking slice.

## Generated artifacts

```text
run-output/run_<id>/
├── discovery.json
├── source.lock.json
├── inventory.json
├── evidence.json
├── claims.json
├── capabilities.json
├── run.json
└── compilations/<compile-id>/
    ├── portable/<skill-name>/
    │   ├── SKILL.md
    │   ├── PROVENANCE.json
    │   ├── BUNDLE.lock.json
    │   └── references/
    └── codex-plugin/
        ├── .codex-plugin/plugin.json
        └── skills/<skill-name>/
```

`SKILL.md` stays short. Detailed options and source lineage live in references and
`PROVENANCE.json`; the Codex adapter wraps the same portable bundle rather than maintaining a
second analysis path.

## Safety boundary

- Discovery never imports, builds, or executes target repository code.
- README text, comments, manifests, and other repository instructions are treated as untrusted data.
- Symlink escapes, unsafe refs, command/path traversal, credential paths, oversized files, and
  invalid cached artifacts fail closed.
- Sensitive paths such as `.env`, SSH keys, and package credentials are excluded; their values are
  never serialized.
- Generated executable facts require Claim → Evidence provenance. No evidence means no generated
  command, flag, API field, or environment variable.
- Installation is preview-only unless the caller explicitly passes `--execute`.

Read the [threat model](docs/threat-model.md) before adding network access, dependency installation,
private-repository support, or extending the runtime sandbox.

## Architecture

```text
CLI / local UI
      ↓
Source Resolver → Scanner → Evidence IR → Planner → Generator
                                      ↓
                            Validators → Artifact Store
                                      ↓
                         Portable Skill + Codex Adapter
```

The CLI is orchestration only. Source resolution, scanning, analyzers, planning, generation,
validation, storage, and the dashboard each have separate module boundaries documented in
[`docs/architecture.md`](docs/architecture.md).

## Development

```bash
python -m pytest
ruff check .
mypy src
python scripts/measure_benchmark.py
```

CI runs pytest, Ruff and mypy on Python 3.12 for Ubuntu and Windows. `measure_benchmark.py` only
analyzes committed fixtures. Public measurements are separate, opt-in scripts documented in the
[reproduction guide](docs/benchmark.md); network downloads and Docker execution do not run in CI.

## Roadmap

1. Stabilize the IR and evidence contract across more real repositories.
2. Add deeper JavaScript/TypeScript and Go extraction without changing the IR.
3. Expand the product sandbox from smoke verification to replayable TaskSpec execution and add external Skills validation.
4. Add private-repository authorization, hosted artifact storage, and model-based evaluation.
5. Add client discovery compatibility tests and then maintain Claude/Cursor adapters as thin projections over the same portable bundle.

## 中文

**Repo-to-Skill 是一个证据驱动的 Repo → Agent Skill 编译器。** 它把本地目录、本地 Git 仓库或
公共 GitHub 快照，编译为可移植 Agent Skills 和轻量 Codex skill-only plugin；分析阶段不会导入
或执行被分析仓库的代码。

> **当前状态：** 可运行的实验版本。已加入严格产物重渲染、安装 receipt、隔离 `verify`、
> 可写的 loopback 工作台、结构化多步骤流程和独立任务验收，以及 Codex/Claude/Cursor 薄适配器；Agent A/B、
> 私有仓库和托管流程仍未完成。

### 核心价值

**新实测：五个工具、36 个任务，生成调用通过 24 个。** Black 9/10、pre-commit 10/10、fzf 5/6，
Prettier 0/6、GitHub CLI 0/4；12 个失败全部保留。参数由明确输入绑定、验收规则独立固定，
不是 Agent 成功率，也没有宣称“零幻觉”。[完整结果及复现](benchmark/workflow-runs/2026-09-21-v14/README.md)。
现在可选择命令和参数、生成带调用与输出检查的 Skill、查看持久化进度、取消/重试、下载已校验产物。
[操作指南与当前限制](docs/bound-workflows.md)。

最新 v15 静态复测完成全部 45 个固定快照，含 36 个高 Star 核心仓库。所选事实覆盖
**16/40 → 23/40**，静态任务前提 **6/30 → 12/30**；1,085 条生成事实完成哈希/commit 核对，
**完整语义审查仍未完成**。Core 静态就绪仍为 20/36，不能把事实数量当作任务成功率。

普通的“README → 提示词”方案很容易编造参数、混淆文档与真实 API，或把错误 commit 的命令写进
Skill。Repo-to-Skill 固定一条可审计链路：

```text
Snapshot → Inventory → Evidence → Claim → Capability → Procedure → Skill bundle
快照     → 清单     → 证据     → 断言  → 能力       → 步骤      → Skill 包
```

生成物中的每一个可执行事实，都必须回溯到源码证据：文件路径、行号（可得时）、内容哈希、commit/blob
身份、提取器和置信度。Planner 和 Generator 只消费统一 IR，不从原始文本临时编造事实。

### 当前支持

- 输入：本地目录、干净的本地 Git 快照、公共 GitHub HTTPS URL。
- 静态分析：Python、JavaScript/TypeScript、Go CLI 入口。
- Python：PEP 621、Poetry、`setup.cfg`，静态导入/别名/委派证据链，argparse 子命令及 helper 参数绑定、Click 命令参数。
- JavaScript/TypeScript：manifest bin；可选 AST 解析部分 Commander 和声明式参数表。
- Go：根目录与 `cmd/<name>` 主包、有限 argv/调用图与 Cobra 工厂，条件注册和继承不作猜测。
- 输出：Portable Agent Skills 与薄 Codex skill-only plugin 适配器。
- 工程能力：内容寻址 Discovery Run、source lock、拆分 IR 校验、SQLite artifact index、漂移报告、
  按 Capability 的增量构建，以及可提交静态分析与生成任务的本地 UI。
- 验证与分发：产物重渲染核验、文件锁、Codex 安装 receipt/更新/回滚；显式 Docker 执行与清理记录。
- Claude/Cursor 目前仅输出目录投影，尚未验证原生客户端加载。

完整 JS/TS、Go 框架覆盖、独立 Skills 规范校验、Agent 效果、私有仓库和托管流程仍在
路线图中，详见 [`docs/implementation-status.md`](docs/implementation-status.md) 与
[`docs/upgrade-status.md`](docs/upgrade-status.md)。

### 中文快速开始

```bash
git clone https://github.com/wzn1118/repo-to-skill.git
cd repo-to-skill
python -m venv .venv

# macOS/Linux
. .venv/bin/activate

# Windows PowerShell
# .venv\Scripts\Activate.ps1

python -m pip install -e '.[dev,analysis]'
r2s inspect tests/fixtures/python_cli --output run-output --json
r2s runs --output run-output
r2s plan run_<id> --goal "使用 demo CLI" --output run-output --json
r2s build run_<id> --goal "使用 demo CLI" --target codex --output run-output
r2s ui --output run-output --open
```

`inspect` 先生成与目标无关的 Discovery Run；之后可以复用 `run_<id>` 为不同目标和客户端编译，避免
重复扫描。`r2s ui` 默认只绑定 `127.0.0.1`，可输入仓库、静态分析、按目标生成，并查看证据和验证结果。
本地来源限于当前目录，可用 `--source-root /path/to/projects` 增加允许范围。安装和执行通过 CLI；
工作台已支持后台任务、阶段取消/重试、参数选择和产物下载。

### 实测统计

首页展示固定公共仓库实测，受控 fixture 与公共 headline 分开统计。真实浏览器和 Docker
回归的范围、复现命令和局限见 [升级状态](docs/upgrade-status.md)，不用于推算 Agent 任务成功率。

```bash
PYTHONPATH=src python scripts/measure_benchmark.py
python -m pytest
```

逐样例回归数据见 [`docs/benchmark.md`](docs/benchmark.md)，公共结果见 [`benchmark/report.md`](benchmark/report.md)。

### 公共高 Star 基准集（v13 历史对照）

本节保留 v13 的对照口径，并非当前编译器的最新成绩；最新结果以 [v15 报告](benchmark/runs/2026-09-21-upgrade-v15/report.md)
和首页五工具任务结果为准，静态生成、执行验收与 Agent 效果分别统计。

首份 Public Repo Benchmark 1.0 不用小型 toy repo 凑成功率，而是固定真实、高使用量、CLI 边界复杂的公共仓库。
`2026-09-14` 的 GitHub 元数据快照包含 **36 个 High-Star Core Repository**（Tier A 16 个、Tier B 20 个）、
**1,453,404 个累计 stars**、10 个 ground-truth 仓库、6 个不支持语言 challenge 和 3 个 Tier C edge case。
Stars 只描述 corpus 的开源影响力，不等于独立用户数。

**High-Star Public Repositories Tested: 36**。45 个真实源码快照（含 challenge/edge）均已固定并验证；
历史 [upgrade-v13](benchmark/runs/2026-09-16-upgrade-v13/report.md) 的 Core 结果为 20 个 `STATIC_READY`、
10 个 `REVIEW_REQUIRED`、6 个 `UNSUITABLE`，按静态状态计算的 Star-weighted coverage 为 **53.5%**。
45 个运行全部完成；TypeScript、webpack 现在返回部分发现结果，未知区域明确保留。

v13 的 IR 1.4 在 [Python 子命令图](docs/python-entrypoint-graph.md) 上增加显式参数声明，132 个选项带有
至少一个可静态提取的字段；其中 Black/blackd、pre-commit、Cookiecutter 合计 95 个。
**302 项本地测试和 12 个子测试通过**，包含真实 Docker 和浏览器检查。
部分扫描在独立校验、安装时仍保持 `REVIEW_REQUIRED`。45 份历史 IR 显式迁移后仍需审核，原文件保持不变。
[v11 前置记录](benchmark/runs/2026-09-15-upgrade-v11/qualification.json)保留评测误判和 manifest 顺序错误，
不参与首页成绩；v12 修复口径后重新跑全部仓库，并禁止覆盖已封存的评测产物。

v13 的 40 条所选源码事实仍覆盖 **16 条**，与 v12 一致，没有把增加参数字段包装成召回率提升。
30 个任务中 **6 个**具备所选静态前提，这不是执行成功率。新版本生成 **275 条**可执行事实，
均通过哈希和 commit 核对。pre-commit 提取出 16 条子命令路径与 108 条带归属的选项；mypy 的辅助 CLI 新增 39 条选项。
四项 Go 后缀命名回归仍通过定向核对。**275 条事实仍待完整语义审计**，不宣称真实任务成功率提高。
旧版的 91 条事实、4 个已确认错误及四项目 10 项运行检查保留在 legacy 报告，不移作新版运行成绩。

另建立 [三个工具、各十个真实任务](benchmark/task-runs/2026-09-16-cli-value-v1/README.md)，用文件内容、
修改保留和预期拒绝验证标准解法。第一轮 29/30，保留失败；修正一个错误信息大小写断言后全量重跑 30/30。
**这是标准解法验证，不是生成 Skill 或 Agent 的成功率**。模型三组对照与人工签核尚未执行。
v13 的“使用 demo 导出结果”返回 `NEEDS_INPUT`，不再假装已理解任务。三个留出仓库在 v13 阶段只登记元数据和 SHA；
9 月 21 日已保留首次源码测量，仍不计入 headline，见 [产品价值评测协议](docs/product-value-evaluation.md)。

ground truth 由 Agent 按源码整理，不冒称人工签字；没有提前写“零幻觉”，也没有声称优于官方 Skill。
旧版 27.9% 报告因 Python 3.10 fallback、未验证缓存和未实际扫描的 challenge 已被更正，历史数据保留。

```bash
python scripts/public_measure.py run --work /path/on/data-disk/new-run --output benchmark/runs/new-run/results.json
python scripts/public_evaluate.py --work /path/on/data-disk/new-run --results benchmark/runs/new-run/results.json --output-dir benchmark/runs/new-run
python scripts/public_fact_audit.py --work /path/on/data-disk/new-run --results benchmark/runs/new-run/results.json --output benchmark/runs/new-run/fact-audit.json
python scripts/render_run_report.py --run benchmark/runs/new-run
```

基准输入见 [`benchmark/corpus.yaml`](benchmark/corpus.yaml) 和 [`benchmark/ground-truth.yaml`](benchmark/ground-truth.yaml)，
快照见 [`benchmark/repository-metadata.json`](benchmark/repository-metadata.json)，GitHub CLI 官方 Skill 对照见
[`docs/case-studies/github-cli.md`](docs/case-studies/github-cli.md)。

### 安全边界

- discovery / compilation 不导入、不构建、不执行目标代码；独立 runtime benchmark 需显式 `--execute` 并使用隔离容器。
- README、注释、manifest 和仓库内指令全部视为不可信数据。
- 符号链接逃逸、不安全 ref、路径穿越、凭证路径、超大文件和损坏缓存默认 fail closed。
- `.env`、SSH key、包管理器凭证等敏感路径不会进入分析输入，值不会被序列化。
- 没有 Claim → Evidence 溯源，就不会生成命令、参数、API 字段或环境变量。
- 安装默认只预览；只有显式传入 `--execute` 才执行。

新增网络访问、依赖安装、私有仓库或运行时沙箱前，请先阅读 [`docs/threat-model.md`](docs/threat-model.md)。

### 开发与路线图

```bash
python -m unittest discover -s tests -q
ruff check .
mypy src
python scripts/measure_benchmark.py
```

CI 在 Python 3.12 的 Ubuntu 和 Windows 上运行同一组检查。后续优先级是扩大真实仓库基准集、完善 JS/TS
与 Go 提取器、增加外部规范校验和隔离沙箱，再接入私有仓库、托管存储、模型评测以及 Claude/Cursor 薄适配器。

## License

This repository does not declare a project license yet. Generated artifacts remain subject to the source
repository's license and the applicable client distribution rules.
