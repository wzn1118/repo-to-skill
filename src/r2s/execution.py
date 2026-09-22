from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import threading
import time
import uuid
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, BinaryIO

from r2s.bundle_contracts import BundleProvenance
from r2s.bundle_validation import bundle_digest, inventory, validate_path
from r2s.domain import Finding
from r2s.scan_policy import INCOMPLETE_REASONS, scan_policy_for, scan_profile_for_id
from r2s.scanner import scan
from r2s.serialization import canonical_json, canonical_sha256, file_sha256

MAX_SOURCE_BYTES = 64 * 1024 * 1024
MAX_OUTPUT_BYTES = 65536
PYTHON_INVOKER = (
    "import importlib,sys; target=sys.argv.pop(1); "
    "module,symbol=target.split(':',1); entry=importlib.import_module(module); "
    "exec('for part in symbol.split(\".\"):\\n entry=getattr(entry,part)'); "
    "sys.exit(entry())"
)


@dataclass(frozen=True)
class ExecutionPolicy:
    image: str
    network: str = "none"
    read_only_source: bool = True
    user: str = "65534:65534"
    cpus: str = "1"
    memory: str = "768m"
    pids_limit: str = "64"
    timeout_seconds: int = 120
    open_files: int = 128


@dataclass(frozen=True)
class ExecutionResult:
    status: str
    argv: tuple[str, ...]
    exit_code: int | None
    stdout: str
    stderr: str
    elapsed_seconds: float
    policy: ExecutionPolicy
    image_id: str | None = None
    image_repository_digests: tuple[str, ...] = ()
    source_sha256: str | None = None
    source_files: dict[str, str] | None = None
    bundle_sha256: str | None = None
    cleanup_status: str = "NOT_STARTED"
    scope: str = "process execution only; no task oracle or runtime readiness assertion"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _policy(policy: ExecutionPolicy, command: tuple[str, ...]) -> None:
    if (
        policy.network != "none" or not policy.read_only_source or policy.user != "65534:65534"
        or policy.cpus not in {"1", "2"} or policy.memory not in {"256m", "512m", "768m", "1024m"}
        or policy.pids_limit not in {"32", "64", "128"}
        or type(policy.timeout_seconds) is not int or not 1 <= policy.timeout_seconds <= 600
        or type(policy.open_files) is not int or policy.open_files not in {128, 256, 512, 1024}
        or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_./:@-]{0,255}", policy.image)
    ):
        raise ValueError("EXECUTION_POLICY_UNSAFE")
    if (
        not command or not command[0] or len(command) > 128
        or any(not isinstance(arg, str) or "\0" in arg or len(arg) > 8192 for arg in command)
    ):
        raise ValueError("EXECUTION_ARGV_INVALID")


def docker_argv(
    policy: ExecutionPolicy, source: Path, command: tuple[str, ...],
    name: str = "r2s-exec-preview",
) -> tuple[str, ...]:
    _policy(policy, command)
    if not source.is_dir() or source.is_symlink():
        raise ValueError("EXECUTION_SOURCE_INVALID")
    if not re.fullmatch(r"r2s-exec-[a-z0-9-]+", name) or "," in str(source.resolve()):
        raise ValueError("EXECUTION_SOURCE_INVALID")
    return (
        "docker", "run", "--rm", "--name", name, "--pull=never", "--network=none", "--read-only",
        "--cap-drop=ALL", "--security-opt=no-new-privileges", "--user", policy.user,
        "--cpus", policy.cpus, "--memory", policy.memory, "--memory-swap", policy.memory,
        "--pids-limit", policy.pids_limit, "--ulimit", "fsize=67108864:67108864",
        "--ulimit", f"nofile={policy.open_files}:{policy.open_files}", "--log-driver=none",
        "--tmpfs", "/tmp:rw,exec,nosuid,nodev,size=128m",
        "--workdir=/tmp", "--env=HOME=/tmp", "--env=XDG_CACHE_HOME=/tmp/cache",
        "--env=PYTHONDONTWRITEBYTECODE=1", "--env=PYTHONPATH=/source/src:/source",
        "--env=GOTOOLCHAIN=local", "--env=CGO_ENABLED=0",
        "--mount", f"type=bind,src={source.resolve()},dst=/source,readonly",
        "--entrypoint", command[0], policy.image, *command[1:],
    )


