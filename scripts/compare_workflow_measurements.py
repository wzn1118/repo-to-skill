from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from measurement_identity import write_new

from r2s.serialization import canonical_sha256, file_sha256


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


def compare_versions(previous: dict, current: dict) -> dict:
    before, after = index_measurement(previous), index_measurement(current)
    if not before or set(before) != set(after):
        raise ValueError("MEASUREMENT_TASK_SET_CHANGED")
    for key in ("source_taskset_sha256", "cross_language_taskset_sha256", "runner_sha256"):
        if not previous.get(key) or previous[key] != current.get(key):
            raise ValueError("MEASUREMENT_VERSION_INPUT_CHANGED")
    paired_execution = []
    environments = []
    for cohort in (before, after):
        by_repository: dict[str, set[str]] = {}
        for record in cohort.values():
            executed = record.get("task_result")
            if executed is None:
                if record["status"] == "PASS":
                    raise ValueError("MEASUREMENT_EXECUTION_MISSING")
                continue
            if record["status"] != executed["status"]:
                raise ValueError("MEASUREMENT_EXECUTION_STATUS_MISMATCH")
            context = {key: executed[key] for key in ("execution_policy", "image_id", "source_files_sha256", "wheel_sha256", "runtime_files_sha256", "worker_sha256")}
            context["runtime"] = executed["task"]["runtime"]
            by_repository.setdefault(record["repository"], set()).add(canonical_sha256(context))
        environments.append(by_repository)
    if environments[0] != environments[1]:
        raise ValueError("MEASUREMENT_RUNTIME_ENVIRONMENT_CHANGED")
    for identifier, original in before.items():
        updated = after[identifier]
        for key in ("repository", "commit_sha", "reference_sha256", "scan_profile", "scan_limits"):
            if original[key] != updated[key]:
                raise ValueError("MEASUREMENT_VERSION_CONDITIONS_CHANGED")
        if original.get("task_result") is not None and updated.get("task_result") is not None:
            for key in ("files", "expected_exit_codes", "oracle", "python_dependencies", "runtime", "timeout_seconds", "output_limit"):
                if original["task_result"]["task"][key] != updated["task_result"]["task"][key]:
                    raise ValueError("MEASUREMENT_BOUND_TASK_CHANGED")
            paired_execution.append(identifier)
    return {
        "format": "r2s-workflow-version-comparison-v1", "selected": len(before),
        "previous_passed": previous["passed"], "current_passed": current["passed"],
        "previous_compiler_sha256": previous["compiler_sha256"], "current_compiler_sha256": current["compiler_sha256"],
        "newly_passing": [key for key in before if before[key]["status"] != "PASS" and after[key]["status"] == "PASS"],
        "regressions": [key for key in before if before[key]["status"] == "PASS" and after[key]["status"] != "PASS"],
        "still_failing": [key for key in before if before[key]["status"] != "PASS" and after[key]["status"] != "PASS"],
        "paired_execution_ids": paired_execution,
        "runtime_contexts_by_repository": {key: sorted(value) for key, value in environments[0].items()},
        "scope": "Same task/source hashes, scan limits and runner. Executed tasks additionally retain identical runtime contexts by repository; paired executed tasks have identical bound inputs/oracles. Previously blocked tasks had no runtime result. No timing ranking, Agent trial or uplift claim.",
    }


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
    parser.add_argument("--previous-expanded", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    outputs = ("comparison.json", "tasks.svg", "tasks.png", "version-comparison.json")
    if any((args.output / filename).exists() for filename in outputs):
        raise ValueError("COMPARISON_OUTPUT_EXISTS")
    paths = (args.baseline, args.default, args.expanded)
    reports = [json.loads(path.read_text()) for path in paths]
    result = compare(*reports)
    result["inputs_sha256"] = {label: file_sha256(path) for label, path in zip(("baseline", "default", "expanded"), paths, strict=True)}
    result["renderer_sha256"] = file_sha256(Path(__file__))
    transition = None
    if args.previous_expanded:
        transition = compare_versions(json.loads(args.previous_expanded.read_text()), reports[2])
        transition["inputs_sha256"] = {"previous": file_sha256(args.previous_expanded), "current": file_sha256(args.expanded)}
        transition["comparison_script_sha256"] = file_sha256(Path(__file__))
    args.output.mkdir(parents=True, exist_ok=True)
    render_chart(result, args.output)
    write_new(args.output / "comparison.json", result)
    if transition is not None:
        write_new(args.output / "version-comparison.json", transition)
    print(json.dumps({key: result[key] for key in ("selected", "baseline_passed", "default_passed", "expanded_passed")}))


if __name__ == "__main__":
    main()
