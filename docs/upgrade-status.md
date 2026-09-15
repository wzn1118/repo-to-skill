# Upgrade status / 升级进度

Updated: 2026-09-15. **Active goal; M0 is not fully accepted and the full upgrade is not complete.**

The [U00–U22 plan](upgrade-plan.md) remains the acceptance contract. “Partial” means there is
reviewable implementation, not that the work package or release gate is passed.

| Package | Status | Evidence and remaining work |
| --- | --- | --- |
| U00 baseline/repros | recorded | Legacy commit and file hashes are frozen in `benchmark/history/2026-09-15-legacy-baseline.lock.json`; historical public reports remain unchanged. Capture-time tools are not a reconstruction of the historical environment. |
| U01 independent validation | partial | Typed provenance, safe YAML, full inventory locks, deterministic re-rendering and install-time checks reject modified bundles. External source authentication/signatures and reference-client conformance are pending. |
| U02 Python bindings | partial | argparse parser ownership and Click/Typer import/alias bindings; unrelated method calls and scope shadowing regressions. Cross-file calls, subparsers and dynamic registration remain incomplete. |
| U03 Go names / roles | partial | Four known v2/v4 name regressions checked against pinned source; pnpm hidden fixtures, bat syntax-test Go module and goreleaser nested test module no longer produce product Skills. Binary/role inference still uses heuristics, not a complete Go command graph. |
| U04 goal matching | partial | Unrelated goals produce NEEDS_INPUT/REVIEW_REQUIRED; user goal text is not emitted as a capability fact. Explicit multilingual ambiguity handling and workflow matching are pending. |
| U05 source identity | partial | Raw byte hashes and committed Git blob IDs separated; CRLF, BOM, dirty trees and SHA-256 Git cases tested. Git filters/fsmonitor disabled. Byte-range mappings and complete snapshot attestations remain open. |
| U06 IR v2 / migration | partial | Strict nested Discovery IR and claim-value contracts, shared schema export, graph/source consistency checks, explicit 1.2 import, actual compiler/dependency/profile cache keys and scoped generation locks implemented. Identical shared evidence is deduplicated; historical input is preserved. This retains the 1.2 wire shape: full command graph, typed extractor payloads, byte ranges and general schema migration remain pending. See [contract and import evidence](discovery-contract.md). |
| U07 workspace scanning | partial | Existing bounded scanner and snapshot checks retained; FIFOs rejected. TypeScript/webpack still exceed file limits. Workspace budgets and product/benchmark resolver consolidation are pending. |
| U08 Python command graph | pending | Current limited bindings do not provide the planned cross-file graph. |
| U09 JS/TS command graph | pending | Manifest bin extraction and role exclusions only; AST/framework/delegation support pending. |
| U10 Go AST/Cobra graph | pending | Lexical extraction remains; AST helper, build conditions, command inheritance and ownership pending. |
| U11 workflows/documents | partial | Deterministic typed SkillDocument with claim-bound content; task-oriented procedures for the five target projects are not implemented. |
| U12 application jobs/policy | partial | Execution policy and bounded local writes exist. CLI/UI still need unified application services, persisted jobs, idempotency, cancellation and approvals. |
| U13 sandbox/replay | partial | Local installed-image pinning, filtered readonly source, no network, non-root process, quotas, output bounds and cleanup tested in real Docker. Dependency build profiles, distributed replay and task oracles pending. |
| U14 gold/tasks/evaluator | partial | 40 selected source facts and 30 static prerequisite records; command/subcommand ownership checked in evaluator. The 200-fact target, executable TaskSpecs, negative oracles and human review remain pending. |
| U15 Agent A/B / official gh | pending | Version-specific static official comparison is recorded. No Agent A/B execution, task uplift, confidence interval or two-version maintenance result. |
| U16 UI/API | partial | Browser-tested inspect → build → evidence/error flow; Host/Origin/token/source-root boundaries. Background jobs, cancellation, capability selection and artifact downloads pending. |
| U17 install/clients | partial | Codex managed destination, staged update, receipt, rollback API, user-modification rejection and receipt-write failure recovery. The bundled plugin-creator validator passes after manifest fixes; native-client loading, full crash recovery, Windows lock behavior and multi-client install lifecycle pending. |
| U18 packaging/community | partial | Current wheel imports from its installed package and passes seven CLI checks, using previously verified development dependencies. Independent clean dependency resolution stalled; no current clean-install claim. Contribution/security/changelog documentation added. License decision, locked release dependencies, signed publishing and complete platform qualification pending. |
| U19 Beta acceptance | pending | Missing recall, semantic review, workflow, client and user-study gates prevent acceptance. |
| U20 CLI 1.0 | pending | Version compatibility, real upstream drift and stability qualification remain. |
| U21 new domains | pending | Rust remains challenge coverage; no complete Rust/library/HTTP support claim. |
| U22 private/hosted | pending | No multi-tenant deployment, private-model transfer authorization or hosted SLO claim. |

## Measured results

The [upgrade-v6 run](../benchmark/runs/2026-09-15-upgrade-v6/report.md) runs the same 45 pinned
repositories: 36 high-star Core, 6 Rust challenges and 3 secondary cases.

- Core: **26 STATIC_READY, 3 REVIEW_REQUIRED, 7 UNSUITABLE**; 34 completed, with TypeScript/webpack
  scanner-limit failures retained.
- Core cumulative stars: **1,453,404**; static star-weighted coverage **69.74%**.
- **49 emitted facts / 49 hash-and-pin checks**. All 49 still await complete semantic review.
- Four known Go binary-name regressions match pinned source. This is a targeted regression check,
  not zero hallucination or full semantic precision.
- **9/40 selected source facts; 1/30 static task prerequisites**. Recall is unchanged from legacy.
- Compiler fingerprint: `2e06c783eeb7e6dd9c6da79cd9360e19e7c054735d04eaa17caff87c3293c14e`.
  The runner checks compiler/harness/dependency identity before and after workers and rejects
  overwrites. Historical metadata is not refreshed when reports are rendered.
- `upgrade-v3` is a retained preliminary run with known helper-entrypoint errors and only an
  end-of-run fingerprint. It does not represent the current compiler.

## Local verification

**181 passed, 12 subtests passed**, including five real Docker checks and one real Chromium test
covering six UI interactions. Ruff and mypy pass. See the
[verification record](../benchmark/runs/2026-09-15-upgrade-v6/verification.json) for exact versions,
hashes and scope. These controlled tests are separate from public-repository task evaluation.

The installed wheel passes version, inspect, Codex build, validate, install preview, schema export
and migration checks. Dependency downloads stalled; this check reuses the verified development
dependencies and does not establish independent clean dependency resolution.

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

`BUNDLE.lock.json` establishes self-consistency; it does not independently authenticate upstream
source. Reports retain `not_independently_authenticated`. Local Docker is a trusted-daemon boundary,
not a hosted multi-tenant sandbox. A successful process exit is not an independent task oracle.

The 30 records in `benchmark/taskset-v1.json` are explicitly a **static prerequisite catalog**,
with no execution oracle; they are not completed TaskSpecs. Historical runtime and official-Skill
results are not reused as current runtime or Agent A/B scores.

Next acceptance work: corroborated Go command identity, external source authentication and full IR v2,
workspace budgets for the two large failing repositories, then the shared job service
and real framework command graphs. Human sign-off, model experiments and production hosting
remain separate gates; their absence does not stop independent engineering.
