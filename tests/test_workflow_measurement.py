import json
import sys
from copy import deepcopy
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from compare_workflow_measurements import compare, compare_versions
from measure_bound_workflows import verify_native_receipt

from r2s.serialization import file_sha256


@pytest.mark.parametrize("tool", ["fzf", "github-cli"])
def test_native_binary_requires_matching_successful_source_build(tmp_path, tool):
    executable = tmp_path / "program"
    executable.write_bytes(b"not executed")
    record = {"id": tool, "commit_sha": "a" * 40}
    item = {**record, "binary_sha256": file_sha256(executable), "offline_build_or_smoke": {"exit_code": 0}}
    receipt = tmp_path / "receipt.json"
    receipt.write_text(json.dumps({"repositories": [item]}))
    verify_native_receipt(record, executable, receipt)
    for change in ({"commit_sha": "b" * 40}, {"binary_sha256": "c" * 64}, {"offline_build_or_smoke": {"exit_code": 1}}):
        receipt.write_text(json.dumps({"repositories": [{**item, **change}]}))
        with pytest.raises(ValueError, match="RUNTIME_BUILD_RECEIPT_MISMATCH"):
            verify_native_receipt(record, executable, receipt)
    with pytest.raises(ValueError, match="RUNTIME_BUILD_RECEIPT_MISMATCH"):
        verify_native_receipt(record, executable, None)


@pytest.mark.parametrize("mutation", ["source", "oracle", "duplicate", "numerator", "compiler"])
def test_comparison_rejects_changed_conditions_and_dishonest_totals(mutation):
    original = {"selected": 1, "passed": 0, "compiler_sha256": "a" * 64, "runner_sha256": "b" * 64,
                "records": [{"id": "task", "repository": "sample/tool", "commit_sha": "c" * 40, "reference_sha256": "d" * 64, "status": "FAIL", "reason": "UNKNOWN"}]}
    assert compare(original, original, original)["identical_task_inputs_and_source_pins"]
    changed = deepcopy(original)
    if mutation == "source":
        changed["records"][0]["commit_sha"] = "e" * 40
    elif mutation == "oracle":
        changed["records"][0]["reference_sha256"] = "e" * 64
    elif mutation == "duplicate":
        changed["records"].append(changed["records"][0])
    elif mutation == "numerator":
        changed["passed"] = 1
    else:
        changed["compiler_sha256"] = "e" * 64
    with pytest.raises(ValueError, match="MEASUREMENT_"):
        compare(original, original, changed)


@pytest.mark.parametrize("mutation", ["none", "policy", "worker", "runtime", "oracle", "scan", "runner", "missing_execution"])
def test_version_comparison_checks_real_environment_and_blocked_task_transitions(mutation):
    task = {"files": {}, "expected_exit_codes": [0], "oracle": {"stdout_exact": "ok"}, "python_dependencies": [], "runtime": {"kind": "python"}, "timeout_seconds": 30, "output_limit": 1000}
    execution = {"status": "PASS", "execution_policy": {"open_files": 1024}, "image_id": "image", "source_files_sha256": "source", "wheel_sha256": {}, "runtime_files_sha256": {}, "worker_sha256": "worker", "task": task}
    record = {"id": "first", "repository": "sample/tool", "commit_sha": "commit", "reference_sha256": "reference", "status": "PASS", "scan_profile": "expanded", "scan_limits": {"files": 40000}, "task_result": execution}
    blocked = {**deepcopy(record), "id": "second", "status": "FAIL"}
    blocked.pop("task_result")
    previous = {"selected": 2, "passed": 1, "compiler_sha256": "old", "runner_sha256": "runner", "source_taskset_sha256": "taskset", "cross_language_taskset_sha256": "cross", "records": [record, blocked]}
    current = deepcopy(previous)
    current.update(passed=2, compiler_sha256="new")
    current["records"][1].update(status="PASS", task_result=deepcopy(execution))
    changed = current["records"][0]
    if mutation == "policy":
        changed["task_result"]["execution_policy"]["open_files"] = 128
    elif mutation == "worker":
        changed["task_result"]["worker_sha256"] = "different"
    elif mutation == "runtime":
        changed["task_result"]["task"]["runtime"]["kind"] = "native"
    elif mutation == "oracle":
        changed["task_result"]["task"]["oracle"] = {"stdout_exact": "easier"}
    elif mutation == "scan":
        changed["scan_limits"]["files"] = 80000
    elif mutation == "runner":
        current["runner_sha256"] = "changed"
    elif mutation == "missing_execution":
        changed.pop("task_result")
    if mutation == "none":
        result = compare_versions(previous, current)
        assert result["newly_passing"] == ["second"]
        assert result["paired_execution_ids"] == ["first"]
        assert result["regressions"] == []
    else:
        with pytest.raises(ValueError, match="MEASUREMENT_"):
            compare_versions(previous, current)
