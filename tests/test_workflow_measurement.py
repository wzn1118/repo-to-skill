import json
import sys
from copy import deepcopy
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from compare_workflow_measurements import compare
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
