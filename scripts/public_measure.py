from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from public_sources import digest, fetch, verify_cache, write_json

ROOT = Path(__file__).resolve().parents[1]


def worker(record: dict, source: Path, output: Path) -> dict:
    sys.path.insert(0, str(ROOT / "src"))
    from r2s.core import discover
    from r2s.domain import RepositorySnapshot
    from r2s.generator import generate

    started = time.monotonic()
    snapshot = RepositorySnapshot(
        "github-archive", record["id"], f"github://{record['repository']}",
        record["commit_sha"], record["commit_sha"], "", False, git_object_format="sha1",
    )
    result = {"repository": record["repository"], "commit_sha": record["commit_sha"],
              "attempted": True, "completed": False, "bundles": 0}
    try:
        discovery = discover(source, snapshot)
        write_json(output / "discovery.json", discovery.to_dict())
        build = generate(discovery, "Use the discovered commands", output, "portable")
        emitted = set()
        bundle_files = []
        for bundle in build.bundles:
            provenance = json.loads((Path(bundle) / "PROVENANCE.json").read_text())
            emitted.update(claim["id"] for claim in provenance["claims"] if claim["executable_fact"])
            for path in Path(bundle).rglob("*"):
                if path.is_file():
                    bundle_files.append({"path": path.relative_to(output).as_posix(),
                                         "bytes": path.stat().st_size, "sha256": digest(path)})
        evidence = {item.id: item for item in discovery.evidence}
        facts = []
        for claim in discovery.claims:
            if not claim.executable_fact:
                continue
            sources = []
            for evidence_id in claim.evidence_ids:
                item = evidence.get(evidence_id)
                if item is None:
                    continue
                location = asdict(item.source)
                location.update({"extractor": item.extractor, "confidence": item.confidence})
                path = source / item.source.path
                location["verified_hash_and_pin"] = (
                    path.is_file() and digest(path) == item.source.content_sha256
                    and item.source.commit_sha == record["commit_sha"]
                )
                sources.append(location)
            facts.append({"id": claim.id, "subject": claim.subject,
                          "predicate": claim.predicate, "value": claim.object,
                          "status": claim.status, "emitted": claim.id in emitted,
                          "sources": sources,
                          "provenance_valid": bool(sources) and len(sources) == len(claim.evidence_ids)
                          and all(item["verified_hash_and_pin"] for item in sources)})
        result.update({"completed": True, "status": build.readiness.value,
                       "languages_detected": discovery.languages,
                       "repository_types": discovery.repository_types,
                       "files_scanned": len(discovery.inventory),
                       "capabilities": len(discovery.capabilities),
                       "bundles": len(build.bundles), "bundle_files": bundle_files,
                       "findings": [asdict(item) for item in build.findings], "facts": facts,
                       "tree_sha256": discovery.tree_sha256})
    except (ValueError, OSError, UnicodeError, TypeError, KeyError, RecursionError) as error:
        reason = str(error).replace(str(source), "<source>")[:400]
        result.update({"status": "REVIEW_REQUIRED", "failure_class": type(error).__name__,
                       "reason": reason})
    result["elapsed_seconds"] = round(time.monotonic() - started, 3)
    write_json(output / "result.json", result)
    return result


def measure(record: dict, work: Path, timeout: int) -> dict:
    output = work / "artifacts" / record["id"]
    output.mkdir(parents=True, exist_ok=True)
    base = {key: record[key] for key in (
        "id", "repository", "commit_sha", "stars_at_benchmark", "tier", "set", "language", "license"
    )}
    try:
        source, lock = fetch(record, work / "snapshots")
    except (OSError, ValueError, KeyError) as error:
        return dict(base, status="FETCH_ERROR", completed=False, attempted=False,
                    failure_class=type(error).__name__)
    base["archive"] = {"sha256": lock["archive_sha256"], "files": len(lock["files"]),
                       "skipped_links": lock["skipped"], "expanded_bytes": lock["expanded_bytes"],
                       "identity_method": lock.get("identity_method", "HTTPS archive addressed by commit SHA"),
                       "restored_files": lock.get("restored_files", [])}
    record_path = output / "input.json"
    write_json(record_path, base)
    command = [sys.executable, str(Path(__file__).resolve()), "worker",
               "--record", str(record_path), "--source", str(source), "--output", str(output)]
    environment = {key: value for key, value in os.environ.items()
                   if key in {"PATH", "SYSTEMROOT", "WINDIR"}}
    environment.update({"TMPDIR": str(work / "tmp"), "PYTHONHASHSEED": "0"})
    try:
        with (output / "worker.log").open("w") as log:
            completed = subprocess.run(command, cwd=ROOT, env=environment, stdout=log,
                                       stderr=subprocess.STDOUT, timeout=timeout, check=False)
        if completed.returncode:
            return dict(base, status="REVIEW_REQUIRED", completed=False, attempted=True,
                        failure_class="WORKER_ERROR", exit_code=completed.returncode)
    except subprocess.TimeoutExpired:
        return dict(base, status="REVIEW_REQUIRED", completed=False, attempted=True,
                    failure_class="ANALYSIS_TIMEOUT", timeout_seconds=timeout)
    result = json.loads((output / "result.json").read_text())
    verify_cache(source.parent, record)
    base.update(result)
    base["analyzer_version"] = "unchanged compiler; benchmark runner v2"
    return base


