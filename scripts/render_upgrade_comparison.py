from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    baseline = json.loads((ROOT / "benchmark/results.json").read_text())
    current = json.loads((ROOT / "benchmark/runs/2026-09-15-upgrade-v5/results.json").read_text())
    old_truth = json.loads((ROOT / "benchmark/ground-truth-results.json").read_text())
    new_truth = json.loads((ROOT / "benchmark/runs/2026-09-15-upgrade-v5/ground-truth-results.json").read_text())
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11, "svg.fonttype": "none"})
    figure, axes = plt.subplots(1, 2, figsize=(12, 4.7), gridspec_kw={"width_ratios": [1.4, 1]})
    figure.patch.set_facecolor("#f5f7fa")
    for axis in axes:
        axis.set_facecolor("#f5f7fa")
        axis.spines[["top", "right", "left"]].set_visible(False)
        axis.tick_params(axis="both", length=0, pad=8)
    left = [0, 0]
    for status, color in [("STATIC_READY", "#3279ad"), ("REVIEW_REQUIRED", "#da8d32"), ("UNSUITABLE", "#8b97a4")]:
        values = [run["summary"]["sets"]["core"].get(status, 0) for run in (baseline, current)]
        bars = axes[0].barh([1, 0], values, left=left, color=color, height=0.5, label=status)
        axes[0].bar_label(bars, label_type="center", color="white", fontsize=12)
        left = [offset + value for offset, value in zip(left, values, strict=True)]
    axes[0].set_yticks([1, 0], ["Legacy", "Upgrade v5"])
    axes[0].set_xlim(0, 36)
    axes[0].set_xticks([0, 12, 24, 36])
    axes[0].set_xlabel("Core repositories (all 36 retained)")
    axes[0].set_title("Static generation outcomes", loc="left", fontweight="bold", pad=18)
    axes[0].legend(loc="upper left", bbox_to_anchor=(0, -0.23), frameon=False, fontsize=9, ncol=2)
    covered = [truth["generated_covered_facts"] for truth in (old_truth, new_truth)]
    totals = [truth["expected_facts"] for truth in (old_truth, new_truth)]
    axes[1].barh([1, 0], totals, height=0.5, color="#dce3e9")
    bars = axes[1].barh([1, 0], covered, height=0.5, color="#3279ad")
    axes[1].bar_label(bars, labels=[f"{value}/{total}" for value, total in zip(covered, totals, strict=True)], padding=6)
    axes[1].set_yticks([1, 0], ["Legacy", "Upgrade v5"])
    axes[1].set_xticks([0, 10, 20, 30, 40])
    axes[1].set_xlim(0, 40)
    axes[1].set_xlabel("Selected source facts across 10 repos")
    axes[1].set_title("Selected fact recall is unchanged", loc="left", fontweight="bold", pad=18)
    figure.suptitle("Repo-to-Skill · fixed high-star corpus", x=0.06, ha="left", fontsize=19, fontweight="bold")
    figure.text(0.06, 0.88, "36 high-star repos · 1,453,404 cumulative stars · metadata frozen 2026-09-14", color="#526474")
    figure.text(0.06, 0.025, "Static readiness is not correctness or task success. Agent-curated facts; no human sign-off or Agent A/B result.", fontsize=10, color="#526474")
    figure.subplots_adjust(left=0.12, right=0.98, bottom=0.27, top=0.73, wspace=0.38)
    for suffix in ("png", "svg"):
        figure.savefig(ROOT / f"docs/assets/upgrade-comparison.{suffix}", dpi=180, facecolor=figure.get_facecolor())
    plt.close(figure)


if __name__ == "__main__":
    main()
