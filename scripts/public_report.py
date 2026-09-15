from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from public_sources import write_json

ROOT = Path(__file__).resolve().parents[1]


def load(name: str) -> dict:
    return json.loads((ROOT / "benchmark" / name).read_text())


def failure_code(record: dict) -> str:
    if record.get("reason"):
        return record["reason"].split(":", 1)[0]
    if record.get("failure_class"):
        return record["failure_class"]
    errors = sorted({item["code"] for item in record.get("findings", [])
                     if item["severity"] in {"error", "high", "critical"}})
    return ", ".join(errors) or ("NO_ACTIONABLE_CAPABILITY" if record["status"] == "UNSUITABLE" else "—")


def render_chart(results: dict, truth: dict, output: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11, "svg.hashsalt": "repo-to-skill",
                         "svg.fonttype": "none", "axes.spines.top": False,
                         "axes.spines.right": False})
    figure, axes = plt.subplots(1, 2, figsize=(14, 6), gridspec_kw={"width_ratios": [1, 1.2]})
    figure.set_facecolor("#f6f8fc")
    stats = results["summary"]
    figure.suptitle("Repo-to-Skill · Real public repository measurements", fontsize=19,
                    fontweight="bold", x=0.06, ha="left", y=0.98)
    figure.text(0.06, 0.885,
                f"{stats['high_star_public_repositories_tested']} high-star repos attempted · "
                f"{stats['total_benchmark_stars']:,} cumulative stars · pinned commits · Python {results['python']}",
                color="#475569")
    statuses = ["STATIC_READY", "REVIEW_REQUIRED", "UNSUITABLE", "FETCH_ERROR"]
    counts = [stats["sets"]["core"].get(status, 0) for status in statuses]
    axes[0].barh(statuses, counts, color=["#2563eb", "#f59e0b", "#64748b", "#dc2626"])
    axes[0].invert_yaxis()
    axes[0].set_xlim(0, max(counts) + 5)
    for index, value in enumerate(counts):
        axes[0].text(value + .3, index, str(value), va="center", fontweight="bold")
    axes[0].set_title("Core: static generation outcomes", loc="left", pad=16)
    axes[0].set_xlabel("Repositories; STATIC_READY is not task success")
    names = [item["id"] for item in truth["repositories"]]
    totals = [item["expected"] for item in truth["repositories"]]
    covered = [item["covered"] for item in truth["repositories"]]
    axes[1].barh(names, totals, color="#e2e8f0", label="Selected source facts")
    axes[1].barh(names, covered, color="#2563eb", label="Present in generated bundle")
    axes[1].invert_yaxis()
    axes[1].set_xlim(0, max(totals) + 1.4)
    for index, (found, total) in enumerate(zip(covered, totals)):
        axes[1].text(total + .15, index, f"{found}/{total}", va="center")
    axes[1].set_title("Ground truth: selected-fact recall", loc="left", pad=16)
    axes[1].legend(loc="upper center", bbox_to_anchor=(.5, -.09), ncol=1, frameon=False, fontsize=9)
    figure.text(.06, .03,
                "Failures retained. Agent-curated source audit; no human sign-off or with/without-skill performance claim.",
                color="#475569", fontsize=10)
    figure.subplots_adjust(left=.15, right=.96, top=.79, bottom=.17, wspace=.47)
    figure.savefig(output, facecolor=figure.get_facecolor(), metadata={"Date": None})
    output.write_text("\n".join(line.rstrip() for line in output.read_text().splitlines()) + "\n")
    figure.savefig(output.with_suffix(".png"), dpi=180, facecolor=figure.get_facecolor())
    plt.close(figure)


