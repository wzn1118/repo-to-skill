from __future__ import annotations

import argparse
import html
import json
from collections import Counter
from pathlib import Path

from measurement_identity import write_new
from public_sources import digest

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--skill-seekers-raw", type=Path, required=True)
    args = parser.parse_args()
    if (args.run / "README.md").exists() or (args.run / "manifest.json").exists():
        raise ValueError("REPORT_ALREADY_WRITTEN")
    measured = json.loads((args.run / "attempt-1.json").read_text())
    competitor = json.loads(args.skill_seekers_raw.read_text())
    comparison = {key: value for key, value in competitor.items() if key != "records"}
    comparison["raw_sha256"] = digest(args.skill_seekers_raw)
    comparison["raw_retention"] = "Complete unmodified output retained on the data disk; public summary excludes generated upstream text. Reproduce with measure_skill_seekers.py."
    comparison["records"] = [{"id": item["id"], "repository": item["repository"], "commit_sha": item["commit_sha"], "status": item["status"], "elapsed_seconds": item["elapsed_seconds"], "exit_code": item.get("exit_code"), "skill_bytes": len((item.get("skill_markdown") or "").encode()), "bundle_bytes": sum(value["bytes"] for value in item.get("files", {}).values()), "files": item.get("files", {}), "stderr": item.get("stderr")} for item in competitor["records"]]
    write_new(args.run / "skill-seekers-summary.json", comparison)
    rows = []
    chart = []
    for index, repository in enumerate(("psf/black", "pre-commit/pre-commit", "junegunn/fzf", "prettier/prettier", "cli/cli")):
        selected = [item for item in measured["records"] if item["repository"] == repository]
        passed = sum(item["status"] == "PASS" for item in selected)
        failures = Counter(item.get("reason", "runtime failure").split(":")[0] for item in selected if item["status"] != "PASS")
        rows.append(f"| {repository} | {passed}/{len(selected)} | {'; '.join(f'{reason} × {count}' for reason, count in failures.items()) or 'none'} |")
        position = 105 + index*48
        chart.extend([f'<text x="24" y="{position+19}" fill="#e2e8f0" font-size="14">{html.escape(repository)}</text>', f'<rect x="234" y="{position}" width="340" height="26" rx="4" fill="#334155"/>', f'<rect x="234" y="{position}" width="{340*passed/len(selected):.1f}" height="26" rx="4" fill="#22c55e"/>', f'<text x="592" y="{position+19}" fill="#e2e8f0" font-size="14">{passed}/{len(selected)}</text>'])
    svg = '<svg xmlns="http://www.w3.org/2000/svg" width="720" height="414" viewBox="0 0 720 414"><rect width="720" height="414" rx="16" fill="#0f172a"/><g font-family="Arial,sans-serif"><text x="24" y="38" fill="white" font-size="23">Generated invocations: '+str(measured["passed"])+"/"+str(measured["selected"])+' tasks pass</text><text x="24" y="68" fill="#94a3b8" font-size="14">Fixed source + independent file/output oracles · all failures retained</text>'+''.join(chart)+'<text x="24" y="384" fill="#94a3b8" font-size="14">Structured inputs, not Agent trials. No task-uplift claim.</text></g></svg>\n'
    with (args.run / "tasks.svg").open("x") as handle:
        handle.write(svg)
    output = ["# Bound workflow measurement — 2026-09-21", "", f"**{measured['passed']}/{measured['selected']} frozen tasks pass using generated invocations.**", "", "Agent-authored structured inputs, generated argv, fixed upstream SHA, offline Docker and independent file/content oracles. **Not natural-language planning accuracy, Agent success or uplift.**", "", "![Task results](tasks.svg)", "", "| Repository | Passed / selected | Retained failures |", "| --- | ---: | --- |", *rows, "", "Inputs: existing Black/pre-commit tasks from `benchmark/tasks/cli-value-v2.json`, plus `benchmark/tasks/cross-language-v1.json`. Oracles were fixed before this run; no failures were removed. Prettier's two valid bindings cannot enter execution because its source scan is incomplete. The other four Prettier tasks and all four gh tasks lack supported bindings. Black custom callbacks and fzf custom argument consumption remain unknown. A blocked task is included in the selected denominator, not called executed.", "", "## Comparisons and boundaries", "", "- v13 validated authored reference argv only. This run compiles explicit task inputs into a Skill and executes the generated Procedure; those measurements are **not** a before/after Agent score.", "- Skill Seekers **3.9.0** generated output for all five identical source snapshots, using its `analyze_codebase` API, deep defaults and enhancement level 0. Its broader documentation product is not a CLI-only compiler. No correctness or superiority conclusion follows from file size or generation alone.", "- `skill-seekers-summary.json` retains file hashes, sizes, elapsed time, stderr, package identity and the complete raw-output hash. Copied upstream generated text remains local, not republished here.", "- Budget: competitor 1 CPU / 1 GiB / 180 seconds per repository; our task runner 1 CPU / 768 MiB / 120-second outer limit per task. Generation and task-execution times are different operations: **no speed ranking**.", "- Two real upstream commits each for Black and pre-commit: the unchanged sample workflow and oracle pass on both versions (4/4 checks). Capability drift is conservative; this does not establish minimal rebuild precision or a repair success.", "- Registered holdouts: dbt-core UNSUITABLE, AWS CLI REVIEW_REQUIRED, Ansible REVIEW_REQUIRED. First outcomes are retained, no tuning against this cohort preceded this run. They are excluded from the 36-Core headline; the cohort is now exposed.", "- Model-enhanced Skill Seekers, upstream-docs Agent, v13 Agent and upgraded Agent arms: **NOT_RUN**, no authorized experimental model gateway configuration. Actual model usage and uplift are null. Loopback gateway contract tests are not model trials.", "- Complete 200-fact semantic gold, human sign-off and native-client loading remain pending. Failure taxonomy drives the next work; no zero-hallucination claim.", "", "## Reproduction", "", "```bash", "python scripts/measure_bound_workflows.py --snapshots /data/snapshots --wheels /data/wheels \\", "  --work /data/new-run --output new-attempt.json --image sha256:<installed-image-id> \\", "  --cross-language benchmark/tasks/cross-language-v1.json --node /path/to/node \\", "  --node-dependencies /data/prettier/node_modules --fzf-binary /data/fzf/program \\", "  --fzf-build-report benchmark/build-runtime-results.json --execute", "python scripts/measure_skill_seekers.py --snapshots /data/snapshots \\", "  --dependencies /data/skill-seekers-3.9.0/deps --image sha256:<installed-image-id> \\", "  --output new-competitor-attempt.json --execute", "```", "", "Images, Python wheel set, runtime binaries and JS dependency preparation must precede execution. Hashes and actual argv are in `attempt-1.json`; the fzf build receipt must match. No host target-code execution or dependency downloads happen during tasks.", "", "## 中文结论", "", "已有三种工具的具体任务可由生成调用完成：格式化、配置/manifest 校验、筛选和输出文件。并非五个工具都已经支持完整任务。12 个失败全部保留，尤其不绕过 Prettier 的扫描门槛，也不为 gh 编造参数。模型、人工签核、200 条语义金标和原生客户端链路尚未完成。", ""]
    with (args.run / "README.md").open("x", encoding="utf-8") as handle:
        handle.write("\n".join(output))


if __name__ == "__main__":
    main()
