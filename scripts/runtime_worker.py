from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def main() -> None:
    repository = sys.argv[1]
    root = Path("/tmp/tasks")
    root.mkdir()
    os.chdir(root)
    packages = {"black": ["black"], "pre-commit": ["pre-commit"],
                "poetry": ["poetry"], "yt-dlp": []}
    if packages.get(repository):
        install = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--no-index", "--find-links=/wheels",
             "--target=/tmp/deps", *packages[repository]], capture_output=True, text=True, check=False,
        )
        if install.returncode:
            print(json.dumps({"status": "DEPENDENCY_FAILED", "stderr": install.stderr[-2000:]}))
            return
    environment = dict(os.environ, PYTHONPATH="/source/src:/source:/tmp/deps",
                       PYTHONDONTWRITEBYTECODE="1", HOME="/tmp", XDG_CACHE_HOME="/tmp/cache")
    Path("sample.py").write_text("value=  1\n")
    modules = {"black": "black", "pre-commit": "pre_commit", "yt-dlp": "yt_dlp",
               "poetry": "poetry.console.application"}
    if repository in modules:
        probe = subprocess.run(
            [sys.executable, "-c", ("import importlib.util,sys; "
             "origin=importlib.util.find_spec(sys.argv[1]).origin; "
             "print(origin); assert origin.startswith('/source/')"), modules[repository]],
            env=environment, text=True, capture_output=True, check=False,
        )
        if probe.returncode:
            print(json.dumps({"status": "SOURCE_IMPORT_FAILED", "stderr": probe.stderr[-2000:]}))
            return
    cases = {
        "black": [(["-m", "black", "--code", "value=  1"], 0, "value = 1"),
                  (["-m", "black", "--check", "sample.py"], 1, "would reformat"),
                  (["-m", "black", "--check", "--exclude", "sample.py", "."], 0, "Nothing to do")],
        "pre-commit": [(["-m", "pre_commit", "--help"], 0, "run"),
                       (["-m", "pre_commit", "run", "--help"], 0, "--all-files"),
                       (["-m", "pre_commit", "install", "--help"], 0, "--install-hooks")],
        "poetry": [(["-m", "poetry", "install", "--help"], 0, "--no-root"),
                   (["-m", "poetry", "add", "--help"], 0, "--group"),
                   (["-m", "poetry", "env", "info", "--help"], 0, "--path")],
        "yt-dlp": [(["-m", "yt_dlp", "--version"], 0, "2026"),
                   (["-m", "yt_dlp", "--help"], 0, "--dump-json"),
                   (["-m", "yt_dlp", "--help"], 0, "--output")],
    }
    if repository not in cases:
        print(json.dumps({"status": "BUILD_REQUIRED", "reason": "No source-built executable and dependencies in isolated environment"}))
        return
    results = []
    for arguments, expected_exit, expected_text in cases[repository]:
        command = [sys.executable, *arguments]
        completed = subprocess.run(command, env=environment, capture_output=True, text=True,
                                   timeout=30, check=False)
        combined = completed.stdout + completed.stderr
        results.append({"argv": command, "exit_code": completed.returncode,
                        "expected_exit": expected_exit, "expected_text": expected_text,
                        "passed": completed.returncode == expected_exit and expected_text in combined,
                        "stdout": completed.stdout[:1200], "stderr": completed.stderr[:1200]})
    print(json.dumps({"status": "COMPLETED", "cases": results}))


if __name__ == "__main__":
    main()
