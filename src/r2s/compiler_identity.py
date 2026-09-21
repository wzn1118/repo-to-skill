from __future__ import annotations

import platform
import sys
from dataclasses import asdict
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from r2s.client_profiles import CLIENT_PROFILES
from r2s.domain import DiscoveryIR
from r2s.serialization import canonical_sha256, file_sha256
from r2s.workflows import WorkflowRequest


def compiler_identity(target: str) -> dict[str, Any]:
    profile = CLIENT_PROFILES.get(target)
    if profile is None:
        raise ValueError("CLIENT_PROFILE_UNKNOWN")
    package_root = Path(__file__).parent
    files = {
        path.relative_to(package_root).as_posix(): file_sha256(path)
        for path in sorted(package_root.rglob("*"))
        if path.is_file() and path.suffix in {".py", ".j2", ".jinja2", ".json", ".yaml", ".html", ".js", ".css"}
        and "__pycache__" not in path.parts
    }
    parsers: dict[str, str | None] = {}
    for name in ("tree-sitter", "tree-sitter-javascript", "tree-sitter-typescript", "tree-sitter-go"):
        try:
            parsers[name] = version(name)
        except PackageNotFoundError:
            parsers[name] = None
    payload = {
        "format": "r2s-compiler-identity-v1",
        "files": files,
        "dependencies": {name: version(name) for name in ("pydantic", "pydantic-core", "PyYAML", "jinja2")},
        "runtime": {"python": platform.python_version(), "implementation": sys.implementation.name, "platform": sys.platform},
        "profile": asdict(profile),
        "discovery_boundary": "bound-workflows-1.5",
        "optional_parsers": parsers,
    }
    return {**payload, "sha256": canonical_sha256(payload)}


def compilation_request(
    discovery: DiscoveryIR, goal: str, target: str, capability_ids: set[str] | None,
    identity: dict[str, Any], parent_run_id: str | None,
    workflow: WorkflowRequest | None = None,
) -> dict[str, Any]:
    if capability_ids is not None and capability_ids - {item.id for item in discovery.capabilities}:
        raise ValueError("COMPILATION_CAPABILITY_UNKNOWN")
    return {
        "parent_run_id": parent_run_id,
        "discovery_sha256": canonical_sha256(discovery.to_dict()),
        "goal": " ".join(goal.split()),
        "target": target,
        "scope": "full" if capability_ids is None else "capability_delta",
        "capability_ids": sorted(capability_ids or ()),
        "compiler_sha256": identity["sha256"],
        "workflow": workflow.model_dump(mode="json") if workflow is not None else None,
    }
