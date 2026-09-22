from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

from semantic_gold import digest, strict_load


def write_new(path: Path, content: str) -> None:
    if path.exists() or path.is_symlink():
        raise ValueError(f"SEMANTIC_REPORT_OUTPUT_EXISTS: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(content)


def render_chart(evaluation: dict) -> str:
    width = 980
    row_height = 30
    left = 150
    plot_width = 620
    top = 42
    height = top + row_height * len(evaluation["repositories"]) + 35
    scale = plot_width / 20
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-label="Semantic gold outcomes by repository">',
        '<style>text{font:13px sans-serif;fill:#24292f}.label{font-weight:600}.axis{fill:#57606a;font-size:12px}</style>',
        '<text x="16" y="22" class="label">Positive subjects: green selected-field match, red unresolved or disagreement</text>',
    ]
    for index, repo in enumerate(evaluation["repositories"]):
        y = top + index * row_height
        counts = repo["counts"]
        match = counts.get("SELECTED_FIELDS_MATCH", 0)
        other = sum(counts.get(status, 0) for status in ("MISSING_FACT", "FIELD_MISMATCH", "PARTIAL_OR_UNKNOWN", "AMBIGUOUS_FACT", "MEASUREMENT_INCOMPLETE"))
        parts.append(f'<text x="{left - 12}" y="{y + 17}" text-anchor="end" class="label">{html.escape(repo["id"])}</text>')
        parts.append(f'<rect x="{left}" y="{y}" width="{match * scale}" height="18" fill="#1a7f37"/>')
        parts.append(f'<rect x="{left + match * scale}" y="{y}" width="{other * scale}" height="18" fill="#cf222e"/>')
        parts.append(f'<text x="{left + plot_width + 12}" y="{y + 14}">{match}/{match + other}</text>')
    axis_y = height - 10
    for value in (0, 5, 10, 15, 20):
        x = left + value * scale
        parts.append(f'<line x1="{x}" y1="{top - 5}" x2="{x}" y2="{axis_y - 12}" stroke="#d0d7de"/>')
        parts.append(f'<text x="{x}" y="{axis_y}" text-anchor="middle" class="axis">{value}</text>')
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def render_report(evaluation: dict, gold: dict, metadata: dict, chart_name: str) -> str:
    rows = []
    selected = 0
    positive = evaluation["positive_subjects"]
    for repo in evaluation["repositories"]:
        counts = repo["counts"]
        match = counts.get("SELECTED_FIELDS_MATCH", 0)
        selected += match
        rows.append(f"| `{repo['id']}` | {match} | {counts.get('MISSING_FACT', 0)} | {counts.get('FIELD_MISMATCH', 0)} | {counts.get('PARTIAL_OR_UNKNOWN', 0) + counts.get('AMBIGUOUS_FACT', 0)} | {counts.get('NEGATIVE_CLEAR', 0)} |")
    stars = {item["id"]: item["stars_at_benchmark"] for item in metadata["repositories"] if item["id"] in {repo["id"] for repo in evaluation["repositories"]}}
    total_stars = sum(stars.values())
    field_counts = evaluation["field_counts"]
    return f"""# v23 Semantic Gold Audit

This is a retrospective, agent-curated selected-field comparison against the immutable v22 compiler result. It is not human sign-off, held-out accuracy, complete generated-fact precision, or Agent task uplift.

## Scope

- High-Star repositories: {len(evaluation['repositories'])}
- Cumulative GitHub stars at the frozen benchmark snapshot: {total_stars:,}
- Positive operational subjects: {positive}
- Separate negative probes: {evaluation['negative_subjects']}
- Gold input: `{evaluation['gold_input_sha256']}`
- Compiler result input: `{evaluation['results_input_sha256']}`

The gold set is independently authored from pinned source declarations and line anchors. It was frozen after the v22 run; no core analyzer change was made to improve this score. It deliberately selects options and positional arguments that matter to task-oriented Skills. Aliases and choices are checked only where explicitly selected; they are not exhaustive inventories.

## Results

`SELECTED_FIELDS_MATCH` means every selected field for that subject matched. `MISSING_FACT`, `FIELD_MISMATCH`, partial, and ambiguous outcomes remain failures or unknowns. `NEGATIVE_CLEAR` only means the selected false option was not emitted; it is not a zero-hallucination claim.

| Repository | Selected match | Missing | Field mismatch | Partial / ambiguous | Negative clear |
| --- | ---: | ---: | ---: | ---: | ---: |
{chr(10).join(rows)}

![Selected-field outcomes](./{chart_name})

Across positive subjects, {selected}/{positive} ({selected / positive:.1%}) reached selected-field agreement. The field-level diagnostic is {field_counts.get('MATCH', 0)} matches, {field_counts.get('MISMATCH', 0)} mismatches, and {field_counts.get('NOT_EVALUATED', 0)} fields without a selected fact. The field ratio must not be read as overall semantic precision because missing facts are not verified fields.

The most visible roadmap signals are the complete pre-commit, yt-dlp, ESLint, Hugo, and Poetry selected cohorts with no matching emitted options; fzf custom argument consumption remains unknown or mismatched; Prettier's color alias is incomplete; and Black's dynamic target-version behavior remains partial. These are preserved as analyzer work, not removed from the denominator.

## Reproduce

```bash
python scripts/freeze_semantic_gold.py \\
  --snapshots /data/repo-to-skill-benchmark-work/snapshots \\
  --output benchmark/runs/2026-09-22-upgrade-v23-semantic-audit/semantic-gold.json
python scripts/semantic_gold.py \\
  --gold benchmark/runs/2026-09-22-upgrade-v23-semantic-audit/semantic-gold.json \\
  --results benchmark/runs/2026-09-22-upgrade-v23-semantic-audit/v22-semantic-results.json \\
  --snapshots /data/repo-to-skill-benchmark-work/snapshots \\
  --output benchmark/runs/2026-09-22-upgrade-v23-semantic-audit/semantic-evaluation-v2.json
```

The rejected first evaluation remains in `semantic-evaluation.json` as a diagnostic: it exposed an alias grouping defect in the evaluator and is excluded from this report. The corrected evaluator has a regression test for short and long option spellings.
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evaluation", type=Path, required=True)
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--chart", type=Path, required=True)
    args = parser.parse_args()
    evaluation = strict_load(args.evaluation)
    gold = strict_load(args.gold)
    metadata = strict_load(args.metadata)
    chart = render_chart(evaluation)
    report = render_report(evaluation, gold, metadata, args.chart.name)
    write_new(args.chart, chart)
    write_new(args.output, report)
    print(json.dumps({"report": str(args.output), "chart": str(args.chart), "evaluation_sha256": digest(args.evaluation.read_bytes())}))


if __name__ == "__main__":
    main()
