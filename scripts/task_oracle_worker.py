from __future__ import annotations

import importlib.metadata
import json
import os
import subprocess
import sys
from pathlib import Path


def contained(root: Path, relative: str) -> Path:
    if not relative or relative.startswith("/") or "\\" in relative or ":" in relative or any(part in {"", ".", ".."} for part in relative.split("/")):
        raise ValueError("TASK_PATH_INVALID")
    target = root / relative
    if not target.resolve().is_relative_to(root.resolve()):
        raise ValueError("TASK_PATH_ESCAPE")
    return target


def oracle_failures(root: Path, oracle: dict, stdout: str, stderr: str) -> list[str]:
    if set(oracle) - {"files_exact", "files_contains", "absent", "stdout_exact", "stdout_contains", "stderr_contains"}:
        raise ValueError("UNKNOWN_ORACLE")
    failures = []
    for kind in ("files_exact", "files_contains"):
        for name, expected in oracle.get(kind, {}).items():
            path = contained(root, name)
            if path.is_symlink() or not path.is_file() or path.stat().st_size > 1_000_000:
                failures.append(f"{kind}:{name}:missing_or_unsafe")
                continue
            actual = path.read_text(encoding="utf-8")
            if (actual != expected if kind == "files_exact" else expected not in actual):
                failures.append(f"{kind}:{name}:mismatch")
    for name in oracle.get("absent", []):
        if contained(root, name).exists():
            failures.append(f"absent:{name}")
    for key, actual in [("stdout_exact", stdout), ("stdout_contains", stdout), ("stderr_contains", stderr)]:
        if key in oracle and (actual != oracle[key] if key.endswith("exact") else oracle[key] not in actual):
            failures.append(key)
    return failures


def run_task(task: dict, module: str, environment: dict[str, str]) -> dict:
    root = Path("/tmp/tasks") / task["id"]
    root.mkdir(parents=True)
    for name, content in task["files"].items():
        path = contained(root, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
    records = []
    failures = []
    stdout = stderr = ""
    for step in task["steps"]:
        argv = [sys.executable, "-m", module, *step["argv"]]
        try:
            result = subprocess.run(argv, cwd=root, env=environment, capture_output=True, text=True, timeout=20, check=False)
            stdout, stderr = result.stdout, result.stderr
            passed = result.returncode == step["expected_exit"]
            records.append({"argv": argv, "exit_code": result.returncode, "expected_exit": step["expected_exit"], "passed": passed, "stdout": stdout[:2000], "stderr": stderr[:2000]})
            if not passed:
                failures.append("exit_code")
                break
            if "stdout_file" in step:
                path = contained(root, step["stdout_file"])
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(stdout, encoding="utf-8")
        except subprocess.TimeoutExpired:
            failures.append("timeout")
            break
    failures.extend(oracle_failures(root, task["oracle"], stdout, stderr))
    return {"id": task["id"], "status": "PASS" if not failures else "FAIL", "failures": failures, "steps": records}


def main() -> None:
    identifier = sys.argv[1]
    modules = {"black": "black", "pre-commit": "pre_commit", "cookiecutter": "cookiecutter"}
    package = {"black": "black==26.5.1", "pre-commit": "pre-commit==4.6.2", "cookiecutter": "cookiecutter==2.6.0"}[identifier]
    install = subprocess.run([sys.executable, "-m", "pip", "install", "--no-index", "--find-links=/wheels", "--only-binary=:all:", "--target=/tmp/deps", package], capture_output=True, text=True, timeout=60, check=False)
    if install.returncode:
        print(json.dumps({"status": "DEPENDENCY_FAILED", "stderr": install.stderr[-2000:], "tasks": []}))
        return
    environment = dict(os.environ, PYTHONPATH="/source/src:/source:/tmp/deps", PYTHONDONTWRITEBYTECODE="1", HOME="/tmp/home", XDG_CACHE_HOME="/tmp/cache", PRE_COMMIT_HOME="/tmp/pre-commit", GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL="/dev/null")
    Path(environment["HOME"]).mkdir()
    module = modules[identifier]
    probe = subprocess.run([sys.executable, "-c", "import importlib.util,sys; path=importlib.util.find_spec(sys.argv[1]).origin; print(path); assert path.startswith('/source/')", module], env=environment, capture_output=True, text=True, check=False)
    if probe.returncode:
        print(json.dumps({"status": "SOURCE_IMPORT_FAILED", "stderr": probe.stderr[-2000:], "tasks": []}))
        return
    taskset = json.loads(Path("/tasks.json").read_text())
    tasks = [run_task(task, module, environment) for task in taskset["tasks"] if task["repository_id"] == identifier]
    dependencies = {item.metadata["Name"]: item.version for item in importlib.metadata.distributions(path=["/tmp/deps"])}
    print(json.dumps({"status": "COMPLETED", "source_module_origin": probe.stdout.strip(), "dependencies": dependencies, "tasks": tasks}))


if __name__ == "__main__":
    main()
