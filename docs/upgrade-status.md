# Upgrade status / 升级进度

Updated: 2026-09-22. **Execution resumed; M0 is not fully accepted and the full upgrade is not complete.**

The [U00–U22 plan](upgrade-plan.md) remains the acceptance contract. “Partial” means there is
reviewable implementation, not that the work package or release gate is passed.

| Package | Status | Evidence and remaining work |
| --- | --- | --- |
| U00 baseline/repros | recorded | Legacy commit and file hashes are frozen in `benchmark/history/2026-09-15-legacy-baseline.lock.json`; historical public reports remain unchanged. Capture-time tools are not a reconstruction of the historical environment. |
| U01 independent validation | partial | Typed provenance, safe YAML, full inventory locks, deterministic re-rendering and install-time checks reject modified bundles. External source authentication/signatures and reference-client conformance are pending. |
| U02 Python bindings | partial | argparse options require a parsed owner; Click options require a recognized command. Aliases, shadowing, same-line parser identities, local framework impersonation, invalid group methods and registrations after parsing are tested. Typer registration, dynamic bindings and complete framework semantics remain incomplete. |
| U03 Go names / roles | partial | Four known v2/v4 name regressions checked against pinned source; pnpm hidden fixtures, bat syntax-test Go module and goreleaser nested test module no longer produce product Skills. Binary/role inference still uses heuristics, not a complete Go command graph. |
| U04 goal matching | partial | Structured workflow inputs and explicit command selection bind to source facts. Optional, separately authorized model gateway candidates pass the same binder. Free natural-language interpretation remains unmeasured. |
| U05 source identity | partial | Raw byte hashes and committed Git blob IDs separated; CRLF, BOM, dirty trees and SHA-256 Git cases tested. Git filters/fsmonitor disabled. Byte-range mappings and complete snapshot attestations remain open. |
| U06 IR v2 / migration | partial | Discovery IR 1.6 adds bounded source-backed regex/enum validation to positional arguments, parameter shapes and workflow bindings. Historical 1.2–1.5 imports remain review-blocked without invented facts. Full runtime semantics, byte ranges and external attestation remain pending. See [contract](discovery-contract.md). |
| U07 workspace scanning | partial | CLI/UI now offer standard and expanded bounded scans; TaskSpec/verify preserve known bundle profiles during source preparation. Partial scans remain review-required. Expanded update automation, resolver consolidation, complete workspace graphs, process quotas and hostile-filesystem race isolation remain pending. See [scope contract](scan-budgets.md). |
| U08 Python command graph | partial | Bounded local import/re-export/alias resolution, direct delegation and argparse helper parameter binding preserve source hops. Parsed argparse subcommands, groups and nested children retain their own option paths; fixed pre-commit exposes 16 child paths and 108 scoped options. Black/blackd adds 43 options and Cookiecutter 21 on fixed pins. Dynamic registration, aliases, parser inheritance, local import semantics and complete framework coverage remain pending. See [implemented boundary](python-entrypoint-graph.md). |
| U09 JS/TS command graph | partial | Optional pinned tree-sitter support for bounded Commander declarations and normalized minimist/vnopts flows. Named/default re-exports, object export projections, CLI/core table forwarding and positional consumption retain source witnesses. The disconnected-table shortcut is removed. Dynamic wrappers, complete framework scopes and whole-program semantics remain unsupported; see [implemented boundary](javascript-option-flow.md). |
| U10 Go AST/Cobra graph | partial | Bounded call/argv traversal, Cobra factories and scoped options include literal ExactArgs positionals, literal scalar switch assignments and structurally verified local string-enum wrappers. Required-flag markers retain their own witnesses. Conditional registration/build-tag files, inherited scope and other custom consumption remain unknown. |
| U11 workflows/documents | partial | Same-tool multi-step Procedures, explicit stdin/output capture, bound quickstarts, input types/choices/required/exclusive checks and acceptance descriptions. Cross-tool composition and evidence-backed automatic recovery remain pending. |
| U12 application jobs/policy | partial | CLI/UI share build service. SQLite jobs/events, two worker slots, cancellation boundaries, attempt history and expired-lease recovery implemented. Hosted approvals, transactional artifact publication recovery and distributed scheduling remain pending. |
| U13 sandbox/replay | partial | Identity-bound TaskSpecs, offline runtime profiles, independent oracles and Python repair SDK. Native benchmark binaries require matching successful build receipts; bounded open-file limits and complete execution policies are recorded. Multi-tenant and universal dependency preparation remain pending. |
| U14 gold/tasks/evaluator | partial | 36 structured-input tasks across the five target tools: first attempt 24 pass, 12 retained failures. A new frozen v23 semantic gold set covers 200 positive operational subjects and 20 negative probes across 10 high-Star repositories; v22 agreement is 69/200, with 118 missing, 10 field mismatches and 3 partial/unknown. This is retrospective agent-curated static evidence, not human review, held-out accuracy or Agent uplift. Existing reference tasks and static prerequisites stay separate. Three registered holdouts retain first outcomes. |
| U15 Agent A/B / official gh | partial | Skill Seekers 3.9.0 offline generation measured on the five fixed snapshots; two-version sample workflows pass on Black/pre-commit. Neither result measures Agent utility or superiority. Four-arm Agent execution, model-enhanced comparison and native-client tests remain pending. |
| U16 UI/API | partial | Browser-tested command selection, parameter binding and locked ZIP download, plus inspect/build/evidence/errors. Persisted background jobs, phase progress, cancel/retry and refresh reconnect exist; native installation/execution still use CLI. |
| U17 install/clients | partial | Codex managed destination, staged update, receipt, rollback API, user-modification rejection and receipt-write failure recovery. The bundled plugin-creator validator passes after manifest fixes; native-client loading, full crash recovery, Windows lock behavior and multi-client install lifecycle pending. |
| U18 packaging/community | partial | Current wheel and dependencies install independently into a fresh environment and pass seven CLI checks in isolated Python mode; package bytes match the wheel. Contribution/security/changelog documentation added. License decision, locked release dependencies, signed publishing and complete platform qualification pending. |
| U19 Beta acceptance | pending | Missing recall, semantic review, workflow, client and user-study gates prevent acceptance. |
| U20 CLI 1.0 | pending | Version compatibility, real upstream drift and stability qualification remain. |
| U21 new domains | pending | Rust remains challenge coverage; no complete Rust/library/HTTP support claim. |
| U22 private/hosted | pending | No multi-tenant deployment, private-model transfer authorization or hosted SLO claim. |

