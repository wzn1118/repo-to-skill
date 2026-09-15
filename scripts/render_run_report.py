from __future__ import annotations

import argparse
import json
from pathlib import Path


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def render(run: Path) -> str:
    results = load(run / "results.json")
    truth = load(run / "ground-truth-results.json")
    audit = load(run / "fact-audit.json")
    stats = results["summary"]
    lines = [
        "# Repo-to-Skill Benchmark Run",
        "",
        f"**Run:** `{run.name}`",
        "",
        f"**High-Star Public Repositories Tested:** {stats['high_star_public_repositories_tested']}",
        "",
        f"**Core cumulative GitHub stars:** {stats['total_benchmark_stars']:,}",
        "",
        f"**Compiler fingerprint:** `{results['compiler_sha256']}`",
        "",
        "This report is a versioned static compiler run. It does not reuse runtime, model A/B, or official comparison results from another compiler fingerprint.",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Core outcomes | {stats['static_ready']} STATIC_READY / {stats['high_star_selected']} |",
        f"| Core REVIEW_REQUIRED | {stats['sets']['core'].get('REVIEW_REQUIRED', 0)} |",
        f"| Core UNSUITABLE | {stats['sets']['core'].get('UNSUITABLE', 0)} |",
        f"| Star-weighted repository coverage | {stats['star_weighted_repository_coverage']:.2%} |",
        f"| Emitted executable facts | {stats['emitted_executable_facts']} |",
        f"| Hash + commit verified facts | {stats['hash_and_pin_verified_facts']} |",
        f"| Selected source facts covered | {truth['generated_covered_facts']} / {truth['expected_facts']} |",
        f"| Generated facts awaiting full semantic review | {audit['not_semantically_reviewed']} |",
        f"| Four legacy binary-name regressions corrected | {sum(item['name_regression_fixed'] for item in audit.get('binary_name_regressions', []))} / 4 |",
        "",
        "## Outcomes",
        "",
        "| Repository | Tier | Stars | Status | Bundles |",
        "| --- | --- | ---: | --- | ---: |",
    ]
    qualification = run / "qualification.json"
    if qualification.is_file():
        record = load(qualification)
        lines[4:4] = [
            f"**Qualification:** {record['status']}; headline eligible: {record['headline_eligible']}.",
            "", str(record.get("defect", "See qualification.json")), "",
            "Read [qualification.json](qualification.json) before interpreting this preliminary measurement.", "",
        ]
    for item in results["repositories"]:
        lines.append(
            f"| `{item['repository']}` | {item['tier']} | {item['stars_at_benchmark']:,} | "
            f"{item['status']} | {item.get('bundles', 0)} |"
        )
    scans = [item for item in results["repositories"] if item.get("scan")]
    if scans:
        lines.extend([
            "", "## Scan scope", "",
            "Content admission is bounded independently from path enumeration. Partial scans retain unknown regions and require review, including in standalone bundle validation. Admitted text-file counts are not parser success or complete CLI coverage.",
            "",
            "| Repository | Inventory entries | Admitted text files | Budget-excluded files | Complete within policy |",
            "| --- | ---: | ---: | ---: | --- |",
        ])
        for item in scans:
            scan = item["scan"]
            lines.append(
                f"| `{item['repository']}` | {scan['inventory_entries']} | {scan['analyzed_files']} | "
                f"{scan['budget_skipped_files']} | {scan['complete_within_policy']} |"
            )
    failures = [item for item in results["repositories"] if not item.get("completed") or item["status"] == "REVIEW_REQUIRED"]
    if failures:
        lines.extend(["", "## Failures and review reasons", ""])
        for item in failures:
            codes = sorted({finding["code"] for finding in item.get("findings", []) if finding["severity"] == "error"})
            reason = item.get("reason", item.get("failure_class", ", ".join(codes) or "See raw result"))
            reason = str(reason).replace("`", "'").replace("\n", " ")
            lines.append(f"- `{item['repository']}`: {reason}")
    lines.extend([
        "",
        "## Limits",
        "",
        "This run measures static discovery and generation only. `STATIC_READY` is not semantic correctness, runtime readiness, or agent task uplift. The ground truth remains agent-curated with zero human sign-offs; unreviewed facts are not counted as correct.",
        "The targeted name check covers the four known Go module-suffix regressions only. Its error count is not an estimate of hallucination rate. Test/helper entrypoints are filtered by exact repository path components; role inference and Go binary-name inference remain conservative heuristics.",
        "",
        "Raw artifacts: [`results.json`](results.json), [`ground-truth-results.json`](ground-truth-results.json), [`fact-audit.json`](fact-audit.json), [`official-comparison.json`](official-comparison.json).",
    ])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    args = parser.parse_args()
    report = args.run / "report.md"
    report.write_text(render(args.run), encoding="utf-8")
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
