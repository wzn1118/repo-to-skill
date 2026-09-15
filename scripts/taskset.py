from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from public_evaluate import TASK_REQUIREMENTS as STATIC_REQUIREMENTS

ROOT = Path(__file__).resolve().parents[1]
TASK_REQUIREMENTS = {
    "prettier": ["format-a-file-with-explicit-parser", "check-format-with-config", "ignore-selected-paths"],
    "github-cli": ["inspect-repository-status", "create-and-list-issues", "query-pull-request-data"],
    "yt-dlp": ["inspect-video-metadata", "select-format", "write-output-template"],
    "eslint": ["lint-selected-files", "apply-safe-fixes", "use-configured-ignores"],
    "hugo": ["create-development-server", "build-site", "render-drafts"],
    "fzf": ["filter-input", "use-preview-command", "select-with-key-binding"],
    "black": ["format-selected-files", "check-format", "exclude-paths"],
    "pre-commit": ["run-all-hooks", "run-selected-hook", "install-hooks"],
    "webpack": ["build-with-config", "inspect-build-statistics", "use-watch-mode"],
    "poetry": ["install-project-dependencies", "add-a-dependency", "inspect-environment"],
}


def build(metadata_path: Path, truth_path: Path, output: Path) -> dict:
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    truth = json.loads(truth_path.read_text(encoding="utf-8"))
    records = {item["id"]: item for item in metadata["repositories"]}
    truth_by_id = {item["id"]: item for item in truth["repositories"]}
    tasks = []
    for repository_id, names in TASK_REQUIREMENTS.items():
        record = records[repository_id]
        facts = {item["value"]: item for item in truth_by_id[repository_id]["facts"]}
        for index, name in enumerate(names, 1):
            tasks.append({
                "id": f"{repository_id}-{index}",
                "repository": record["repository"],
                "repository_id": repository_id,
                "commit_sha": record["commit_sha"],
                "title": name,
                "input": {"goal": name.replace("-", " ")},
                "required_static_facts": [
                    facts[value] for value in STATIC_REQUIREMENTS[repository_id][index - 1]
                ],
                "execution_oracle": None,
                "scope": "selected static prerequisites only; not an executable TaskSpec",
            })
    result = {
        "format": "r2s-static-prerequisite-catalog-v1",
        "created_at": datetime.now(UTC).isoformat(),
        "source_metadata": str(metadata_path.relative_to(ROOT)),
        "source_truth": str(truth_path.relative_to(ROOT)),
        "tasks": tasks,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def validate(taskset: dict, metadata: dict) -> list[str]:
    records = {item["repository"]: item for item in metadata["repositories"]}
    errors = []
    identifiers = [item.get("id") for item in taskset.get("tasks", [])]
    if len(identifiers) != len(set(identifiers)):
        errors.append("DUPLICATE_TASK_ID")
    if len(identifiers) != 30:
        errors.append(f"TASK_COUNT:{len(identifiers)}")
    for task in taskset.get("tasks", []):
        record = records.get(task.get("repository"))
        if record is None or task.get("commit_sha") != record.get("commit_sha"):
            errors.append(f"PIN_MISMATCH:{task.get('id')}")
        if not task.get("required_static_facts") or task.get("execution_oracle") is not None:
            errors.append(f"SCOPE_INVALID:{task.get('id')}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "benchmark/taskset-v1.json")
    args = parser.parse_args()
    metadata = json.loads((ROOT / "benchmark/repository-metadata.json").read_text())
    taskset = build(ROOT / "benchmark/repository-metadata.json", ROOT / "benchmark/ground-truth-facts.json", args.output)
    errors = validate(taskset, metadata)
    print(json.dumps({"tasks": len(taskset["tasks"]), "errors": errors}, sort_keys=True))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
