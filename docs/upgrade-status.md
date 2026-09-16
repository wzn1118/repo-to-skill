# Upgrade status / 升级进度

Updated: 2026-09-16. **Active goal; M0 is not fully accepted and the full upgrade is not complete.**

The [U00–U22 plan](upgrade-plan.md) remains the acceptance contract. “Partial” means there is
reviewable implementation, not that the work package or release gate is passed.

| Package | Status | Evidence and remaining work |
| --- | --- | --- |
| U00 baseline/repros | recorded | Legacy commit and file hashes are frozen in `benchmark/history/2026-09-15-legacy-baseline.lock.json`; historical public reports remain unchanged. Capture-time tools are not a reconstruction of the historical environment. |
| U01 independent validation | partial | Typed provenance, safe YAML, full inventory locks, deterministic re-rendering and install-time checks reject modified bundles. External source authentication/signatures and reference-client conformance are pending. |
| U02 Python bindings | partial | argparse options require a parsed owner; Click options require a recognized command. Aliases, shadowing, same-line parser identities, local framework impersonation, invalid group methods and registrations after parsing are tested. Typer registration, dynamic bindings and complete framework semantics remain incomplete. |
| U03 Go names / roles | partial | Four known v2/v4 name regressions checked against pinned source; pnpm hidden fixtures, bat syntax-test Go module and goreleaser nested test module no longer produce product Skills. Binary/role inference still uses heuristics, not a complete Go command graph. |
| U04 goal matching | partial | Unrelated goals produce NEEDS_INPUT/REVIEW_REQUIRED; user goal text is not emitted as a capability fact. Explicit multilingual ambiguity handling and workflow matching are pending. |
| U05 source identity | partial | Raw byte hashes and committed Git blob IDs separated; CRLF, BOM, dirty trees and SHA-256 Git cases tested. Git filters/fsmonitor disabled. Byte-range mappings and complete snapshot attestations remain open. |
| U06 IR v2 / migration | partial | Discovery IR 1.4 adds typed explicit option keyword declarations to scoped `CommandSpec`. 1.2/1.3 imports preserve prior facts with no guessed semantics and remain review-blocked; all 45 retained v12 IR files migrate without source changes. Full argument/runtime semantics, byte ranges and general migration remain pending. See [contract and import evidence](discovery-contract.md). |
| U07 workspace scanning | partial | Deterministic workspace/role content budgets, independent metadata limits, tracked-directory inclusion and scanner-gated analyzer reads implemented. Partial scans carry indexed scan.json plus bundle scope, and remain review-required through standalone validation/install. TypeScript/webpack now return partial discoveries. Resolver consolidation, complete workspace graphs, process quotas and hostile-filesystem race isolation remain pending. See [scope contract](scan-budgets.md). |
| U08 Python command graph | partial | Bounded local import/re-export/alias resolution, direct delegation and argparse helper parameter binding preserve source hops. Parsed argparse subcommands, groups and nested children retain their own option paths; fixed pre-commit exposes 16 child paths and 108 scoped options. Black/blackd adds 43 options and Cookiecutter 21 on fixed pins. Dynamic registration, aliases, parser inheritance, local import semantics and complete framework coverage remain pending. See [implemented boundary](python-entrypoint-graph.md). |
| U09 JS/TS command graph | pending | Manifest bin extraction and role exclusions only; AST/framework/delegation support pending. |
| U10 Go AST/Cobra graph | pending | Lexical extraction remains; AST helper, build conditions, command inheritance and ownership pending. |
| U11 workflows/documents | partial | Deterministic typed SkillDocument now renders explicit parameter keywords by command path. Task-specific goals mentioning a known CLI return NEEDS_INPUT instead of a generic empty-argv plan. Complete task-oriented procedures remain unimplemented. |
| U12 application jobs/policy | partial | Execution policy and bounded local writes exist. CLI/UI still need unified application services, persisted jobs, idempotency, cancellation and approvals. |
| U13 sandbox/replay | partial | Local installed-image pinning, filtered readonly source, no network, non-root process, quotas, output bounds and cleanup tested in real Docker. Dependency build profiles, distributed replay and task oracles pending. |
| U14 gold/tasks/evaluator | partial | 40 selected source facts and 30 static prerequisite records remain separate from 30 new reference tasks with file/output oracles on Black, pre-commit and Cookiecutter. First attempt 29/30; corrected oracle casing 30/30 on full rerun. Three metadata-only holdouts registered. Broader TaskSpecs, 200-fact gold, human review and Agent trials remain pending. |
| U15 Agent A/B / official gh | pending | Version-specific static official comparison is recorded. No Agent A/B execution, task uplift, confidence interval or two-version maintenance result. |
| U16 UI/API | partial | Browser-tested inspect → build → evidence/error flow; Host/Origin/token/source-root boundaries. Background jobs, cancellation, capability selection and artifact downloads pending. |
| U17 install/clients | partial | Codex managed destination, staged update, receipt, rollback API, user-modification rejection and receipt-write failure recovery. The bundled plugin-creator validator passes after manifest fixes; native-client loading, full crash recovery, Windows lock behavior and multi-client install lifecycle pending. |
| U18 packaging/community | partial | Current wheel and dependencies install independently into a fresh environment and pass seven CLI checks in isolated Python mode; package bytes match the wheel. Contribution/security/changelog documentation added. License decision, locked release dependencies, signed publishing and complete platform qualification pending. |
| U19 Beta acceptance | pending | Missing recall, semantic review, workflow, client and user-study gates prevent acceptance. |
| U20 CLI 1.0 | pending | Version compatibility, real upstream drift and stability qualification remain. |
| U21 new domains | pending | Rust remains challenge coverage; no complete Rust/library/HTTP support claim. |
| U22 private/hosted | pending | No multi-tenant deployment, private-model transfer authorization or hosted SLO claim. |

## Measured results

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

## Local verification

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

Next acceptance work: complete Python parameter semantics, JS/TS and Go framework graphs,
external source authentication and full IR v2, then the shared job service and executable TaskSpecs.
Human sign-off, model experiments and production hosting
remain separate gates; their absence does not stop independent engineering.
