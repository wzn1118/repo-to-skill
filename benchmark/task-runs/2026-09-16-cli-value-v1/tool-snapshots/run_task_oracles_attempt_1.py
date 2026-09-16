from __future__ import annotations

import argparse
import json
import subprocess
import uuid
from pathlib import Path

from measurement_identity import write_new
from public_sources import digest, verify_cache

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshots", type=Path, required=True)
    parser.add_argument("--wheels", type=Path, required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not args.execute:
        print("Preview: install cached binary wheels and run 30 reference solutions in offline, read-only-source Docker containers. Pass --execute.")
        return
    if args.output.exists():
        raise ValueError("ORACLE_OUTPUT_EXISTS")
    task_path = ROOT / "benchmark/tasks/cli-value-v1.json"
    worker = ROOT / "scripts/task_oracle_worker.py"
    taskset = json.loads(task_path.read_text())
    metadata = json.loads((ROOT / "benchmark/repository-metadata.json").read_text())
    image = json.loads(subprocess.check_output(["docker", "image", "inspect", args.image]))[0]["Id"]
    if image != args.image:
        raise ValueError("PINNED_LOCAL_IMAGE_REQUIRED")
    identities = {"taskset_sha256": digest(task_path), "worker_sha256": digest(worker), "runner_sha256": digest(Path(__file__)), "wheel_sha256": {path.name: digest(path) for path in sorted(args.wheels.glob("*.whl"))}}
    repositories = []
    for identifier in ("black", "pre-commit", "cookiecutter"):
        record = next(item for item in metadata["repositories"] if item["id"] == identifier)
        tasks = [task for task in taskset["tasks"] if task["repository_id"] == identifier]
        if len(tasks) != 10 or any(task["commit_sha"] != record["commit_sha"] for task in tasks):
            raise ValueError("TASK_SOURCE_PIN_MISMATCH")
        cached = args.snapshots / f"{identifier}-{record['commit_sha']}"
        verify_cache(cached, record)
        name = "r2s-task-" + uuid.uuid4().hex[:12]
        command = ["docker", "run", "--rm", "--name", name, "--network=none", "--read-only", "--cap-drop=ALL", "--security-opt=no-new-privileges", "--user=65534:65534", "--cpus=1", "--memory=768m", "--pids-limit=64", "--tmpfs=/tmp:rw,exec,nosuid,size=536870912", "--env=PYTHONDONTWRITEBYTECODE=1"]
        for source, destination in [(cached / "source", "/source"), (args.wheels, "/wheels"), (worker, "/worker.py"), (task_path, "/tasks.json")]:
            command += ["--mount", f"type=bind,src={source.resolve()},dst={destination},readonly"]
        command += [image, "python", "/worker.py", identifier]
        try:
            process = subprocess.run(command, capture_output=True, text=True, timeout=300, check=False)
            outcome = json.loads(process.stdout) if process.returncode == 0 else {"status": "CONTAINER_FAILED", "stderr": process.stderr[-2000:], "tasks": []}
        except subprocess.TimeoutExpired:
            outcome = {"status": "TIMEOUT", "tasks": []}
        finally:
            subprocess.run(["docker", "rm", "--force", name], capture_output=True, check=False, timeout=30)
        verify_cache(cached, record)
        repositories.append({"repository": record["repository"], "commit_sha": record["commit_sha"], "source_lock_sha256": digest(cached / "source.lock.json"), **outcome})
        print(identifier, outcome["status"], sum(task["status"] == "PASS" for task in outcome["tasks"]), "/ 10", flush=True)
    current = {"taskset_sha256": digest(task_path), "worker_sha256": digest(worker), "runner_sha256": digest(Path(__file__)), "wheel_sha256": {path.name: digest(path) for path in sorted(args.wheels.glob("*.whl"))}}
    if current != identities:
        raise ValueError("ORACLE_INPUT_CHANGED")
    passed = sum(task["status"] == "PASS" for repo in repositories for task in repo["tasks"])
    write_new(args.output, {"format": "r2s-reference-task-validation-v1", "scope": taskset["scope"], "cohort": taskset["cohort"], "image_id": image, **identities, "tasks_selected": 30, "tasks_passed": passed, "repositories": repositories, "agent_trials": 0, "human_signoffs": 0, "model": None, "skill_uplift": None})


if __name__ == "__main__":
    main()
