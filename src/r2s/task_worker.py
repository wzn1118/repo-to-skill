from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


def contained(root: Path, name: str) -> Path:
    path = root / name
    if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("TASK_PATH_ESCAPE")
    return path


def oracle_failures(root: Path, oracle: dict[str, Any], stdout: str, stderr: str) -> list[str]:
    failures = []
    for kind in ("files_exact", "files_contains", "json_files"):
        for name, expected in oracle.get(kind, {}).items():
            try:
                path = contained(root, name)
                if not path.is_file() or path.stat().st_size > 1_000_000:
                    raise ValueError("missing_or_large")
                actual = path.read_text(encoding="utf-8")
                matched = expected in actual if kind == "files_contains" else json.loads(actual) == expected if kind == "json_files" else actual == expected
                if not matched:
                    failures.append(f"{kind}:{name}:mismatch")
            except (OSError, ValueError):
                failures.append(f"{kind}:{name}:missing_or_invalid")
    for name in oracle.get("absent", []):
        if (root / name).exists() or (root / name).is_symlink():
            failures.append(f"absent:{name}")
    for key, actual in (("stdout_exact", stdout), ("stdout_contains", stdout), ("stderr_contains", stderr)):
        expected = oracle.get(key)
        if expected is not None and (expected != actual if key.endswith("exact") else expected not in actual):
            failures.append(key)
    return failures


def process(argv: list[str], directory: Path, environment: dict[str, str], timeout: int, limit: int, stdin_text: str | None = None) -> dict[str, Any]:
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        try:
            result = subprocess.run(argv, cwd=directory, env=environment, stdout=stdout, stderr=stderr, input=(stdin_text or "").encode(), timeout=timeout, check=False)
            code = result.returncode
            status = "COMPLETED"
        except subprocess.TimeoutExpired:
            code = None
            status = "TIMEOUT"
        streams = {}
        for stream, handle in (("stdout", stdout), ("stderr", stderr)):
            if handle.tell() > limit:
                status = "OUTPUT_LIMIT"
            handle.seek(0)
            streams[stream] = handle.read(limit).decode("utf-8", errors="replace")
    return {"status": status, "argv": argv, "exit_code": code, **streams}


def main() -> None:
    payload = json.loads(Path("/source/task.json").read_text())
    task = payload["task"]
    workspace = Path("/tmp/task")
    workspace.mkdir()
    environment = dict(os.environ, PYTHONPATH="/source/repository/src:/source/repository:/tmp/deps", HOME="/tmp/home", PRE_COMMIT_HOME="/tmp/pre-commit")
    Path(environment["HOME"]).mkdir()
    preparation: dict[str, Any] = {"status": "NOT_REQUIRED"}
    if task["python_dependencies"]:
        preparation = process([sys.executable, "-m", "pip", "install", "--no-index", "--find-links=/wheels", "--only-binary=:all:", "--target=/tmp/deps", *task["python_dependencies"]], workspace, environment, 60, 16000)
        if preparation["status"] != "COMPLETED" or preparation["exit_code"] != 0:
            print(json.dumps({"status": "DEPENDENCY_FAILED", "preparation": preparation, "steps": []}))
            return
    for name, content in task["files"].items():
        path = contained(workspace, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
    invoke = "import importlib,sys; module,symbol=sys.argv.pop(1).split(':'); entry=importlib.import_module(module); assert entry.__file__.startswith('/source/repository/'); exec('for part in symbol.split(\".\"):\\n entry=getattr(entry,part)'); sys.exit(entry())"
    prefix = [sys.executable, "-c", invoke, payload["target"]]
    if task["runtime"]["kind"] == "native":
        prefix = ["/source/program"]
    elif task["runtime"]["kind"] == "node":
        prefix = ["/source/program", str(contained(Path("/source/repository"), payload["target"]))]
    records = []
    failures = []
    for step, expected in zip(payload["steps"], task["expected_exit_codes"], strict=True):
        result = process([*prefix, *step["arguments"]], workspace, environment, task["timeout_seconds"], task["output_limit"], step.get("stdin"))
        records.append(result)
        if result["status"] != "COMPLETED" or result["exit_code"] != expected:
            failures.append(result["status"] if result["status"] != "COMPLETED" else "EXIT_CODE_MISMATCH")
            break
        if step["stdout_file"] is not None:
            destination = contained(workspace, step["stdout_file"])
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(result["stdout"], encoding="utf-8")
    last = records[-1]
    failures.extend(oracle_failures(workspace, task["oracle"], last["stdout"], last["stderr"]))
    print(json.dumps({"status": "PASS" if not failures else "FAIL", "preparation": preparation, "steps": records, "failures": failures}))


if __name__ == "__main__":
    main()
