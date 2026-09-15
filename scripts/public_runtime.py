from __future__ import annotations

import argparse
import json
import subprocess
import uuid
from pathlib import Path

from public_sources import digest, write_json

ROOT = Path(__file__).resolve().parents[1]


def docker_arguments(image: str, name: str, source: Path, wheels: Path) -> list[str]:
    return ["docker", "run", "--rm", "--name", name, "--network=none", "--read-only",
            "--cap-drop=ALL", "--security-opt=no-new-privileges", "--user=65534:65534",
            "--cpus=1", "--memory=768m", "--pids-limit=64", "--tmpfs=/tmp:rw,exec,nosuid,size=536870912",
            "--mount", f"type=bind,src={source.resolve()},dst=/source,readonly",
            "--mount", f"type=bind,src={wheels.resolve()},dst=/wheels,readonly",
            "--mount", f"type=bind,src={ROOT / 'scripts/runtime_worker.py'},dst=/harness.py,readonly",
            "--env=PYTHONDONTWRITEBYTECODE=1", image, "python", "/harness.py"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not args.execute:
        print("Preview: run pinned source in read-only, no-network containers. Pass --execute.")
        return
    image = json.loads(subprocess.check_output(["docker", "image", "inspect", args.image]))[0]["Id"]
    metadata = json.loads((ROOT / "benchmark/repository-metadata.json").read_text())
    results = []
    for record in metadata["repositories"]:
        if not record.get("ground_truth"):
            continue
        source = args.work / "snapshots" / f"{record['id']}-{record['commit_sha']}" / "source"
        name = "r2s-smoke-" + uuid.uuid4().hex[:12]
        command = docker_arguments(image, name, source, args.work / "wheels") + [record["id"]]
        result = {"id": record["id"], "commit_sha": record["commit_sha"], "image_id": image}
        try:
            completed = subprocess.run(command, capture_output=True, text=True, timeout=120, check=False)
            result.update({"exit_code": completed.returncode, "stderr": completed.stderr[-2000:]})
            if completed.returncode:
                result["status"] = "RUNTIME_FAILED"
            else:
                result.update(json.loads(completed.stdout))
        except subprocess.TimeoutExpired:
            subprocess.run(["docker", "rm", "--force", name], capture_output=True, check=False)
            result["status"] = "TIMEOUT"
        results.append(result)
        print(record["id"], result["status"], flush=True)
    write_json(ROOT / "benchmark/runtime-results.json", {
        "method": "Source invocation smoke checks; help/version checks are not end-to-end user tasks or with/without-skill evals",
        "policy": {"network": "none", "source": "read-only", "user": "65534", "cpus": 1,
                   "memory_mb": 768, "pids": 64, "timeout_seconds": 120},
        "wheel_sha256": {path.name: digest(path) for path in sorted((args.work / "wheels").glob("*.whl"))},
        "repositories": results})


if __name__ == "__main__":
    main()
