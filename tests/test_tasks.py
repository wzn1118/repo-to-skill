import json
import os
import sys
from pathlib import Path

import pytest

from r2s.analyzers import discover
from r2s.execution import ExecutionPolicy
from r2s.generator import generate
from r2s.scan_policy import scan_policy_for
from r2s.task_worker import oracle_failures, process
from r2s.tasks import TaskOracle, run_task, task_for_bundle
from r2s.workflows import WorkflowRequest


@pytest.mark.parametrize("content", ["", "{}", '{"records":[]}', '{"records":[1,2]'])
def test_json_oracle_rejects_empty_partial_wrong_and_malformed_outputs(tmp_path, content):
    (tmp_path / "output.json").write_text(content)
    assert oracle_failures(tmp_path, {"json_files": {"output.json": {"records": [1, 2, 3]}}}, "", "")


def test_trivial_contains_is_not_an_acceptance_condition():
    with pytest.raises(ValueError, match="EMPTY_CONTAINS"):
        TaskOracle(stdout_contains="")


def test_worker_stdin_and_logs_do_not_clobber_input_files(tmp_path):
    (tmp_path / "stdout.log").write_text("important input")
    result = process([sys.executable, "-c", "import sys; print(sys.stdin.read().upper(),end='')"], tmp_path, dict(os.environ), 3, 100, "hello\n")
    assert result["status"] == "COMPLETED" and result["stdout"] == "HELLO" + os.linesep
    assert (tmp_path / "stdout.log").read_text() == "important input"


def test_stdin_is_retained_in_generated_workflow(tmp_path):
    source, _bundle, _task = task_bundle(tmp_path)
    workflow = WorkflowRequest.model_validate({"title": "Explicit stdin", "steps": [{"command": "demo", "parameters": {"source": ["input.txt"], "--output": ["result.json"]}, "stdin": "one\ntwo\n", "expected_observation": "check result.json"}]})
    result = generate(discover(source), "export", tmp_path / "stdin-build", "portable", workflow=workflow)
    bundle = Path(result.bundles[0])
    assert "one\\ntwo\\n" in (bundle / "SKILL.md").read_text()
    assert json.loads((bundle / "PROVENANCE.json").read_text())["procedure"]["steps"][0]["stdin"] == "one\ntwo\n"


def task_bundle(tmp_path: Path, expanded: bool = False):
    source = tmp_path / "source"
    source.mkdir()
    (source / "LICENSE").write_text("MIT")
    (source / "pyproject.toml").write_text('[project.scripts]\ndemo="cli:main"\n')
    (source / "cli.py").write_text('''import argparse
import json
from pathlib import Path
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("source")
    parser.add_argument("--output", required=True)
    args=parser.parse_args()
    Path(args.output).write_text(json.dumps({"records":Path(args.source).read_text().splitlines()}))
''')
    workflow = WorkflowRequest.model_validate({"title": "Export JSON", "steps": [{"command": "demo", "parameters": {"source": ["input.txt"], "--output": ["result.json"]}, "expected_observation": "JSON has all input records"}]})
    if expanded:
        (source / "large.txt").write_text("a" * (2 * 1024 * 1024 + 1))
    result = generate(discover(source, scan_policy=scan_policy_for("expanded" if expanded else "default")), "导出 JSON 文件", tmp_path / "build", "portable", workflow=workflow)
    bundle = Path(result.bundles[0])
    task = task_for_bundle(bundle, "export-json", {"input.txt": "one\ntwo\n"}, [0], TaskOracle(json_files={"result.json": {"records": ["one", "two"]}}))
    return source, bundle, task


def test_execution_preserves_expanded_bundle_scope_without_bypassing_default(tmp_path):
    from r2s.execution import _source_files, verify_bundle

    source, bundle, task = task_bundle(tmp_path, expanded=True)
    with pytest.raises(ValueError, match="EXECUTION_SOURCE_SCAN_INCOMPLETE"):
        _source_files(source)
    result = run_task(bundle, source, task, ExecutionPolicy("python:3.12-slim"))
    assert result["status"] == "PREVIEW" and result["scan_profile"] == "expanded"
    verified, findings = verify_bundle(bundle, ExecutionPolicy("python:3.12-slim"), source, arguments=("--help",))
    assert not findings and verified.status == "PREVIEW"


def test_task_preview_binds_bundle_source_and_independent_oracle(tmp_path):
    source, bundle, task = task_bundle(tmp_path)
    result = run_task(bundle, source, task, ExecutionPolicy("python:3.12-slim"))
    assert result["status"] == "PREVIEW" and not result["attempts"]
    assert json.loads(json.dumps(result))["task"]["oracle"]["json_files"]
    (source / "cli.py").write_text("tampered")
    with pytest.raises(ValueError, match="SOURCE_CHANGED"):
        run_task(bundle, source, task, ExecutionPolicy("python:3.12-slim"))


@pytest.mark.skipif(not os.environ.get("R2S_TEST_IMAGE"), reason="explicit Docker image required")
def test_generated_invocation_creates_verified_output_inside_container(tmp_path):
    source, bundle, task = task_bundle(tmp_path)
    result = run_task(bundle, source, task, ExecutionPolicy(os.environ["R2S_TEST_IMAGE"]), execute=True)
    assert result["status"] == "PASS", result
    assert result["cleanup"] == "REMOVED"
    assert not (source / "result.json").exists()
