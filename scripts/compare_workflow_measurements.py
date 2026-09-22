from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from measurement_identity import write_new

from r2s.serialization import file_sha256


def index_measurement(report: dict) -> dict[str, dict]:
    records = {item["id"]: item for item in report["records"]}
    if len(records) != len(report["records"]) or len(records) != report["selected"]:
        raise ValueError("MEASUREMENT_DENOMINATOR_MISMATCH")
    if report["passed"] != sum(item["status"] == "PASS" for item in records.values()):
        raise ValueError("MEASUREMENT_NUMERATOR_MISMATCH")
    return records


def compare(baseline: dict, default: dict, expanded: dict) -> dict:
    cohorts = [index_measurement(report) for report in (baseline, default, expanded)]
    if not cohorts[0] or any(set(cohort) != set(cohorts[0]) for cohort in cohorts):
        raise ValueError("MEASUREMENT_TASK_SET_CHANGED")
    for identifier, original in cohorts[0].items():
        for cohort in cohorts[1:]:
            if any(cohort[identifier][key] != original[key] for key in ("repository", "commit_sha", "reference_sha256")):
                raise ValueError("MEASUREMENT_TASK_OR_SOURCE_CHANGED")
    if default["compiler_sha256"] != expanded["compiler_sha256"]:
        raise ValueError("MEASUREMENT_PAIRED_COMPILER_CHANGED")
    if default["runner_sha256"] != expanded["runner_sha256"]:
        raise ValueError("MEASUREMENT_PAIRED_RUNNER_CHANGED")
    rows = []
    for repository in dict.fromkeys(item["repository"] for item in baseline["records"]):
        selected = [[item for item in cohort.values() if item["repository"] == repository] for cohort in cohorts]
        rows.append({"repository": repository, "selected": len(selected[0]),
                     "baseline_passed": sum(item["status"] == "PASS" for item in selected[0]),
                     "default_passed": sum(item["status"] == "PASS" for item in selected[1]),
                     "expanded_passed": sum(item["status"] == "PASS" for item in selected[2]),
                     "expanded_failures": dict(Counter(item.get("reason", item.get("task_result", {}).get("status", "runtime failure")).split(":")[0] for item in selected[2] if item["status"] != "PASS"))})
    return {"format": "r2s-workflow-comparison-v1", "selected": len(cohorts[0]), "rows": rows,
            "baseline_passed": baseline["passed"], "default_passed": default["passed"], "expanded_passed": expanded["passed"],
            "identical_task_inputs_and_source_pins": True, "identical_current_compiler_and_runner": True,
            "scope": "Authored structured inputs and fixed independent oracles; no Agent trial or model uplift measurement. The baseline is historical; the current pair differs in scan budget."}


def render_chart(comparison: dict, destination: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib import pyplot as plot

    with plot.rc_context({"font.family": "DejaVu Sans", "svg.fonttype": "none"}):
        figure, axis = plot.subplots(figsize=(10, 5.5), layout="constrained")
        rows = comparison["rows"]
        positions = list(range(len(rows)))
        for offset, key, label, color in (
            (-0.25, "baseline_passed", "Previous run · standard budget", "#94a3b8"),
            (0, "default_passed", "Current · standard budget", "#3b82f6"),
            (0.25, "expanded_passed", "Current · expanded budget", "#16a34a"),
        ):
            bars = axis.barh([position + offset for position in positions], [row[key] / row["selected"] * 100 for row in rows], height=0.22, color=color, label=label)
            axis.bar_label(bars, labels=[f"{row[key]}/{row['selected']}" for row in rows], padding=4, fontsize=9)
        axis.set_yticks(positions, [row["repository"] for row in rows])
        axis.invert_yaxis()
        axis.set_xlim(0, 115)
        axis.set_xticks([0, 25, 50, 75, 100], ["0%", "25%", "50%", "75%", "100%"])
        axis.set_xlabel("Tasks passing independent output checks; all selected failures retained")
        axis.set_title(f"Generated invocations on the same {comparison['selected']} tasks", loc="left", weight="bold", pad=16)
        axis.spines[["top", "right", "left"]].set_visible(False)
        axis.set_axisbelow(True)
        axis.grid(axis="x", alpha=0.15)
        axis.legend(loc="lower center", bbox_to_anchor=(0.5, -0.36), frameon=False, ncol=1)
        figure.suptitle("Structured inputs, fixed source commits and oracles. Not Agent trials.", fontsize=10, y=1.04)
        figure.savefig(destination / "tasks.svg", bbox_inches="tight")
        figure.savefig(destination / "tasks.png", dpi=180, bbox_inches="tight")
        plot.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--default", required=True, type=Path)
    parser.add_argument("--expanded", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    outputs = ("comparison.json", "tasks.svg", "tasks.png")
    if any((args.output / filename).exists() for filename in outputs):
        raise ValueError("COMPARISON_OUTPUT_EXISTS")
    paths = (args.baseline, args.default, args.expanded)
    reports = [json.loads(path.read_text()) for path in paths]
    result = compare(*reports)
    result["inputs_sha256"] = {label: file_sha256(path) for label, path in zip(("baseline", "default", "expanded"), paths, strict=True)}
    result["renderer_sha256"] = file_sha256(Path(__file__))
    args.output.mkdir(parents=True, exist_ok=True)
    render_chart(result, args.output)
    write_new(args.output / "comparison.json", result)
    print(json.dumps({key: result[key] for key in ("selected", "baseline_passed", "default_passed", "expanded_passed")}))


if __name__ == "__main__":
    main()