## Current v22 measurements

[The new paired run](../benchmark/workflow-runs/2026-09-22-v22-native/README.md) passes **26/36**
with standard scans and **36/36** with expanded scans after native dependency repair. Both use
an explicit 1,024-open-file allowance. Expanded results: Black 10/10, pre-commit 10/10, fzf 6/6,
Prettier 6/6, gh 4/4. The authored inputs, task oracles and fixed source commits remain unchanged.
This is not Agent uplift. Defaults still use standard scans and 128 open files.

The improvement is separated: **32→33/36** from v19 to v22 in the original recorded environment;
**33→36/36** after two declared GNU/Linux native packages add five files to the Prettier cache.
The comparison verifies that all 10,199 old regular files, the compiler, runner, source, oracles
and resource limits stay unchanged for that repair. Original failures, a rejected symlink-copy
assembly and an insufficient OXC-only repair remain recorded. No attempts are pooled.

[v22 static regression](../benchmark/runs/2026-09-22-upgrade-v22/report.md) completes all 45
pinned snapshots: 36 Core, 20 STATIC_READY, 10 REVIEW_REQUIRED, 6 UNSUITABLE. Selected facts are
**24/40**, task prerequisites **13/30**, and emitted/hash-checked facts **1,130**. These are not
semantic precision. Local verification: **462 passed, 12 subtests passed**, including real Docker
checks and nine browser interactions, with no skips; Ruff, mypy and seven isolated-wheel checks pass.
Linux/Windows CI remains a separate published-commit gate.

