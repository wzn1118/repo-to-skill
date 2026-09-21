from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from r2s.generator import generate
from r2s.storage import compilation_root, load_discovery, record_compilation
from r2s.workflows import WorkflowRequest


def build_workflow(discovery_root: Path, goal: str, target: str, workflow: WorkflowRequest | None = None, capability_ids: set[str] | None = None) -> dict[str, Any]:
    discovery = load_discovery(discovery_root)
    root = compilation_root(discovery_root, goal, target, capability_ids, workflow)
    result = generate(discovery, goal, root, target, capability_ids, workflow)
    record_compilation(discovery_root, root, goal, target, result.readiness.value)
    value = asdict(result)
    value["compilation_id"] = root.name
    return value
