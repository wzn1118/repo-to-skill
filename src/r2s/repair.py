from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from r2s.domain import DiscoveryIR
from r2s.execution import ExecutionPolicy
from r2s.generator import generate
from r2s.serialization import canonical_json, canonical_sha256
from r2s.tasks import TaskSpec, run_task, task_for_bundle
from r2s.workflows import WorkflowRequest


def repair_workflow(discovery: DiscoveryIR, source: Path, task: TaskSpec, initial: WorkflowRequest, output: Path, policy: ExecutionPolicy,
                    candidate: Callable[[dict[str, Any]], WorkflowRequest | None], wheels: Path | None = None, max_attempts: int = 2) -> dict[str, Any]:
    if not 1 <= max_attempts <= 3 or output.exists():
        raise ValueError("REPAIR_BUDGET_OR_OUTPUT_INVALID")
    output.mkdir(parents=True)
    frozen = canonical_sha256({"files": task.files, "oracle": task.oracle.model_dump(), "exit_codes": task.expected_exit_codes, "dependencies": task.python_dependencies})
    workflow = initial
    attempts: list[dict[str, Any]] = []
    for index in range(max_attempts):
        directory = output / f"attempt-{index+1}"
        directory.mkdir()
        try:
            result = generate(discovery, task.id, directory / "build", "portable", workflow=workflow)
            if not result.bundles:
                raise ValueError("REPAIR_NO_BUNDLE")
            bundle = Path(result.bundles[0])
            prepared = task_for_bundle(bundle, task.id, task.files, task.expected_exit_codes, task.oracle, task.python_dependencies)
            prepared = prepared.model_copy(update={"timeout_seconds": task.timeout_seconds, "output_limit": task.output_limit})
            if task.runtime.kind != "python":
                raise ValueError("REPAIR_RUNTIME_PROFILE_NOT_CONFIGURED")
            result_record = run_task(bundle, source, prepared, policy, wheels, execute=True)
        except (ValueError, TypeError, OSError) as error:
            result_record = {"status": "FAIL", "failure_class": "generation_or_binding", "reason": str(error)}
        record = {"attempt": index+1, "workflow": workflow.model_dump(), "frozen_acceptance_sha256": frozen, "result": result_record}
        with (directory / "result.json").open("x", encoding="utf-8") as handle:
            handle.write(canonical_json(record))
        attempts.append(record)
        if result_record["status"] == "PASS" or index+1 == max_attempts:
            break
        replacement = candidate(record)
        if replacement is None:
            break
        if len(replacement.steps) != len(initial.steps) or [step.command for step in replacement.steps] != [step.command for step in initial.steps]:
            raise ValueError("REPAIR_CANNOT_DROP_STEPS_OR_CHANGE_TOOL")
        workflow = replacement
    report = {"format": "r2s-repair-v1", "status": attempts[-1]["result"]["status"], "attempts": attempts, "attempt_budget": max_attempts, "frozen_acceptance_sha256": frozen}
    with (output / "report.json").open("x", encoding="utf-8") as handle:
        handle.write(canonical_json(report))
    return report
