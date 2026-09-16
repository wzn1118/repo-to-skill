from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    run = ROOT / "benchmark/runs/2026-09-16-upgrade-v13"
    tasks = ROOT / "benchmark/task-runs/2026-09-16-cli-value-v1"
    data = json.loads((run / "results.json").read_text())
    selected = [next(item for item in data["repositories"] if item["id"] == identifier) for identifier in ("black", "pre-commit", "cookiecutter")]
    options = [[fact for fact in item["facts"] if fact["emitted"] and fact["predicate"] == "supports_option"] for item in selected]
    totals = [len(items) for items in options]
    annotated = [sum("semantics" in fact["value"] for fact in items) for items in options]
    attempts = [json.loads((tasks / f"attempt-{number}.json").read_text()) for number in (1, 2)]
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11, "svg.fonttype": "none"})
    figure, axes = plt.subplots(1, 2, figsize=(12, 4.8))
    figure.patch.set_facecolor("#f5f7fa")
    for axis in axes:
        axis.set_facecolor("#f5f7fa")
        axis.spines[["top", "right", "left"]].set_visible(False)
        axis.tick_params(length=0, pad=8)
    axes[0].barh([2, 1, 0], totals, color="#dce3e9", height=0.5)
    bars = axes[0].barh([2, 1, 0], annotated, color="#3279ad", height=0.5)
    axes[0].bar_label(bars, labels=[f"{value}/{total}" for value, total in zip(annotated, totals, strict=True)], padding=5)
    axes[0].set_yticks([2, 1, 0], ["Black / blackd", "pre-commit", "Cookiecutter"])
    axes[0].set_title("Options with explicit parameter declarations", loc="left", fontsize=12, fontweight="bold", pad=15)
    axes[0].set_xlabel("Some explicit fields known / emitted option names")
    axes[0].set_xlim(0, 120)
    axes[1].barh([1, 0], [30, 30], color="#dce3e9", height=0.5)
    bars = axes[1].barh([1, 0], [item["tasks_passed"] for item in attempts], color=["#da8d32", "#3279ad"], height=0.5)
    axes[1].bar_label(bars, labels=[f"{item['tasks_passed']}/30" for item in attempts], padding=5)
    axes[1].set_yticks([1, 0], ["First attempt", "Corrected oracle"])
    axes[1].set_xlim(0, 35)
    axes[1].set_title("Reference solutions in offline containers", loc="left", fontsize=12, fontweight="bold", pad=15)
    axes[1].set_xlabel("Independent file/output checks; Agent trials = 0")
    figure.suptitle("Repo-to-Skill · parameter evidence and executable tasks", x=0.04, ha="left", fontsize=18, fontweight="bold")
    figure.text(0.04, 0.88, "Pinned source · no target execution during discovery · failed first attempt retained", color="#526474")
    figure.text(0.04, 0.035, "Not Skill task success or Agent uplift. Missing parameter fields remain unknown. One oracle casing error corrected.", fontsize=10, color="#526474")
    figure.subplots_adjust(left=0.14, right=0.96, bottom=0.22, top=0.74, wspace=0.55)
    for suffix in ("png", "svg"):
        path = ROOT / f"docs/assets/product-value.{suffix}"
        figure.savefig(path, dpi=180, facecolor=figure.get_facecolor())
        if suffix == "svg":
            path.write_text("\n".join(line.rstrip() for line in path.read_text().splitlines()) + "\n")
    plt.close(figure)


if __name__ == "__main__":
    main()
