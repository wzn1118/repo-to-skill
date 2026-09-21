import os

import pytest
from test_tasks import task_bundle

from r2s.analyzers import discover
from r2s.execution import ExecutionPolicy
from r2s.repair import repair_workflow
from r2s.workflows import WorkflowRequest


@pytest.mark.skipif(not os.environ.get("R2S_TEST_IMAGE"), reason="explicit Docker image required")
def test_repair_preserves_failed_attempt_and_same_file_oracle(tmp_path):
    source, _bundle, task = task_bundle(tmp_path)
    initial = WorkflowRequest.model_validate({"title": "Export JSON", "steps": [{"command": "demo", "parameters": {"source": ["input.txt"], "--output": ["wrong.json"]}, "expected_observation": "result.json contains all records"}]})
    corrected = initial.model_copy(deep=True)
    corrected.steps[0].parameters["--output"] = ["result.json"]
    report = repair_workflow(discover(source), source, task, initial, tmp_path / "repair", ExecutionPolicy(os.environ["R2S_TEST_IMAGE"]), lambda failure: corrected)
    assert [attempt["result"]["status"] for attempt in report["attempts"]] == ["FAIL", "PASS"]
    assert len({attempt["frozen_acceptance_sha256"] for attempt in report["attempts"]}) == 1
    assert (tmp_path / "repair/attempt-1/result.json").exists()
