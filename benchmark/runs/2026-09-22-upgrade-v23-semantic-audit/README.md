# Rejected source-token experiment — not a semantic result

`independent-audit.json` is retained as a diagnostic, **excluded from semantic metrics**.
It inspected the existing v22 emitted facts, not a new compiler run. Its 549 declaration/token
matches do not prove command ownership, parameter types or effective behavior; its missing-token
count can reflect transformations such as camelCase-to-kebab-case. It also trusted extractor
labels and used an unjustified global `v2`/`v4` name rule. A package could legitimately use either
name. Consequently its zero confirmed-error count is not usable evidence of correctness.

The uncommitted heuristic is removed rather than promoted into the product. All 1,130 facts
remain pending complete semantic review. The replacement is an independently curated,
commit-bound selected-field gold set: matches, omissions, contradictions and negatives are
reported separately, with unsupported and unreviewed fields never counted correct.

This diagnostic is neither an accepted v23 compiler result nor human review. Earlier immutable
v22 source, task, and hash-verification measurements remain unchanged.

## Accepted selected-field evaluation

The replacement gold set is frozen in [`semantic-gold.json`](semantic-gold.json). It covers 10
high-Star repositories, 200 positive operational subjects, and 20 separate negative probes.
Against the immutable v22 compiler result, 69/200 positive subjects reached complete selected-field
agreement, 118 were missing, 10 disagreed on a selected field, and 3 remained partial or unknown.
All 20 negative probes were clear. These are retrospective static semantic results, not Agent task
success or full generated-fact precision.

The accepted report is [`report-v2.md`](report-v2.md), with the companion
[`semantic-coverage-v2.svg`](semantic-coverage-v2.svg). The write-once artifact identity is in
[`semantic-manifest.json`](semantic-manifest.json). The first alias-sensitive evaluation is retained
as `semantic-evaluation.json` and excluded because the evaluator initially treated short and long
spellings of one option as ambiguous; `semantic-evaluation-v2.json` is the corrected result.
