from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from measurement_identity import write_new
from public_sources import fetch, verify_cache

from r2s.analyzers import discover
from r2s.compiler_identity import compiler_identity
from r2s.domain import RepositorySnapshot
from r2s.drift import compare_discoveries
from r2s.execution import ExecutionPolicy
from r2s.generator import generate
from r2s.serialization import canonical_sha256, file_sha256
from r2s.tasks import TaskOracle, run_task, task_for_bundle
from r2s.workflows import WorkflowRequest

ROOT = Path(__file__).resolve().parents[1]
PREVIOUS = {"black": "87928e6d6761a4a6d22250e1fee5601b3998086e", "pre-commit": "8a0630ca1aa7f6d5665effe674ebe2022af17919"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshots", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--wheels", type=Path, required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not args.execute:
        print("Preview: fetch two older pinned public commits; replay unchanged task inputs/oracles on old and corpus commits in offline Docker.")
        return
    if args.output.exists() or args.work.exists():
        raise ValueError("UPDATE_EXPERIMENT_OUTPUT_EXISTS")
    args.work.mkdir(parents=True)
    identity = compiler_identity("portable")
    metadata = json.loads((ROOT / "benchmark/repository-metadata.json").read_text())
    taskset = json.loads((ROOT / "benchmark/tasks/cli-value-v2.json").read_text())
    outcomes = []
    for identifier, previous_sha in PREVIOUS.items():
        record = next(item for item in metadata["repositories"] if item["id"] == identifier)
        selected = next(item for item in taskset["tasks"] if item["repository_id"] == identifier)
        parameters = {"--code": [selected["steps"][0]["argv"][1]]} if identifier == "black" else {"filenames": [selected["steps"][0]["argv"][-1]]}
        workflow = WorkflowRequest.model_validate({"title": selected["id"], "steps": [{"command": identifier, "path": [] if identifier == "black" else [selected["steps"][0]["argv"][0]], "parameters": parameters, "expected_observation": "Match the same frozen output oracle on both source versions"}]})
        versions = []
        discoveries = []
        for label, commit in [("previous", previous_sha), ("corpus", record["commit_sha"])]:
            version = {**record, "commit_sha": commit}
            source, _lock = fetch(version, args.snapshots)
            snapshot = RepositorySnapshot("github-archive", identifier, f"github://{record['repository']}", commit, commit, "", False, git_object_format="sha1")
            discovery = discover(source, snapshot)
            discoveries.append(discovery)
            build = generate(discovery, workflow.title, args.work / identifier / label, "portable", workflow=workflow)
            measured = {"status": "BINDING_FAILED"}
            if build.bundles:
                bundle = Path(build.bundles[0])
                task = task_for_bundle(bundle, selected["id"], selected["files"], [step["expected_exit"] for step in selected["steps"]], TaskOracle.model_validate(selected["oracle"]), ["black==26.5.1" if identifier == "black" else "pre-commit==4.6.2"])
                measured = run_task(bundle, source, task, ExecutionPolicy(args.image), args.wheels, True)
            versions.append({"commit_sha": commit, "version": label, "result": measured})
            verify_cache(source.parent, version)
        drift = compare_discoveries(*discoveries, "previous", "corpus")
        outcomes.append({"repository": record["repository"], "task_id": selected["id"], "task_input_sha256": canonical_sha256(selected), "workflow": workflow.model_dump(), "versions": versions, "drift": asdict(drift)})
        print(identifier, [item["result"]["status"] for item in versions], flush=True)
    if identity != compiler_identity("portable"):
        raise ValueError("UPDATE_EXPERIMENT_COMPILER_CHANGED")
    write_new(args.output, {"format": "r2s-real-upstream-update-v1", "compiler": identity, "runner_sha256": file_sha256(Path(__file__)), "records": outcomes, "scope": "Two real upstream versions per tool, same structured input and independent oracle. Conservative capability rebuild accounting, not validated minimal invalidation or a native-client update. No repair success is claimed if no failing call was observed."})


if __name__ == "__main__":
    main()
