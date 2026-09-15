from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import pytest

from r2s.analyzers import discover
from r2s.execution import ExecutionPolicy, docker_argv, run_sandbox, verify_bundle
from r2s.generator import generate


def test_execution_defaults_to_safe_preview(tmp_path: Path) -> None:
    policy = ExecutionPolicy("python:3.12-slim")
    result = run_sandbox(tmp_path, ("python", "--version"), policy)
    assert result.status == "PREVIEW"
    assert "--network=none" in result.argv
    assert "--read-only" in result.argv
    assert "--cap-drop=ALL" in result.argv
    assert "docker.sock" not in str(result.argv)


def test_execution_rejects_unsafe_policy(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="POLICY_UNSAFE"):
        docker_argv(ExecutionPolicy("python:3.12-slim", network="host"), tmp_path, ("true",))


def test_execution_rejects_symlink_source(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "link"
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks unavailable")
    with pytest.raises(ValueError, match="SOURCE_INVALID"):
        docker_argv(ExecutionPolicy("python:3.12-slim"), link, ("true",))


@pytest.mark.parametrize("changes", [
    {"user": "root"}, {"pids_limit": "-1"}, {"cpus": "999"}, {"memory": "128g"},
    {"timeout_seconds": 0}, {"timeout_seconds": True}, {"image": "--privileged"},
])
def test_resource_limits_cannot_be_disabled(tmp_path: Path, changes: dict) -> None:
    with pytest.raises(ValueError, match="POLICY_UNSAFE"):
        run_sandbox(tmp_path, ("true",), replace(ExecutionPolicy("python:3.12-slim"), **changes))


def test_preview_excludes_secrets_and_never_starts_docker(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("token=secret")
    (tmp_path / "tool.py").write_text("print('ok')")
    with patch("subprocess.Popen", side_effect=AssertionError("preview executed")):
        result = run_sandbox(tmp_path, ("python", "/source/tool.py"), ExecutionPolicy("python:3.12-slim"))
    assert set(result.source_files or {}) == {"tool.py"}


def test_verify_requires_explicit_arguments_and_source_identity(tmp_path: Path) -> None:
    source = Path(__file__).parent / "fixtures/python_cli"
    build = generate(discover(source), "inspect options", tmp_path / "build", "portable")
    bundle = Path(build.bundles[0])
    policy = ExecutionPolicy("python:3.12-slim")
    result, findings = verify_bundle(bundle, policy, source)
    assert result is None
    assert findings[0].code == "EXECUTION_INPUT_REQUIRED"
    result, findings = verify_bundle(bundle, policy, source, arguments=("--output", "value"))
    assert not findings
    assert result is not None
    assert "--help" not in result.argv
    assert result.argv[-3:] == ("demo_cli.main:main", "--output", "value")
    result, findings = verify_bundle(bundle, policy, tmp_path, arguments=("--help",))
    assert result is None
    assert findings[0].code == "EXECUTION_SOURCE_MISMATCH"