def _source_files(source: Path, scan_profile: str = "default") -> dict[str, str]:
    if source.is_symlink() or source.resolve() in {Path("/"), Path.home()}:
        raise ValueError("EXECUTION_SOURCE_INVALID")
    scanned = scan(source, policy=scan_policy_for(scan_profile))
    if any(item.reason in INCOMPLETE_REASONS for item in scanned.inventory):
        raise ValueError("EXECUTION_SOURCE_SCAN_INCOMPLETE")
    if sum(item.size for item in scanned.inventory if item.classification == "source") > MAX_SOURCE_BYTES:
        raise ValueError("EXECUTION_SOURCE_TOO_LARGE")
    result = {}
    for item in scanned.inventory:
        if item.classification != "source" or item.content_sha256 is None:
            continue
        path = source / item.path
        data = path.read_bytes()
        if (
            re.search(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", data)
            or re.search(rb"\b(?:ghp_|github_pat_)[A-Za-z0-9_]{30,}", data)
        ):
            raise ValueError("EXECUTION_SOURCE_SECRET")
        result[item.path] = item.content_sha256
    return result


def _docker_environment(home: Path) -> dict[str, str]:
    environment = {key: value for key, value in os.environ.items() if key in {"PATH", "SYSTEMROOT", "WINDIR"}}
    environment.update({"HOME": str(home), "DOCKER_CONFIG": str(home), "LANG": "C.UTF-8"})
    return environment


def _image_identity(image: str, environment: dict[str, str]) -> tuple[str, tuple[str, ...]]:
    try:
        inspected = subprocess.run(
            ["docker", "image", "inspect", image], check=True, capture_output=True,
            text=True, timeout=15, env=environment,
        )
        record = json.loads(inspected.stdout)[0]
        value = record["Id"]
        if record["Os"] != "linux" or not re.fullmatch(r"sha256:[a-f0-9]{64}", value):
            raise ValueError("EXECUTION_IMAGE_UNSUPPORTED")
        return value, tuple(record.get("RepoDigests") or ())
    except (OSError, subprocess.SubprocessError, ValueError, TypeError, KeyError, IndexError) as exc:
        raise ValueError("EXECUTION_IMAGE_UNAVAILABLE") from exc


def _cleanup(name: str, environment: dict[str, str]) -> str:
    try:
        subprocess.run(
            ["docker", "rm", "--force", name], capture_output=True, timeout=15,
            check=False, env=environment,
        )
        probe = subprocess.run(
            ["docker", "ps", "-aq", "--filter", f"name=^{name}$"], capture_output=True,
            check=False, timeout=15, env=environment,
        )
        return "REMOVED" if probe.returncode == 0 and not probe.stdout.strip() else "UNKNOWN"
    except (OSError, subprocess.SubprocessError):
        return "UNKNOWN"


def _capture(
    argv: tuple[str, ...], timeout: int, environment: dict[str, str], name: str,
) -> tuple[str, int | None, str, str, str]:
    output = {"stdout": bytearray(), "stderr": bytearray()}
    overflow = threading.Event()
    failures = threading.Event()

    def drain(stream: BinaryIO, key: str) -> None:
        try:
            while chunk := stream.read(4096):
                remaining = MAX_OUTPUT_BYTES - len(output[key])
                output[key].extend(chunk[:max(remaining, 0)])
                if len(chunk) > remaining:
                    overflow.set()
        except (OSError, ValueError):
            failures.set()

    process = subprocess.Popen(
        argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, env=environment,
    )
    assert process.stdout is not None and process.stderr is not None
    readers = [
        threading.Thread(target=drain, args=(process.stdout, "stdout"), daemon=True),
        threading.Thread(target=drain, args=(process.stderr, "stderr"), daemon=True),
    ]
    for reader in readers:
        reader.start()
    deadline = time.monotonic() + timeout
    status = "COMPLETED"
    try:
        while process.poll() is None:
            if overflow.is_set():
                status = "OUTPUT_LIMIT"
                break
            if time.monotonic() >= deadline:
                status = "TIMEOUT"
                break
            overflow.wait(0.05)
    finally:
        cleanup_status = _cleanup(name, environment)
        if process.poll() is None:
            process.kill()
        process.wait(timeout=10)
        for reader in readers:
            reader.join(timeout=2)
        process.stdout.close()
        process.stderr.close()
    if status == "COMPLETED":
        status = "OUTPUT_LIMIT" if overflow.is_set() else (
            "COMPLETED" if process.returncode == 0 and not failures.is_set() else "FAILED"
        )
    if cleanup_status != "REMOVED":
        status = "CLEANUP_FAILED"
    return (
        status, process.returncode, output["stdout"].decode("utf-8", errors="replace"),
        output["stderr"].decode("utf-8", errors="replace"), cleanup_status,
    )


def run_sandbox(
    source: Path, command: tuple[str, ...], policy: ExecutionPolicy, execute: bool = False,
    expected_source_sha256: str | None = None,
    scan_profile: str = "default",
) -> ExecutionResult:
    _policy(policy, command)
    source_files = _source_files(source, scan_profile)
    source_sha = canonical_sha256(source_files)
    if expected_source_sha256 is not None and source_sha != expected_source_sha256:
        raise ValueError("EXECUTION_SOURCE_CHANGED")
    if not execute:
        return ExecutionResult(
            "PREVIEW", docker_argv(policy, source, command), None, "", "", 0.0, policy,
            source_sha256=source_sha, source_files=source_files,
        )
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="r2s-execution-") as directory:
        temporary = Path(directory)
        temporary.chmod(0o755)
        snapshot = temporary / "source"
        snapshot.mkdir(mode=0o755)
        environment = _docker_environment(temporary)
        image_id, repository_digests = _image_identity(policy.image, environment)
        pinned = replace(policy, image=image_id)
        for relative, digest in source_files.items():
            path = source / relative
            if path.is_symlink() or file_sha256(path) != digest:
                raise ValueError("EXECUTION_SOURCE_CHANGED")
            destination = snapshot / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(path.read_bytes())
            destination.chmod(0o644)
            if file_sha256(destination) != digest:
                raise ValueError("EXECUTION_SOURCE_CHANGED")
        name = "r2s-exec-" + uuid.uuid4().hex[:20]
        argv = docker_argv(pinned, snapshot, command, name)
        status, exit_code, stdout, stderr, cleanup = _capture(
            argv, pinned.timeout_seconds, environment, name,
        )
        return ExecutionResult(
            status, argv, exit_code, stdout, stderr, round(time.monotonic() - started, 3), pinned,
            image_id, repository_digests, source_sha, source_files, cleanup_status=cleanup,
        )


