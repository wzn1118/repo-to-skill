from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path

from compare_workflow_measurements import index_measurement
from measurement_identity import write_new

from r2s.serialization import canonical_sha256, file_sha256


def compare_addition(previous: dict, current: dict, receipt: dict, repository: str) -> dict:
    before, after = index_measurement(previous), index_measurement(current)
    if not before or set(before) != set(after):
        raise ValueError("RUNTIME_COMPARISON_TASK_SET_CHANGED")
    for key in ("compiler_sha256", "runner_sha256", "source_taskset_sha256", "cross_language_taskset_sha256"):
        if not previous.get(key) or previous[key] != current.get(key):
            raise ValueError("RUNTIME_COMPARISON_COMPILER_OR_TASK_CHANGED")
    additions = receipt.get("added_files")
    if receipt.get("all_existing_files_unchanged") is not True or not isinstance(additions, dict) or not additions:
        raise ValueError("RUNTIME_ADDITION_RECEIPT_INVALID")
    checked = []
    for identifier, original in before.items():
        updated = after[identifier]
        for key in ("repository", "commit_sha", "reference_sha256", "scan_profile", "scan_limits"):
            if original[key] != updated[key]:
                raise ValueError("RUNTIME_COMPARISON_CONDITIONS_CHANGED")
        original_run, updated_run = original.get("task_result"), updated.get("task_result")
        if original_run is None or updated_run is None:
            raise ValueError("RUNTIME_COMPARISON_EXECUTION_MISSING")
        if original_run["status"] != original["status"] or updated_run["status"] != updated["status"]:
            raise ValueError("RUNTIME_COMPARISON_STATUS_MISMATCH")
        for key in ("execution_policy", "image_id", "source_files_sha256", "wheel_sha256", "worker_sha256"):
            if original_run[key] != updated_run[key]:
                raise ValueError("RUNTIME_COMPARISON_UNDECLARED_ENVIRONMENT_CHANGE")
        expected_task = deepcopy(original_run["task"])
        if original["repository"] == repository:
            old_files, new_files = original_run["runtime_files_sha256"], updated_run["runtime_files_sha256"]
            if additions.keys() & old_files.keys() or new_files != {**old_files, **additions}:
                raise ValueError("RUNTIME_COMPARISON_FILES_NOT_ADDITIVE")
            if canonical_sha256(old_files) != receipt["original_inventory_sha256"] or canonical_sha256(new_files) != receipt["updated_inventory_sha256"]:
                raise ValueError("RUNTIME_COMPARISON_INVENTORY_MISMATCH")
            if expected_task["runtime"]["dependency_files_sha256"] != receipt["original_inventory_sha256"]:
                raise ValueError("RUNTIME_COMPARISON_TASK_INVENTORY_MISMATCH")
            expected_task["runtime"]["dependency_files_sha256"] = receipt["updated_inventory_sha256"]
            checked.append(identifier)
        elif original_run["runtime_files_sha256"] != updated_run["runtime_files_sha256"]:
            raise ValueError("RUNTIME_COMPARISON_UNDECLARED_REPOSITORY_CHANGE")
        if expected_task != updated_run["task"]:
            raise ValueError("RUNTIME_COMPARISON_BOUND_TASK_CHANGED")
    if not checked:
        raise ValueError("RUNTIME_COMPARISON_REPOSITORY_MISSING")
    return {
        "format": "r2s-runtime-addition-comparison-v1", "selected": len(before),
        "previous_passed": previous["passed"], "current_passed": current["passed"],
        "repository_with_changed_environment": repository, "checked_dependency_change_tasks": checked,
        "identical_compiler_and_runner": True, "identical_inputs_and_oracles": True,
        "identical_environment": False, "added_runtime_files": additions,
        "newly_passing": [key for key in before if before[key]["status"] != "PASS" and after[key]["status"] == "PASS"],
        "regressions": [key for key in before if before[key]["status"] == "PASS" and after[key]["status"] != "PASS"],
        "still_failing": [key for key in after if after[key]["status"] != "PASS"],
        "scope": "Same compiler, source, task, oracle and resource limits. Only the explicit dependency-file addition changes the selected repository's runtime; not analyzer uplift, same-environment comparison or Agent trials.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--previous", required=True, type=Path)
    parser.add_argument("--current", required=True, type=Path)
    parser.add_argument("--addition", required=True, type=Path)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = compare_addition(json.loads(args.previous.read_text()), json.loads(args.current.read_text()), json.loads(args.addition.read_text()), args.repository)
    result["inputs_sha256"] = {name: file_sha256(getattr(args, name)) for name in ("previous", "current", "addition")}
    result["comparison_script_sha256"] = file_sha256(Path(__file__))
    write_new(args.output, result)
    print(json.dumps({key: result[key] for key in ("previous_passed", "current_passed", "identical_environment", "newly_passing")}))


if __name__ == "__main__":
    main()
