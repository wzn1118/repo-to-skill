import json
import os
from pathlib import Path

import pytest

from r2s.analyzers import discover
from r2s.execution import MAX_OUTPUT_BYTES, ExecutionPolicy, run_sandbox, verify_bundle
from r2s.generator import generate

IMAGE = os.environ.get("R2S_TEST_IMAGE")
pytestmark = pytest.mark.skipif(not IMAGE, reason="Set R2S_TEST_IMAGE to a locally installed Linux image")


def test_container_invokes_verified_python_entrypoint(tmp_path: Path) -> None:
    source = Path(__file__).parent / "fixtures/python_cli"
    build = generate(discover(source), "inspect options", tmp_path / "build", "portable")
    result, findings = verify_bundle(
        Path(build.bundles[0]), ExecutionPolicy(IMAGE or ""), source,
        execute=True, arguments=("--output", "value"),
    )
    assert not findings
    assert result is not None
    assert result.status == "COMPLETED", result.stderr
    assert result.exit_code == 0
    assert result.cleanup_status == "REMOVED"
    assert result.image_id and result.image_id.startswith("sha256:")
    assert result.bundle_sha256 and result.source_sha256


def test_container_isolation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("R2S_HOST_SECRET", "must-not-enter-container")
    (tmp_path / ".env").write_text("R2S_PRIVATE_VALUE=must-not-be-mounted")
    (tmp_path / "probe.py").write_text(
        "import json,os,pathlib,socket\n"
        "assert os.getuid()==65534\n"
        "assert 'R2S_HOST_SECRET' not in os.environ\n"
        "assert not pathlib.Path('/source/.env').exists()\n"
        "assert not pathlib.Path('/var/run/docker.sock').exists()\n"
        "try:\n pathlib.Path('/source/probe.py').write_text('changed')\n"
        "except OSError:\n pass\n"
        "else:\n raise AssertionError('source writable')\n"
        "assert [name for _,name in socket.if_nameindex()]==['lo']\n"
        "print(json.dumps({'uid':os.getuid(),'source_readonly':True,'network':'loopback-only'}))\n"
    )
    result = run_sandbox(
        tmp_path, ("python", "/source/probe.py"), ExecutionPolicy(IMAGE or ""), execute=True,
    )
    assert result.status == "COMPLETED", result.stderr
    assert json.loads(result.stdout)["source_readonly"] is True
    assert result.cleanup_status == "REMOVED"
    assert set(result.source_files or {}) == {"probe.py"}


@pytest.mark.parametrize(("program", "status"), [
    ("import time; time.sleep(60)", "TIMEOUT"),
    ("import os;\nwhile True: os.write(1,b'x'*8192)", "OUTPUT_LIMIT"),
    ("import sys; sys.exit(7)", "FAILED"),
])
def test_container_failure_limits_and_cleanup(tmp_path: Path, program: str, status: str) -> None:
    result = run_sandbox(
        tmp_path, ("python", "-c", program),
        ExecutionPolicy(IMAGE or "", timeout_seconds=2 if status == "TIMEOUT" else 20),
        execute=True,
    )
    assert result.status == status, result.stderr
    assert len(result.stdout.encode()) <= MAX_OUTPUT_BYTES
    assert result.cleanup_status == "REMOVED"
    if status == "FAILED":
        assert result.exit_code == 7
