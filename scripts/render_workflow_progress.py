from __future__ import annotations

import argparse
import json
from pathlib import Path

from compare_runtime_addition import compare_addition
from compare_workflow_measurements import compare_versions
from measurement_identity import write_new

from r2s.serialization import file_sha256


def summarize(previous: dict, original: dict, repaired: dict, receipt: dict, repository: str) -> dict:
    source_change = compare_versions(previous, original)
    runtime_change = compare_addition(original, repaired, receipt, repository)
    return {
        "format": "r2s-workflow-progress-v1",
        "selected": source_change["selected"],
        "previous_passed": previous["passed"],
        "source_change_passed": original["passed"],
        "runtime_repair_passed": repaired["passed"],
        "source_change": source_change,
        "runtime_change": runtime_change,
        "scope": "Two separately checked transitions: compiler change in an unchanged recorded environment, then explicit runtime dependency additions with an unchanged compiler. Authored structured inputs, not Agent trials or a general accuracy score.",
    }


def render(summary: dict, destination: Path, labels: list[str]) -> None:
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib import pyplot as plot

    total = summary["selected"]
    counts = [summary[key] for key in ("previous_passed", "source_change_passed", "runtime_repair_passed")]
    with plot.rc_context({"font.family": "DejaVu Sans", "svg.fonttype": "none"}):
        figure, axis = plot.subplots(figsize=(11, 4.8), layout="constrained")
        positions = list(range(len(counts)))
        axis.barh(positions, [total] * len(counts), color="#e2e8f0", height=0.5)
        bars = axis.barh(positions, counts, color=["#64748b", "#2563eb", "#047857"], height=0.5)
        axis.bar_label(bars, labels=[f"{count}/{total}" for count in counts], padding=8, weight="bold")
        axis.set_yticks(positions, labels, fontsize=10)
        axis.invert_yaxis()
        axis.set_xlim(0, total * 1.16)
        axis.set_xticks(sorted({0, total // 4, total // 2, total * 3 // 4, total}))
        axis.spines[["top", "right", "left"]].set_visible(False)
        axis.set_axisbelow(True)
        axis.grid(axis="x", alpha=0.15)
        axis.set_xlabel("Passed independent output checks; grey remainder = selected failures", labelpad=10)
        axis.set_title("Generated invocations: source improvement ≠ runtime repair", loc="left", weight="bold", pad=25)
        figure.suptitle("Fixed source pins, structured inputs and task oracles. Expanded scans; not Agent trials.", fontsize=10, y=1.07)
        figure.text(0.5, -0.03, "First transition: unchanged recorded environment. Second: unchanged compiler, added native dependencies.", ha="center", fontsize=9)
        figure.savefig(destination / "progress.svg", bbox_inches="tight")
        figure.savefig(destination / "progress.png", dpi=180, bbox_inches="tight")
        plot.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser()
    for name in ("previous", "original", "repaired", "addition", "output"):
        parser.add_argument(f"--{name}", required=True, type=Path)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--labels", required=True, nargs=3)
    args = parser.parse_args()
    if any((args.output / name).exists() for name in ("progress.json", "progress.svg", "progress.png")):
        raise ValueError("PROGRESS_OUTPUT_EXISTS")
    inputs = ("previous", "original", "repaired", "addition")
    reports = [json.loads(getattr(args, name).read_text(encoding="utf-8")) for name in inputs]
    summary = summarize(*reports, args.repository)
    summary["inputs_sha256"] = {name: file_sha256(getattr(args, name)) for name in inputs}
    summary["renderer_sha256"] = file_sha256(Path(__file__))
    summary["labels"] = args.labels
    args.output.mkdir(parents=True, exist_ok=True)
    render(summary, args.output, args.labels)
    write_new(args.output / "progress.json", summary)
    print(json.dumps({key: summary[key] for key in ("selected", "previous_passed", "source_change_passed", "runtime_repair_passed")}))


if __name__ == "__main__":
    main()