def verify_bundle(
    bundle: Path, policy: ExecutionPolicy, source: Path | None = None, execute: bool = False,
    arguments: tuple[str, ...] | None = None,
) -> tuple[ExecutionResult | None, list[Finding]]:
    findings = validate_path(bundle)
    if findings:
        return None, findings
    if source is None or arguments is None:
        return None, [Finding(
            "EXECUTION_INPUT_REQUIRED", "error",
            "Provide source and explicit --arg values; no flags or invocation are inferred",
        )]
    skill = bundle
    if (bundle / "skills").is_dir():
        skills = sorted(path for path in (bundle / "skills").iterdir() if path.is_dir())
        if len(skills) != 1:
            return None, [Finding("EXECUTION_AMBIGUOUS", "error", "Select one portable Skill")]
        skill = skills[0]
    try:
        bundle_files, bundle_findings = inventory(bundle)
        if bundle_findings:
            raise ValueError("EXECUTION_BUNDLE_CHANGED")
        verified_bundle_sha256 = bundle_digest(bundle_files)
        if validate_path(bundle, expected_digest=verified_bundle_sha256):
            raise ValueError("EXECUTION_BUNDLE_CHANGED")
        provenance_key = (skill / "PROVENANCE.json").relative_to(bundle).as_posix()
        provenance = BundleProvenance.model_validate_json(bundle_files[provenance_key])
        scan_profile = scan_profile_for_id(provenance.source_snapshot.scan_policy_id)
        files = _source_files(source, scan_profile)
        for evidence in provenance.evidence:
            if files.get(evidence.source.path) != evidence.source.content_sha256:
                raise ValueError("EXECUTION_SOURCE_MISMATCH")
        claim = next(item for item in provenance.claims if item.id == provenance.document.entrypoint_claim_id)
        target = claim.object.get("target")
        if not isinstance(target, str):
            raise TypeError("EXECUTION_ENTRYPOINT_UNSUPPORTED")
        kinds = {item.kind for item in provenance.evidence if item.id in claim.evidence_ids}
        if "manifest.entrypoint" in kinds:
            from r2s.policy import is_safe_python_target

            module, separator, symbol = target.partition(":")
            if not separator or not is_safe_python_target(module, symbol):
                raise ValueError("EXECUTION_ENTRYPOINT_UNSUPPORTED")
            source_module = module.replace(".", "/")
            if not any(path in files for path in [
                f"{source_module}.py", f"{source_module}/__init__.py",
                f"src/{source_module}.py", f"src/{source_module}/__init__.py",
            ]):
                raise ValueError("EXECUTION_ENTRYPOINT_MISSING")
            command = ("python", "-c", PYTHON_INVOKER, target, *arguments)
        elif "javascript.bin" in kinds and target in files and Path(target).suffix in {".js", ".cjs", ".mjs"}:
            command = ("node", f"/source/{target}", *arguments)
        else:
            raise ValueError("EXECUTION_BUILD_PROFILE_REQUIRED")
        result = run_sandbox(
            source, command, policy, execute, expected_source_sha256=canonical_sha256(files),
            scan_profile=scan_profile,
        )
        result = replace(result, bundle_sha256=verified_bundle_sha256)
        return result, []
    except (ValueError, TypeError, OSError, StopIteration) as exc:
        code = str(exc) if isinstance(exc, ValueError) else "EXECUTION_INPUT_INVALID"
        return None, [Finding(code, "error", "Source invocation could not be verified")]


def write_execution_result(path: Path, result: ExecutionResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(canonical_json(result.to_dict()))
