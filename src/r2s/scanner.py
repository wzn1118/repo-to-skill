from __future__ import annotations

import hashlib
import os
import stat
from collections import Counter, deque
from dataclasses import asdict, dataclass, replace
from functools import cached_property
from pathlib import Path
from typing import Any

from r2s.contract_types import relative_source_path
from r2s.domain import InventoryEntry, RepositorySnapshot
from r2s.scan_policy import (
    PRIORITY_NAMES,
    SOURCE_SUFFIXES,
    ScanPolicy,
    path_role,
    workspace_for,
    workspace_roots,
)
from r2s.serialization import canonical_json, canonical_sha256

MAX_FILES = 10_000
MAX_FILE_BYTES = 2 * 1024 * 1024
IGNORED_PARTS = {
    ".git", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".snapshots", ".venv",
    "__pycache__", "build", "dist", "node_modules", "run-output", "vendor",
}
SENSITIVE_DIRECTORIES = {".aws", ".gnupg", ".kube", ".ssh"}
SENSITIVE_NAMES = {
    ".env", ".npmrc", ".pypirc", "credentials", "credentials.json",
    "id_dsa", "id_ed25519", "id_rsa", "known_hosts", "netrc",
}


def read_regular(path: Path, limit: int) -> bytes:
    attributes = path.lstat()
    if not stat.S_ISREG(attributes.st_mode):
        raise ValueError("SCAN_SOURCE_NOT_REGULAR")
    if attributes.st_size > limit:
        raise ValueError("SCAN_SOURCE_SIZE_CHANGED")
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0) | getattr(os, "O_NONBLOCK", 0))
    with os.fdopen(descriptor, "rb") as handle:
        opened = os.fstat(handle.fileno())
        if not stat.S_ISREG(opened.st_mode) or (opened.st_dev, opened.st_ino) != (attributes.st_dev, attributes.st_ino):
            raise ValueError("SCAN_SOURCE_CHANGED")
        content = handle.read(limit + 1)
        after = os.fstat(handle.fileno())
    if len(content) > limit or len(content) != opened.st_size or after.st_mtime_ns != opened.st_mtime_ns:
        raise ValueError("SCAN_SOURCE_CHANGED")
    return content


@dataclass(frozen=True)
class ScanResult:
    root: Path
    analyzable_files: tuple[Path, ...]
    inventory: tuple[InventoryEntry, ...]
    tree_sha256: str
    snapshot: RepositorySnapshot
    policy: ScanPolicy

    @cached_property
    def source_index(self) -> dict[Path, InventoryEntry]:
        return {self.root / item.path: item for item in self.inventory if item.classification == "source"}

    def read_text(self, path: Path) -> str:
        entry = self.source_index.get(path)
        if entry is None:
            raise ValueError("ANALYSIS_SOURCE_NOT_SCANNED")
        if path.resolve(strict=True) != path:
            raise ValueError("ANALYSIS_SOURCE_LINK_CHANGED")
        content = read_regular(path, entry.size)
        if hashlib.sha256(content).hexdigest() != entry.content_sha256:
            raise ValueError("ANALYSIS_SOURCE_CHANGED")
        return content.decode("utf-8")


def _is_sensitive(path: str) -> bool:
    name = Path(path).name.lower()
    return name in SENSITIVE_NAMES or name.startswith(".env.")


def _enumerate(root: Path, policy: ScanPolicy, tracked: dict[str, str]) -> tuple[list[tuple[str, int]], list[InventoryEntry]]:
    files: list[tuple[str, int]] = []
    inventory: list[InventoryEntry] = []
    pending = deque([root])
    tracked_directories = {str(parent).replace(os.sep, "/") for name in tracked for parent in Path(name).parents}
    observed = 0
    directories = 0
    while pending:
        current = pending.popleft()
        children = []
        with os.scandir(current) as entries:
            for entry in entries:
                observed += 1
                if observed > policy.max_inventory_entries:
                    raise ValueError("SCAN_INVENTORY_LIMIT_EXCEEDED")
                children.append(entry)
        for child in sorted(children, key=lambda entry: entry.name):
            path = Path(child.path)
            relative = path.relative_to(root).as_posix()
            relative_source_path(relative)
            if len(path.relative_to(root).parts) > policy.max_depth:
                raise ValueError("SCAN_DEPTH_LIMIT_EXCEEDED")
            if child.is_symlink():
                if not path.resolve(strict=False).is_relative_to(root):
                    raise ValueError(f"UNTRUSTED_SYMLINK_ESCAPE: {relative}")
                inventory.append(InventoryEntry(relative, 0, None, "symlink", "SYMLINK_SKIPPED"))
                continue
            if child.is_dir(follow_symlinks=False):
                directories += 1
                if directories > policy.max_directories:
                    raise ValueError("SCAN_DIRECTORY_LIMIT_EXCEEDED")
                if child.name.lower() in SENSITIVE_DIRECTORIES:
                    inventory.append(InventoryEntry(relative, 0, None, "sensitive-directory", "SENSITIVE_DIRECTORY_SKIPPED"))
                elif child.name == ".git":
                    continue
                elif child.name in IGNORED_PARTS and relative not in tracked_directories:
                    inventory.append(InventoryEntry(relative, 0, None, "skipped", "DIRECTORY_POLICY_EXCLUDED"))
                else:
                    pending.append(path)
                continue
            attributes = child.stat(follow_symlinks=False)
            if not stat.S_ISREG(attributes.st_mode):
                raise ValueError(f"UNTRUSTED_SPECIAL_FILE: {relative}")
            files.append((relative, attributes.st_size))
    return files, inventory


