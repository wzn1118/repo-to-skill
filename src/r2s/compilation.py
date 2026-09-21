from __future__ import annotations

from pathlib import Path
from typing import Any

from r2s.compiler_identity import compilation_request
from r2s.discovery_contract import strict_json_loads
from r2s.domain import DiscoveryIR
from r2s.serialization import canonical_json, canonical_sha256, file_sha256
from r2s.workflows import WorkflowRequest

GENERATION_LOCK = "generation.lock.json"
OWNED_NAMES = frozenset({
    "portable", "codex-plugin", "claude", "cursor", "goal.json", "procedures.json",
    "client-profile.lock.json", "generation-scope.json", "validation.json", GENERATION_LOCK,
})


def read_lock(path: Path) -> Any:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 32 * 1024 * 1024:
        raise ValueError("COMPILATION_LOCK_INVALID")
    return strict_json_loads(path.read_bytes())


def check_compiler_lock(
    root: Path, discovery: DiscoveryIR, goal: str, target: str,
    capability_ids: set[str] | None, identity: dict[str, Any],
    workflow: WorkflowRequest | None = None,
) -> dict[str, Any]:
    path = root / "compiler.lock.json"
    parent = root.parent.parent.name if path.exists() or path.is_symlink() else None
    request = compilation_request(discovery, goal, target, capability_ids, identity, parent, workflow)
    if parent is not None:
        expected = {"compiler": identity, "request": request, "request_sha256": canonical_sha256(request)}
        if read_lock(path) != expected:
            raise ValueError("COMPILATION_INPUT_MISMATCH")
    return request


def generation_inventory(root: Path) -> dict[str, str]:
    inventory = {}
    for name in sorted(OWNED_NAMES - {GENERATION_LOCK}):
        parent = root / name
        paths = [parent, *sorted(parent.rglob("*"))] if parent.is_dir() else [parent]
        for path in paths:
            if path.is_symlink():
                raise ValueError("COMPILATION_OUTPUT_SYMLINK")
            if path.exists() and not path.is_dir():
                if not path.is_file():
                    raise ValueError("COMPILATION_OUTPUT_SPECIAL_FILE")
                inventory[path.relative_to(root).as_posix()] = file_sha256(path)
    return inventory


def publish_generation(staging: Path, root: Path, identity: dict[str, Any], request: dict[str, Any]) -> None:
    record = {
        "format": "r2s-generation-v1", "compiler": identity,
        "request": request, "files": generation_inventory(staging),
        "source_authenticity": "not_independently_authenticated",
    }
    lock = root / GENERATION_LOCK
    if lock.exists() or lock.is_symlink():
        if read_lock(lock) != record or generation_inventory(root) != record["files"]:
            raise ValueError("COMPILATION_OUTPUT_MISMATCH")
        return
    if any((root / name).exists() or (root / name).is_symlink() for name in OWNED_NAMES):
        raise ValueError("COMPILATION_OUTPUT_UNMANAGED")
    (staging / GENERATION_LOCK).write_text(canonical_json(record), encoding="utf-8", newline="\n")
    for name in sorted(OWNED_NAMES - {GENERATION_LOCK}):
        source = staging / name
        if source.exists():
            source.rename(root / name)
    (staging / GENERATION_LOCK).rename(lock)
