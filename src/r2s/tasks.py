from __future__ import annotations

import json
import re
import shutil
import tempfile
import time
import uuid
from dataclasses import asdict, replace
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from r2s.bundle_contracts import BundleProvenance, RelativePath, Sha256
from r2s.bundle_validation import bundle_digest, inventory, validate_path
from r2s.compiler_identity import compiler_identity
from r2s.execution import (
    ExecutionPolicy,
    _capture,
    _docker_environment,
    _image_identity,
    _source_files,
    docker_argv,
)
from r2s.scan_policy import scan_profile_for_id
from r2s.serialization import canonical_json, canonical_sha256, file_sha256


class TaskOracle(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    files_exact: dict[RelativePath, str] = Field(default_factory=dict)
    files_contains: dict[RelativePath, str] = Field(default_factory=dict)
    json_files: dict[RelativePath, Any] = Field(default_factory=dict)
    absent: list[RelativePath] = Field(default_factory=list)
    stdout_exact: str | None = None
    stdout_contains: str | None = None
    stderr_contains: str | None = None

    @model_validator(mode="after")
    def nonempty_conditions(self) -> TaskOracle:
        if any(value == "" for value in (*self.files_contains.values(), self.stdout_contains, self.stderr_contains)):
            raise ValueError("TASK_EMPTY_CONTAINS_ORACLE")
        return self


class TaskRuntime(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    kind: Literal["python", "node", "native"] = "python"
    executable_sha256: Sha256 | None = None
    dependency_files_sha256: Sha256 | None = None
    build_source_sha256: Sha256 | None = None


class TaskSpec(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    format: Literal["r2s-task-v1"] = "r2s-task-v1"
    id: Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9-]{0,63}$")]
    repository_commit: str | None
    compiler_sha256: Sha256
    bundle_sha256: Sha256
    procedure_sha256: Sha256
    files: dict[RelativePath, str] = Field(default_factory=dict, max_length=128)
    expected_exit_codes: list[int] = Field(min_length=1, max_length=16)
    oracle: TaskOracle
    python_dependencies: list[Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_.-]+==[A-Za-z0-9_.+-]+$")]] = Field(default_factory=list, max_length=32)
    timeout_seconds: int = Field(default=30, ge=1, le=120)
    output_limit: int = Field(default=16384, ge=256, le=32768)
    runtime: TaskRuntime = Field(default_factory=TaskRuntime)


def task_for_bundle(bundle: Path, identifier: str, files: dict[str, str], expected_exit_codes: list[int], oracle: TaskOracle, dependencies: list[str] | None = None) -> TaskSpec:
    contents, findings = inventory(bundle)
    if findings or validate_path(bundle):
        raise ValueError("TASK_BUNDLE_INVALID")
    provenance = BundleProvenance.model_validate_json(contents["PROVENANCE.json"])
    return TaskSpec(id=identifier, repository_commit=provenance.source_snapshot.resolved_commit_sha,
                    compiler_sha256=compiler_identity("portable")["sha256"], bundle_sha256=bundle_digest(contents),
                    procedure_sha256=canonical_sha256(asdict(provenance.procedure)), files=files,
                    expected_exit_codes=expected_exit_codes, oracle=oracle, python_dependencies=dependencies or [])


def dependency_inventory(root: Path) -> dict[str, str]:
    if root.is_symlink() or not root.is_dir() or "," in str(root.resolve()):
        raise ValueError("TASK_RUNTIME_DEPENDENCIES_INVALID")
    result = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            if not path.resolve().is_relative_to(root.resolve()):
                raise ValueError("TASK_RUNTIME_DEPENDENCIES_ESCAPE")
            continue
        if path.is_file():
            result[path.relative_to(root).as_posix()] = file_sha256(path)
    return result


def run_task(bundle: Path, source: Path, task: TaskSpec, policy: ExecutionPolicy, wheels: Path | None = None, execute: bool = False, executable: Path | None = None, dependencies: Path | None = None) -> dict[str, Any]:
    contents, findings = inventory(bundle)
    if findings or validate_path(bundle, expected_digest=task.bundle_sha256):
        raise ValueError("TASK_BUNDLE_IDENTITY_MISMATCH")
    provenance = BundleProvenance.model_validate_json(contents["PROVENANCE.json"])
    if task.procedure_sha256 != canonical_sha256(asdict(provenance.procedure)) or task.repository_commit != provenance.source_snapshot.resolved_commit_sha:
        raise ValueError("TASK_SOURCE_OR_PROCEDURE_MISMATCH")
    if task.compiler_sha256 != compiler_identity("portable")["sha256"]:
        raise ValueError("TASK_COMPILER_CHANGED")
    if any(step.mode != "invocation" for step in provenance.procedure.steps) or len(task.expected_exit_codes) != len(provenance.procedure.steps):
        raise ValueError("TASK_BOUND_WORKFLOW_REQUIRED")
    if not any(value is not None and value != {} and value != [] for value in task.oracle.model_dump().values()):
        raise ValueError("TASK_INDEPENDENT_ORACLE_REQUIRED")
    if sum(len(content.encode()) for content in task.files.values()) > 1_000_000:
        raise ValueError("TASK_INPUT_TOO_LARGE")
    scan_profile = scan_profile_for_id(provenance.source_snapshot.scan_policy_id)
    source_files = _source_files(source, scan_profile)
    if any(source_files.get(item.source.path) != item.source.content_sha256 for item in provenance.evidence):
        raise ValueError("TASK_SOURCE_CHANGED")
    entry = next(claim for claim in provenance.claims if claim.id == provenance.document.entrypoint_claim_id)
    target = str(entry.object.get("target"))
    kinds = {item.kind for item in provenance.evidence if item.id in entry.evidence_ids}
    if task.runtime.kind == "python" and "manifest.entrypoint" not in kinds:
        raise ValueError("TASK_BUILD_PROFILE_REQUIRED")
    runtime_files = {}
    if task.runtime.kind != "python":
        if executable is None or executable.is_symlink() or not executable.is_file() or file_sha256(executable) != task.runtime.executable_sha256:
            raise ValueError("TASK_EXECUTABLE_IDENTITY_MISMATCH")
        if task.runtime.build_source_sha256 != canonical_sha256(source_files):
            raise ValueError("TASK_RUNTIME_SOURCE_IDENTITY_MISMATCH")
        if task.runtime.kind == "node":
            runtime_files = dependency_inventory(dependencies) if dependencies else {}
            if not runtime_files or canonical_sha256(runtime_files) != task.runtime.dependency_files_sha256 or target not in source_files:
                raise ValueError("TASK_RUNTIME_DEPENDENCIES_MISMATCH")
    wheel_files = {}
    if task.python_dependencies:
        if wheels is None or wheels.is_symlink() or not wheels.is_dir() or "," in str(wheels.resolve()):
            raise ValueError("TASK_DEPENDENCIES_REQUIRED")
        wheel_files = {path.name: file_sha256(path) for path in sorted(wheels.glob("*.whl")) if path.is_file() and not path.is_symlink()}
        if not wheel_files:
            raise ValueError("TASK_DEPENDENCIES_REQUIRED")
    record: dict[str, Any] = {"format": "r2s-task-result-v1", "task_sha256": canonical_sha256(task.model_dump()),
        "task": task.model_dump(), "worker_sha256": file_sha256(Path(__file__).with_name("task_worker.py")),
        "source_files_sha256": canonical_sha256(source_files), "wheel_sha256": wheel_files, "scan_profile": scan_profile,
        "runtime_files_sha256": runtime_files, "execution_policy": asdict(policy),
        "status": "PREVIEW", "scope": "Generated bound invocation checked by supplied independent oracle; no Agent trial", "attempts": []}
    if not execute:
        return record
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="r2s-task-") as directory:
        temporary = Path(directory)
        temporary.chmod(0o755)
        environment = _docker_environment(temporary)
        image_id, digests = _image_identity(policy.image, environment)
        pinned = replace(policy, image=image_id)
        pack = temporary / "pack"
        pack.mkdir(mode=0o755)
        for relative, digest in source_files.items():
            path = source / relative
            destination = pack / "repository" / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            if path.is_symlink() or file_sha256(path) != digest:
                raise ValueError("TASK_SOURCE_CHANGED")
            destination.write_bytes(path.read_bytes())
            destination.chmod(0o644)
            if file_sha256(destination) != digest:
                raise ValueError("TASK_SOURCE_CHANGED")
        shutil.copyfile(Path(__file__).with_name("task_worker.py"), pack / "worker.py")
        if executable is not None and task.runtime.kind != "python":
            shutil.copyfile(executable, pack / "program")
            (pack / "program").chmod(0o755)
            if file_sha256(pack / "program") != task.runtime.executable_sha256:
                raise ValueError("TASK_EXECUTABLE_CHANGED")
        payload = {"task": task.model_dump(), "target": target, "steps": [{"arguments": list(step.arguments), "stdout_file": step.stdout_file, "stdin": step.stdin} for step in provenance.procedure.steps]}
        (pack / "task.json").write_text(canonical_json(payload), encoding="utf-8")
        name = "r2s-exec-" + uuid.uuid4().hex[:20]
        argv = list(docker_argv(pinned, pack, ("python", "/source/worker.py"), name))
        if wheels is not None and task.python_dependencies:
            argv[2:2] = ["--mount", f"type=bind,src={wheels.resolve()},dst=/wheels,readonly"]
        if dependencies is not None and task.runtime.kind == "node":
            (pack / "repository" / "node_modules").mkdir(exist_ok=True)
            argv[2:2] = ["--mount", f"type=bind,src={dependencies.resolve()},dst=/source/repository/node_modules,readonly"]
        status, exit_code, stdout, stderr, cleanup = _capture(tuple(argv), policy.timeout_seconds, environment, name)
        try:
            result = json.loads(stdout) if status == "COMPLETED" else {"status": status, "stderr": stderr, "exit_code": exit_code}
        except ValueError:
            result = {"status": "WORKER_FAILED", "stderr": stderr, "stdout": stdout, "exit_code": exit_code}
        record.update(status=result["status"], attempts=[result], cleanup=cleanup, image_id=image_id, repository_digests=digests, elapsed_seconds=round(time.monotonic()-started, 3))
    if wheels is not None and any(not re.fullmatch(r"[A-Za-z0-9_.+-]+\.whl", name) or file_sha256(wheels / name) != digest for name, digest in wheel_files.items()):
        raise ValueError("TASK_DEPENDENCIES_CHANGED")
    if dependencies is not None and task.runtime.kind == "node" and dependency_inventory(dependencies) != runtime_files:
        raise ValueError("TASK_RUNTIME_DEPENDENCIES_CHANGED")
    if task.compiler_sha256 != compiler_identity("portable")["sha256"]:
        raise ValueError("TASK_COMPILER_CHANGED")
    return record