def _ordered_files(files: list[tuple[str, int]]) -> list[tuple[str, int, str]]:
    roots = workspace_roots([path for path, _ in files])
    groups: dict[tuple[int, int, str], list[tuple[str, int, str]]] = {}
    for path, size in files:
        owner = workspace_for(path, roots)
        role = {"product": 0, "example": 1, "test": 2}[path_role(path)]
        priority = 0 if Path(path).name in PRIORITY_NAMES else (1 if Path(path).suffix in SOURCE_SUFFIXES else 2)
        groups.setdefault((role, priority, owner), []).append((path, size, owner))
    ordered = []
    for role, priority in sorted({(key[0], key[1]) for key in groups}):
        queues = deque(
            deque(sorted(groups[key])) for key in sorted(groups) if key[:2] == (role, priority)
        )
        while queues:
            queue = queues.popleft()
            ordered.append(queue.popleft())
            if queue:
                queues.append(queue)
    return ordered


def scan(
    root_value: str | Path,
    snapshot: RepositorySnapshot | None = None,
    committed_blob_oids: dict[str, str] | None = None,
    policy: ScanPolicy | None = None,
) -> ScanResult:
    root = Path(root_value).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("SOURCE_NOT_DIRECTORY")
    selected_policy = policy or ScanPolicy(max_files=MAX_FILES, max_file_bytes=MAX_FILE_BYTES)
    tracked = committed_blob_oids or {}
    files, inventory = _enumerate(root, selected_policy, tracked)
    sensitive_digests: dict[str, str] = {}
    file_counts: Counter[str] = Counter()
    byte_counts: Counter[str] = Counter()
    for relative, size, workspace in _ordered_files(files):
        path = root / relative
        role = path_role(relative)
        scopes = [
            ("total", selected_policy.max_files, selected_policy.max_bytes, "SCAN"),
            ("workspace:" + workspace, selected_policy.max_workspace_files, selected_policy.max_workspace_bytes, "WORKSPACE"),
        ]
        if role != "product":
            scopes.append(("role:" + role, selected_policy.max_nonproduct_files, selected_policy.max_nonproduct_bytes, "ROLE"))
        reason = "FILE_TOO_LARGE" if size > selected_policy.max_file_bytes else None
        if reason is None:
            for scope, max_files, max_bytes, prefix in scopes:
                if file_counts[scope] >= max_files:
                    reason = prefix + "_FILE_BUDGET"
                    break
                if byte_counts[scope] + size > max_bytes:
                    reason = prefix + "_BYTE_BUDGET"
                    break
        sensitive = _is_sensitive(relative)
        if reason is not None:
            inventory.append(InventoryEntry(relative, size, None, "sensitive" if sensitive else "skipped", reason))
            continue
        if path.resolve(strict=True) != path:
            raise ValueError("SCAN_SOURCE_LINK_CHANGED")
        content = read_regular(path, selected_policy.max_file_bytes)
        if len(content) != size:
            raise ValueError("SCAN_SOURCE_SIZE_CHANGED")
        for scope, _, _, _ in scopes:
            file_counts[scope] += 1
            byte_counts[scope] += size
        digest = hashlib.sha256(content).hexdigest()
        if sensitive:
            sensitive_digests[relative] = digest
            inventory.append(InventoryEntry(relative, size, None, "sensitive", "SENSITIVE_PATH_SKIPPED"))
            continue
        binary = b"\0" in content[:8192]
        inventory.append(InventoryEntry(
            relative, size, digest, "binary" if binary else "source",
            "BINARY_SKIPPED" if binary else None, tracked.get(relative),
        ))
    inventory.sort(key=lambda item: item.path)
    policy_id = selected_policy.id + ":" + canonical_sha256({
        "ignored": sorted(IGNORED_PARTS), "sensitive_names": sorted(SENSITIVE_NAMES),
        "sensitive_directories": sorted(SENSITIVE_DIRECTORIES),
        "tracked_inventory": bool(tracked),
    })
    rows: list[Any] = [[asdict(item), sensitive_digests.get(item.path)] for item in inventory]
    tree_sha256 = hashlib.sha256(canonical_json({"policy": policy_id, "inventory": rows}).encode()).hexdigest()
    if snapshot is None:
        snapshot = RepositorySnapshot(
            "local-directory", root.name, f"local://{root.name}", None, None,
            tree_sha256, None, scan_policy_id=policy_id,
        )
    else:
        snapshot = replace(snapshot, tree_sha256=tree_sha256, scan_policy_id=policy_id)
    return ScanResult(
        root, tuple(root / item.path for item in inventory if item.classification == "source"),
        tuple(inventory), tree_sha256, snapshot, selected_policy,
    )