def summary(records: list[dict]) -> dict:
    core = [item for item in records if item["set"] == "core"]
    completed = [item for item in core if item.get("completed")]
    attempted = [item for item in core if item.get("attempted")]
    ready = [item for item in completed if item["status"] == "STATIC_READY"]
    stars = sum(item["stars_at_benchmark"] for item in core)
    covered = sum(item["stars_at_benchmark"] for item in ready)
    emitted = [fact for item in core for fact in item.get("facts", []) if fact["emitted"]]
    return {"high_star_public_repositories_tested": len(attempted),
            "high_star_completed": len(completed), "high_star_selected": len(core),
            "total_benchmark_stars": stars, "static_ready": len(ready),
            "star_weighted_repository_coverage": covered / stars if stars else None,
            "repository_static_generation_rate": len(ready) / len(core) if core else None,
            "emitted_executable_facts": len(emitted),
            "hash_and_pin_verified_facts": sum(item["provenance_valid"] for item in emitted),
            "sets": {group: dict(Counter(item["status"] for item in records if item["set"] == group))
                     for group in ("core", "unsupported-challenge", "edge")}}


def run(metadata: Path, work: Path, output: Path, timeout: int) -> None:
    if tuple(sys.version_info[:2]) < (3, 12):
        raise SystemExit("Public measurements require Python >= 3.12; no TOML bootstrap fallback.")
    work = work.resolve()
    (work / "tmp").mkdir(parents=True, exist_ok=True)
    snapshot = json.loads(metadata.read_text())
    records = []
    started = datetime.now(UTC).isoformat()
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {pool.submit(measure, item, work, timeout): item for item in snapshot["repositories"]}
        for future in as_completed(futures):
            result = future.result()
            records.append(result)
            print(result["id"], result["status"], result.get("bundles", 0), flush=True)
            write_json(work / "progress.json", records)
    positions = {item["id"]: index for index, item in enumerate(snapshot["repositories"])}
    records.sort(key=lambda item: positions[item["id"]])
    code = {path.relative_to(ROOT).as_posix(): digest(path)
            for path in sorted((ROOT / "src" / "r2s").glob("*.py"))}
    write_json(output, {"schema_version": 2, "started_at": started,
                        "finished_at": datetime.now(UTC).isoformat(),
                        "python": platform.python_version(), "platform": platform.platform(),
                        "metadata_sha256": digest(metadata), "compiler_files": code,
                        "compiler_sha256": hashlib.sha256(json.dumps(code, sort_keys=True).encode()).hexdigest(),
                        "method": "Unmodified compiler: pinned source -> discover -> generate -> validate; no target code execution",
                        "summary": summary(records), "repositories": records})


def collect(metadata: Path, work: Path, output: Path) -> None:
    snapshot = json.loads(metadata.read_text())
    records = []
    for record in snapshot["repositories"]:
        artifact = work / "artifacts" / record["id"]
        value = json.loads((artifact / "input.json").read_text())
        value.update(json.loads((artifact / "result.json").read_text()))
        if value["commit_sha"] != record["commit_sha"]:
            raise ValueError("RESULT_PIN_MISMATCH")
        records.append(value)
    code = {path.relative_to(ROOT).as_posix(): digest(path)
            for path in sorted((ROOT / "src" / "r2s").glob("*.py"))}
    write_json(output, {"schema_version": 2, "finished_at": datetime.now(UTC).isoformat(),
                        "python": platform.python_version(), "platform": platform.platform(),
                        "metadata_sha256": digest(metadata), "compiler_files": code,
                        "compiler_sha256": hashlib.sha256(json.dumps(code, sort_keys=True).encode()).hexdigest(),
                        "method": "Unmodified compiler: pinned source -> discover -> generate -> validate; no target code execution",
                        "summary": summary(records), "repositories": records})


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    batch = sub.add_parser("run")
    batch.add_argument("--metadata", type=Path, default=ROOT / "benchmark/repository-metadata.json")
    batch.add_argument("--work", type=Path, required=True)
    batch.add_argument("--output", type=Path, default=ROOT / "benchmark/results.json")
    batch.add_argument("--timeout", type=int, default=180)
    gather = sub.add_parser("collect")
    gather.add_argument("--metadata", type=Path, default=ROOT / "benchmark/repository-metadata.json")
    gather.add_argument("--work", type=Path, required=True)
    gather.add_argument("--output", type=Path, default=ROOT / "benchmark/results.json")
    child = sub.add_parser("worker")
    child.add_argument("--record", type=Path, required=True)
    child.add_argument("--source", type=Path, required=True)
    child.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "worker":
        worker(json.loads(args.record.read_text()), args.source, args.output)
    elif args.command == "collect":
        collect(args.metadata, args.work, args.output)
    else:
        run(args.metadata, args.work, args.output, args.timeout)


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    main()