The JS option-flow implementation binds both CLI/API tables through the actual minimist/vnopts
path. The v20 unrelated-context-field false negative and three v21 structural-matcher defects
remain in retained diagnostic records with exact compiler-reconstruction patches. v22 fixes
them and repeats all source and task measurements. [JS boundaries](javascript-option-flow.md)
and [Python/Go validator boundaries](source-validators.md) document the supported subset.

Next acceptance gaps: add human-verified and held-out semantic gold, test generalization on unexposed repos,
run configured model arms, verify native-client loading and preserve behavior across real upstream
updates. Complete dynamic framework semantics and full U00–U22 acceptance remain open.

## Historical v14 workflow measurements

The [five-tool run](../benchmark/workflow-runs/2026-09-21-v14/README.md) first passes **24/36**:
Black 9/10, pre-commit 10/10, fzf 5/6, Prettier 0/6 and gh 0/4. The failed bindings and scan-gated
tasks remain in the denominator. This measures generated argv from authored structured inputs,
not Agent goal understanding. The same frozen oracles and all attempts are retained.

Skill Seekers 3.9.0 produces output on all five snapshots in offline mode; sizes and generation
times do not establish correctness or a win. Two real commits each for Black and pre-commit pass
the unchanged sample task (4 checks); minimal invalidation precision and native-client update are
not proven. Holdout first outcomes: dbt-core UNSUITABLE, AWS CLI REVIEW_REQUIRED, Ansible REVIEW_REQUIRED.
The cohort is now exposed and remains outside the 36-Core headline.

v14's public run exposed a TypeScript conflict-propagation defect. Its raw data and qualification
are preserved; the fix marks descendant interface claims conflicted before constructing the graph.
The post-fix [v15 run](../benchmark/runs/2026-09-21-upgrade-v15/report.md) is recorded separately.
All 45 snapshots now complete: selected source facts **23/40**, static prerequisites **12/30**,
and **1,085** emitted Core facts with hash/pin checks. Core outcomes remain 20 STATIC_READY,
10 REVIEW_REQUIRED, 6 UNSUITABLE; full semantic precision remains unmeasured.

The v15 local verification recorded **335 passed, 12 subtests passed**, with all explicitly enabled
Docker/browser checks included. Browser coverage includes eight interactions, now including
parameter binding and locked ZIP download. Ruff and strict mypy pass. The 45 v13 IR files migrate
to review-required 1.5 records without changing originals. Windows CI is a separate platform gate,
not inferred from these Linux results.

## Historical v13 measurements

The [upgrade-v13 run](../benchmark/runs/2026-09-16-upgrade-v13/report.md) runs the same 45 pinned
repositories: 36 high-star Core, 6 Rust challenges and 3 secondary cases.

- Core: **20 STATIC_READY, 10 REVIEW_REQUIRED, 6 UNSUITABLE**; all 36 Core and all 45 total runs
  completed. TypeScript/webpack return partial discovery and remain review-required.
- Core cumulative stars: **1,453,404**; static star-weighted coverage **53.49%**.
- **275 emitted facts / 275 hash-and-pin checks**. All 275 still await complete semantic review.
- Four known Go binary-name regressions match pinned source. This is a targeted regression check,
  not zero hallucination or full semantic precision.
- **16/40 selected source facts; 6/30 static task prerequisites**, unchanged from v12. More parameter
  fields are not counted as extra selected facts or task success.
- **132 emitted options have explicit keyword declarations**, including Black/blackd 41, pre-commit
  36, Cookiecutter 18 and mypy auxiliary CLIs 37. Unknown fields and effective runtime behavior remain unknown.
- Compared with v10, the compiler adds 16 pre-commit command paths; it now retains 108 scoped options
  there and 39 additional options across mypy's auxiliary CLIs. Black and
  Cookiecutter facts retain the same source declarations with an explicit empty root path. This is
  declaration coverage, not semantically verified command completeness.
- Partial scans now block static readiness, including standalone bundle validation/install. The
  26→20 decline from v6 reflects this stricter scope gate, not a measured accuracy decline.
- Compiler fingerprint: `bea4d8f30b8cafe1ad19233c2ec10ca238178590d69b3c082747e2ba71de97dc`.
  The runner checks compiler/harness/dependency identity before and after workers and rejects
  overwrites. Historical metadata is not refreshed when reports are rendered.