def render(results: dict, truth: dict, runtime: dict, functional: dict, builds: dict, audit: dict) -> str:
    stats = results["summary"]
    sections = ["# Public Repo Benchmark 1.0 — measured results / 实测结果", "",
                f"**High-Star Public Repositories Tested: {stats['high_star_public_repositories_tested']}**", "",
                (f"{stats['high_star_selected']} Core · {stats['total_benchmark_stars']:,} cumulative GitHub stars. "
                "Stars describe the corpus, not unique users."), "",
                "![Measured results](../docs/assets/public-benchmark.svg)", "",
                "## Scope / 口径", "",
                ("Every source is commit-pinned and hashed. All languages go through the unmodified scanner, "
                "analyzers, portable generator and internal validator. No repository code runs during discovery. "
                "Separate containers perform explicitly requested runtime checks."), "",
                ("所有语言都实际经过原有编译器，不按 metadata 预判成功/不支持。STATIC_READY 只代表内部静态校验；"
                "不保证产品入口正确、参数完整或真实任务成功。下载失败、扫描限额和辅助脚本误报均保留。"), "",
                "| Metric | Measured value |", "| --- | ---: |",
                f"| Core attempts / completed pipelines | {stats['high_star_public_repositories_tested']} / {stats['high_star_completed']} |",
                f"| Core STATIC_READY | {stats['static_ready']} / {stats['high_star_selected']} |",
                f"| Star-weighted coverage (static-generation definition) | {stats['star_weighted_repository_coverage']:.1%} |",
                f"| Generated executable facts (Core) | {stats['emitted_executable_facts']} |",
                f"| Fact provenance: file hash + commit verified | {stats['hash_and_pin_verified_facts']} |",
                (f"| Confirmed wrong executable names | {audit['confirmed_wrong_executable_facts']}; "
                 f"remaining {audit['not_semantically_reviewed']} facts not semantically reviewed |"),
                f"| Selected ground-truth facts covered | {truth['generated_covered_facts']} / {truth['expected_facts']} |",
                f"| Source-verified ground-truth facts | {truth['source_verified_facts']} / {truth['expected_facts']} |",
                f"| Tasks with all selected static prerequisites covered | {truth['static_task_prerequisites_covered']} / {truth['tasks_evaluated']} |",
                "| Human-verified repositories | 0 |",
                "| Hallucination rate / with-vs-without-skill task uplift | Not measured |", "",
                ("Coverage denominator is **all selected Core stars**, including failed attempts. "
                "Hash provenance proves traceability; it does not prove semantic correctness. "
                "The selected facts are a small, agent-curated sample, not an exhaustive CLI inventory."), "",
                "## Per-repository outcomes / 逐仓库结果", "",
                "| Repository | Set / tier | Stars | Outcome | Bundles | Failure |",
                "| --- | --- | ---: | --- | ---: | --- |"]
    for item in results["repositories"]:
        sections.append(f"| [{item['repository']}](https://github.com/{item['repository']}/tree/{item['commit_sha']}) "
                        f"| {item['set']} / {item['tier']} | {item['stars_at_benchmark']:,} | {item['status']} "
                        f"| {item.get('bundles', 0)} | {failure_code(item)} |")
    sections += ["", "## Runtime / 隔离运行", "",
                 ("Source read-only; no network during execution; no host keys; non-root; dropped capabilities; "
                 "CPU, memory, process and time limits. Dependency acquisition occurs separately with network; "
                 "npm lifecycle scripts are disabled. Python wheels are hashed. Source import paths are checked."), "",
                 "| Repository | Check type | Result |", "| --- | --- | --- |"]
    for item in runtime["repositories"]:
        if item.get("cases"):
            sections.append(f"| {item['id']} | {'Functional formatting' if item['id'] == 'black' else 'Help/version smoke'} "
                            f"| {sum(case['passed'] for case in item['cases'])}/{len(item['cases'])} |")
    for item in builds["repositories"]:
        sections.append(f"| {item['id']} | Source build/help attempt | {item['status']} |")
    for item in functional["cases"]:
        sections.append(f"| {item['id']} | {item['case']} | {'PASS' if item['passed'] else 'FAIL'} |")
    sections += ["", ("Help/version checks are not user-task success. Functional checks use synthetic inputs "
                 "against real pinned source. No agent/model baseline ran; no time/token benefit is claimed."), "",
                 "## Evidence-driven roadmap / 失败驱动路线图", "",
                 "1. Fix Go module suffixes becoming commands: goreleaser/gum/direnv → v2, yq → v4. See [fact audit](fact-audit.json).",
                 "2. Exclude test fixtures and developer utilities from product CLI capabilities (bat, npm, pnpm).",
                 "3. Extract subcommands and options across files (gh, fzf, Hugo, black, Poetry, yt-dlp).",
                 "4. Handle large repositories without silently skipping them (webpack and TypeScript hit scan limits).",
                 "5. Resolve multi-license filenames; root LICENSE detection misses LICENSE-MIT / LICENSE-APACHE.",
                 "6. Model CLI delegation (webpack → webpack-cli), and pin dependency/toolchain versions for runtime checks.", "",
                 "## Reproduce / 复现", "", "```bash",
                 "python scripts/public_measure.py run --work /path/on/data-disk",
                 "python scripts/public_evaluate.py --work /path/on/data-disk",
                 "python scripts/public_fact_audit.py --work /path/on/data-disk",
                 "python scripts/public_runtime.py --work /path/on/data-disk --image <python-image> --execute",
                 "python scripts/public_build_runtime.py --work /path/on/data-disk --go-image <go-image> --execute",
                 "python scripts/functional_runtime.py --work /path/on/data-disk --execute",
                 "python scripts/public_report.py", "```", "",
                 ("Runtime reproduction requires the recorded wheel set and container images; their hashes/IDs "
                 "are in the runtime reports. No generated Skill is installed or executed automatically."), "",
                 ("Raw data: [results](results.json), [fact audit](fact-audit.json), [ground truth](ground-truth-results.json), "
                 "[runtime](runtime-results.json), [builds](build-runtime-results.json), "
                 "[functional](functional-results.json), [official comparison](official-comparison.json)."), "",
                 "## Previous report correction / 旧数据更正", "",
                 ("The earlier 27.9% report used Python 3.10's limited TOML fallback, accepted incomplete caches, "
                 "and labeled Rust challenges without scanning. It is retained in [history](history/2026-09-15-bootstrap-results.json) "
                 "for audit only and is superseded. The new result is not a before/after analyzer improvement claim."), ""]
    return "\n".join(sections)


def main() -> None:
    argparse.ArgumentParser().parse_args()
    results, truth = load("results.json"), load("ground-truth-results.json")
    runtime, functional, builds = load("runtime-results.json"), load("functional-results.json"), load("build-runtime-results.json")
    audit = load("fact-audit.json")
    markdown = render(results, truth, runtime, functional, builds, audit)
    (ROOT / "benchmark/report.md").write_text(markdown, encoding="utf-8")
    write_json(ROOT / "benchmark/report.json", {
        "summary": results["summary"], "ground_truth": {key: value for key, value in truth.items() if key != "repositories"},
        "fact_audit": {key: value for key, value in audit.items() if key != "facts"},
        "failure_counts": dict(Counter(failure_code(item) for item in results["repositories"] if item["status"] != "STATIC_READY")),
    })
    render_chart(results, truth, ROOT / "docs/assets/public-benchmark.svg")


if __name__ == "__main__":
    main()
