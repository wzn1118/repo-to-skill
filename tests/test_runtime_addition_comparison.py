import sys
from copy import deepcopy
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from compare_runtime_addition import compare_addition
from render_workflow_progress import summarize

from r2s.serialization import canonical_sha256


@pytest.mark.parametrize("mutation", ["none", "compiler", "oracle", "policy", "existing_file", "extra_file", "missing_execution", "receipt"])
def test_dependency_repair_is_separate_from_analyzer_or_oracle_changes(mutation):
    original_files, added_files = {"old": "digest"}, {"native": "binary"}
    updated_files = {**original_files, **added_files}
    old_hash, new_hash = canonical_sha256(original_files), canonical_sha256(updated_files)
    execution = {"status": "FAIL", "execution_policy": {"memory": "768m"}, "image_id": "image", "source_files_sha256": "source", "wheel_sha256": {}, "worker_sha256": "worker", "runtime_files_sha256": original_files, "task": {"oracle": {"stdout_exact": "ok"}, "runtime": {"dependency_files_sha256": old_hash}}}
    execution["task"].update({"files": {}, "expected_exit_codes": [0], "python_dependencies": [], "timeout_seconds": 30, "output_limit": 1024})
    record = {"id": "task", "repository": "org/tool", "commit_sha": "pin", "reference_sha256": "ref", "scan_profile": "expanded", "scan_limits": {"files": 40000}, "status": "FAIL", "task_result": execution}
    previous = {"selected": 1, "passed": 0, "compiler_sha256": "compiler", "runner_sha256": "runner", "source_taskset_sha256": "taskset", "cross_language_taskset_sha256": "cross", "records": [record]}
    current = deepcopy(previous)
    current["passed"] = 1
    row = current["records"][0]
    row["status"] = row["task_result"]["status"] = "PASS"
    row["task_result"]["runtime_files_sha256"] = deepcopy(updated_files)
    row["task_result"]["task"]["runtime"]["dependency_files_sha256"] = new_hash
    receipt = {"all_existing_files_unchanged": True, "added_files": added_files, "original_inventory_sha256": old_hash, "updated_inventory_sha256": new_hash}
    if mutation == "compiler":
        current["compiler_sha256"] = "changed"
    elif mutation == "oracle":
        row["task_result"]["task"]["oracle"] = {"stdout_exact": "easier"}
    elif mutation == "policy":
        row["task_result"]["execution_policy"]["memory"] = "4096m"
    elif mutation == "existing_file":
        row["task_result"]["runtime_files_sha256"]["old"] = "changed"
    elif mutation == "extra_file":
        row["task_result"]["runtime_files_sha256"]["extra"] = "undeclared"
    elif mutation == "missing_execution":
        row.pop("task_result")
    elif mutation == "receipt":
        receipt["all_existing_files_unchanged"] = False
    if mutation == "none":
        result = compare_addition(previous, current, receipt, "org/tool")
        assert result["identical_environment"] is False
        assert result["identical_inputs_and_oracles"] is True
        assert result["newly_passing"] == ["task"]
        assert result["regressions"] == []
        older = deepcopy(previous)
        older["compiler_sha256"] = "older-compiler"
        progress = summarize(older, previous, current, receipt, "org/tool")
        assert progress["previous_passed"] == progress["source_change_passed"] == 0
        assert progress["runtime_repair_passed"] == 1
        assert progress["source_change"]["newly_passing"] == []
        assert progress["runtime_change"]["newly_passing"] == ["task"]
    else:
        with pytest.raises(ValueError, match="RUNTIME_"):
            compare_addition(previous, current, receipt, "org/tool")
