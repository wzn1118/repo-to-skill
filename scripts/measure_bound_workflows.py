from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from public_sources import verify_cache

from r2s.analyzers import discover
from r2s.compiler_identity import compiler_identity
from r2s.domain import RepositorySnapshot
from r2s.execution import ExecutionPolicy, _source_files
from r2s.generator import generate
from r2s.serialization import canonical_json, canonical_sha256, file_sha256
from r2s.tasks import TaskOracle, TaskRuntime, dependency_inventory, run_task, task_for_bundle
from r2s.workflows import WorkflowRequest

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshots", type=Path, required=True)
    parser.add_argument("--wheels", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--cross-language", type=Path)
    parser.add_argument("--node", type=Path)
    parser.add_argument("--node-dependencies", type=Path)
    parser.add_argument("--fzf-binary", type=Path)
    parser.add_argument("--fzf-build-report", type=Path)
    parser.add_argument("--gh-binary", type=Path)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not args.execute:
        print("Preview: compile and execute the 20 frozen Black/pre-commit tasks with bound inputs and unchanged v2 oracles.")
        return
    if args.output.exists() or args.work.exists():
        raise ValueError("MEASUREMENT_OUTPUT_EXISTS")
    args.work.mkdir(parents=True)
    identity = compiler_identity("portable")
    taskset = json.loads((ROOT / "benchmark/tasks/cli-value-v2.json").read_text())
    metadata = json.loads((ROOT / "benchmark/repository-metadata.json").read_text())
    records = []
    extras = json.loads(args.cross_language.read_text()) if args.cross_language else {"tasks": []}
    runner_sha256 = file_sha256(Path(__file__))
    for tool in ("black", "pre-commit", *(["prettier", "fzf", "github-cli"] if extras["tasks"] else [])):
        record = next(item for item in metadata["repositories"] if item["id"] == tool)
        cached = args.snapshots / f"{tool}-{record['commit_sha']}"
        verify_cache(cached, record)
        snapshot = RepositorySnapshot("github-archive", tool, f"github://{record['repository']}", record["commit_sha"], record["commit_sha"], "", False, git_object_format="sha1")
        discovery = discover(cached / "source", snapshot)
        selected = [task for task in (taskset["tasks"] if tool in {"black", "pre-commit"} else extras["tasks"]) if task["repository_id"] == tool]
        for reference in selected:
            started = time.monotonic()
            output = args.work / reference["id"]
            output.mkdir()
            result = {"id": reference["id"], "repository": record["repository"], "commit_sha": record["commit_sha"], "reference_sha256": canonical_sha256(reference), "status": "NOT_RUN"}
            try:
                steps = []
                for reference_step in reference.get("steps", []):
                    argv = list(reference_step["argv"])
                    path = [argv.pop(0)] if tool == "pre-commit" else []
                    parameters = {}
                    positional = []
                    while argv:
                        value = argv.pop(0)
                        if value.startswith("--"):
                            claim = next(item for item in discovery.claims if item.predicate == "supports_option" and item.object.get("command") == tool and item.object.get("option") == value and list(item.object.get("command_path", ())) == path)
                            shape = claim.object.get("shape", {})
                            arity = shape.get("arity") if isinstance(shape, dict) else None
                            if arity not in {0, 1}:
                                raise ValueError("REFERENCE_BINDING_ARITY_UNSUPPORTED")
                            parameters[value] = [argv.pop(0)] if arity == 1 else []
                        else:
                            positional.append(value)
                    if positional:
                        parameters["src" if tool == "black" else "filenames"] = positional
                    steps.append({"command": tool, "path": path, "parameters": parameters,
                                  "expected_observation": "Match the independently frozen task oracle", "stdout_file": reference_step.get("stdout_file")})
                workflow = WorkflowRequest.model_validate(reference.get("workflow", {"title": reference["id"], "steps": steps}))
                build = generate(discovery, reference.get("goal", workflow.title), output / "build", "portable", workflow=workflow)
                if not build.bundles:
                    raise ValueError("WORKFLOW_NOT_GENERATED")
                bundle = Path(build.bundles[0])
                oracle = TaskOracle.model_validate(reference["oracle"])
                exits = reference.get("exits", [step["expected_exit"] for step in reference.get("steps", [])])
                dependencies = ["black==26.5.1"] if tool == "black" else ["pre-commit==4.6.2"] if tool == "pre-commit" else []
                task = task_for_bundle(bundle, reference["id"], reference["files"], exits, oracle, dependencies)
                executable = None
                node_dependencies = None
                if tool in {"prettier", "fzf", "github-cli"}:
                    executable = args.node if tool == "prettier" else args.fzf_binary if tool == "fzf" else args.gh_binary
                    if executable is None:
                        raise ValueError("RUNTIME_EXECUTABLE_NOT_PREPARED")
                    if tool == "fzf":
                        build_records = json.loads(args.fzf_build_report.read_text()) if args.fzf_build_report else {}
                        if not any(item.get("id") == "fzf" and item.get("commit_sha") == record["commit_sha"] and item.get("binary_sha256") == file_sha256(executable) for item in build_records.get("repositories", [])):
                            raise ValueError("RUNTIME_BUILD_RECEIPT_MISMATCH")
                    node_dependencies = args.node_dependencies if tool == "prettier" else None
                    runtime = TaskRuntime(kind="node" if tool == "prettier" else "native", executable_sha256=file_sha256(executable), build_source_sha256=canonical_sha256(_source_files(cached / "source")), dependency_files_sha256=canonical_sha256(dependency_inventory(node_dependencies)) if node_dependencies else None)
                    task = task.model_copy(update={"runtime": runtime})
                measured = run_task(bundle, cached / "source", task, ExecutionPolicy(args.image), args.wheels, True, executable, node_dependencies)
                (output / "task.json").write_text(canonical_json(task.model_dump()))
                (output / "result.json").write_text(canonical_json(measured))
                result.update(status=measured["status"], task_result=measured, workflow=workflow.model_dump(), skill_bytes=(bundle / "SKILL.md").stat().st_size)
            except (ValueError, TypeError, OSError, StopIteration, IndexError) as error:
                reason = str(error)[:1000]
                result.update(status="FAIL", failure_class="environment_preparation" if reason.startswith("RUNTIME_") else "binding_or_generation", reason=reason)
            result["elapsed_seconds"] = round(time.monotonic()-started, 3)
            records.append(result)
            print(reference["id"], result["status"], result.get("reason", ""), flush=True)
        verify_cache(cached, record)
    if compiler_identity("portable") != identity or file_sha256(Path(__file__)) != runner_sha256:
        raise ValueError("COMPILER_CHANGED_DURING_MEASUREMENT")
    report = {"format": "r2s-bound-workflow-measurement-v1", "scope": "Agent-authored structured inputs compiled into Skills, then generated argv executed against fixed source. No goal-understanding or Agent uplift measurement.", "compiler_sha256": identity["sha256"], "compiler": identity, "runner_sha256": runner_sha256, "cross_language_taskset_sha256": canonical_sha256(extras), "source_taskset_sha256": canonical_sha256(taskset), "selected": len(records), "passed": sum(item["status"] == "PASS" for item in records), "agent_trials": 0, "records": records}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        handle.write(canonical_json(report))
    print("completed", report["passed"], "/", report["selected"])


if __name__ == "__main__":
    sys.exit(main())
