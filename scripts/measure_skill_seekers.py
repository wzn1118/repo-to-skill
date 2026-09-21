from __future__ import annotations

import argparse
import json
import subprocess
import time
import uuid
from pathlib import Path

from measurement_identity import write_new
from public_sources import digest, verify_cache

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshots", type=Path, required=True)
    parser.add_argument("--dependencies", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not args.execute:
        print("Preview: Skill Seekers 3.9.0 analyze_codebase, deep defaults, enhance_level=0, offline Docker, five fixed snapshots, 180s each.")
        return
    if args.output.exists():
        raise ValueError("OUTPUT_EXISTS")
    distribution = args.dependencies / "skill_seekers-3.9.0.dist-info"
    if not distribution.is_dir():
        raise ValueError("PINNED_PACKAGE_REQUIRED")
    image = json.loads(subprocess.check_output(["docker", "image", "inspect", args.image]))[0]["Id"]
    if image != args.image:
        raise ValueError("PINNED_IMAGE_REQUIRED")
    worker = ROOT / "scripts/skill_seekers_worker.py"
    hashes = {"worker": digest(worker), "runner": digest(Path(__file__)), "package_record": digest(distribution / "RECORD"), "package_metadata": digest(distribution / "METADATA")}
    records = []
    metadata = json.loads((ROOT / "benchmark/repository-metadata.json").read_text())
    for record in metadata["repositories"]:
        if record["id"] not in {"black", "pre-commit", "prettier", "github-cli", "fzf"}:
            continue
        cached = args.snapshots / f"{record['id']}-{record['commit_sha']}"
        verify_cache(cached, record)
        name = "r2s-baseline-" + uuid.uuid4().hex[:16]
        command = ["docker", "run", "--rm", "--name", name, "--pull=never", "--network=none", "--read-only", "--cap-drop=ALL", "--security-opt=no-new-privileges", "--user=65534:65534", "--cpus=1", "--memory=1024m", "--memory-swap=1024m", "--pids-limit=64", "--tmpfs=/tmp:rw,nosuid,nodev,size=512m", "--env=HOME=/tmp", "--env=PYTHONDONTWRITEBYTECODE=1", "--env=PYTHONPATH=/deps"]
        for source, destination in [(args.dependencies, "/deps"), (cached / "source", "/source"), (worker, "/worker.py")]:
            command.extend(["--mount", f"type=bind,src={source.resolve()},dst={destination},readonly"])
        command.extend([image, "python", "/worker.py"])
        started = time.monotonic()
        measured = {"repository": record["repository"], "commit_sha": record["commit_sha"], "id": record["id"]}
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=180, check=False)
            markers = [line.removeprefix("R2S_RESULT=") for line in result.stdout.splitlines() if line.startswith("R2S_RESULT=")]
            measured.update(json.loads(markers[-1]) if markers else {"status": "GENERATION_FAILED"})
            measured.update(exit_code=result.returncode, stderr=result.stderr[-8000:], stdout_tail=result.stdout[-2000:] if not markers else "result retained")
        except subprocess.TimeoutExpired as error:
            measured.update(status="TIMEOUT", stderr=str(error.stderr or b"")[-2000:])
        finally:
            subprocess.run(["docker", "rm", "--force", name], capture_output=True, timeout=30, check=False)
        measured["elapsed_seconds"] = round(time.monotonic()-started, 3)
        verify_cache(cached, record)
        records.append(measured)
        print(record["id"], measured["status"], flush=True)
    write_new(args.output, {"format": "r2s-competitor-generation-v1", "package": "skill-seekers==3.9.0", "configuration": {"entry": "skill_seekers.cli.codebase_scraper.analyze_codebase", "depth": "deep", "enhance_level": 0, "other_features": "upstream defaults"}, "identities": hashes, "image_id": image, "records": records, "agent_trials": 0, "model_enhanced_status": "NOT_RUN_NO_AUTHORIZED_MODEL_CONFIG", "scope": "Offline generation only, not task success or evidence of superiority. Baseline has a broader codebase-documentation objective and a separately documented resource budget."})


if __name__ == "__main__":
    main()