- `upgrade-v3` is a retained preliminary run with known helper-entrypoint errors and only an
  end-of-run fingerprint. It does not represent the current compiler.
- `upgrade-v7` was interrupted after an operator cache-preparation failure caused fresh downloads.
  Six partial records and the interruption are retained; they do not contribute to the headline.
- `upgrade-v9` completed but remains preliminary with a known package-attribute resolution defect
  found by controlled negative probes. Its qualification and raw results are preserved; v10 fixes
  the defect and repeats all 45 snapshots.
- `upgrade-v11` is excluded from all headline metrics. Its evaluator incorrectly rejected omitted
  root paths, and evaluation/report files were overwritten after manifest creation. The original
  manifest and raw static results are retained with an explicit invalid-evaluation qualification;
  the mismatching artifacts are not authoritative. v12 uses corrected matching, a new gold-input
  version, write-once evaluation outputs and a manifest generated last.

## Historical v13 verification

**302 passed, 12 subtests passed**, including five real Docker checks and one real Chromium test
covering six UI interactions. Ruff and mypy pass. See the
[verification record](../benchmark/runs/2026-09-16-upgrade-v13/verification.json) for exact versions,
hashes and scope. These controlled tests are separate from public-repository task evaluation.

The wheel and its dependencies install into a new virtualenv through uv, using network downloads
and its package cache. Seven CLI checks run with isolated Python and system site-packages disabled;
installed package bytes match the wheel. This is a Linux clean-environment check, not full release
qualification, hermetic dependency locking or native-client loading.

Docker checks: verified Python invocation, non-root/readonly/no-host-secret isolation, timeout,
output limit, nonzero exit and cleanup. Chromium checks: empty state, inspect, successful build,
evidence view, unrelated goal and rejected outside-root source; no JS exceptions.

```bash
python -m pytest
ruff check .
mypy src

# Explicitly enable integration checks using locally installed tools.
R2S_TEST_IMAGE=sha256:<local-image-id> python -m pytest tests/test_execution_integration.py
R2S_TEST_CHROME=/path/to/chrome-headless-shell python -m pytest tests/test_ui_browser.py
```

The browser check also requires Node 22+. Standard CI skips these integration tests unless the
environment variables are set. Linux container checks do not prove Windows/macOS runtime support.

The bundled plugin-creator validator initially rejected the old list-valued skills field and missing
author/interface metadata. The corrected wrapper passes that independent check. This is a schema
validation result, not a claim of native Codex installation/loading. The layout follows the requested
`codex-plugin/` artifact contract; managed installation uses the manifest name for its destination.

## Integrity and release boundaries

The [product-value task run](../benchmark/task-runs/2026-09-16-cli-value-v1/README.md) is separate:
30 authored reference solutions run on pinned source, without models or generated-Skill use. The
first 29/30 attempt is preserved; only a case-sensitive Black diagnostic assertion is corrected in
taskset v2 before a complete 30/30 rerun. This validates task setup, not Skill benefit. The
[three-arm protocol](product-value-evaluation.md) and three metadata-only holdouts have no results yet.

`BUNDLE.lock.json` establishes self-consistency; it does not independently authenticate upstream
source. Reports retain `not_independently_authenticated`. Local Docker is a trusted-daemon boundary,
not a hosted multi-tenant sandbox. A successful process exit is not an independent task oracle.

The 30 records in `benchmark/taskset-v1.json` are explicitly a **static prerequisite catalog**,
with no execution oracle; they are not completed TaskSpecs. Historical runtime and official-Skill
results are not reused as current runtime or Agent A/B scores.

Next acceptance work: close the retained Prettier/gh bindings and scan boundaries, custom Python/Go
semantics, the 200-fact semantic gold, full four-arm model runner, native-client trials,
external source authentication and full IR v2. The shared local job service and TaskSpec are now
implemented but do not close those acceptance gates.
Human sign-off, model experiments and production hosting
remain separate gates; their absence does not stop independent engineering.
