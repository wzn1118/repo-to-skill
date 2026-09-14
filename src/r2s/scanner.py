from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, replace
from pathlib import Path

from r2s.domain import InventoryEntry, RepositorySnapshot
from r2s.serialization import canonical_json, file_sha256

MAX_FILES = 10_000
MAX_FILE_BYTES = 2 * 1024 * 1024
IGNORED_PARTS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".snapshots",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "run-output",
    "vendor",
}
SENSITIVE_DIRECTORIES = {".aws", ".gnupg", ".kube", ".ssh"}
SENSITIVE_NAMES = {
    ".env",
    ".npmrc",
    ".pypirc",
    "credentials",
    "credentials.json",
    "id_dsa",
    "id_ed25519",
    "id_rsa",
    "known_hosts",
    "netrc",
}


@dataclass(frozen=True)
class ScanResult:
    root: Path
    analyzable_files: tuple[Path, ...]
    inventory: tuple[InventoryEntry, ...]
    tree_sha256: str
    snapshot: RepositorySnapshot


def _is_binary(path: Path) -> bool:
    with path.open("rb") as handle:
        sample = handle.read(8192)
    return b"\0" in sample


def _git_blob_sha(path: Path, object_format: str) -> str:
    content = path.read_bytes()
    header = f"blob {len(content)}\0".encode()
    return hashlib.new(object_format, header + content).hexdigest()


def _is_sensitive(relative: Path) -> bool:
    name = relative.name.lower()
    return name in SENSITIVE_NAMES or name.startswith(".env.")


def scan(
    root_value: str | Path,
    snapshot: RepositorySnapshot | None = None,
) -> ScanResult:
    root = Path(root_value).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("SOURCE_NOT_DIRECTORY")
    analyzable: list[Path] = []
    inventory: list[InventoryEntry] = []
    sensitive_digests: dict[str, str] = {}
    observed_files = 0
    for current, directories, names in os.walk(root, followlinks=False):
        retained_directories: list[str] = []
        for directory in sorted(directories):
            directory_path = Path(current) / directory
            relative_directory = directory_path.relative_to(root).as_posix()
            if directory.lower() in SENSITIVE_DIRECTORIES:
                inventory.append(
                    InventoryEntry(
                        relative_directory,
                        0,
                        None,
                        "sensitive-directory",
                        "SENSITIVE_DIRECTORY_SKIPPED",
                    )
                )
                continue
            if directory in IGNORED_PARTS:
                continue
            if directory_path.is_symlink():
                target = directory_path.resolve(strict=False)
                try:
                    target.relative_to(root)
                except ValueError as exc:
                    raise ValueError(
                        f"UNTRUSTED_SYMLINK_ESCAPE: {relative_directory}"
                    ) from exc
                inventory.append(
                    InventoryEntry(
                        relative_directory,
                        0,
                        None,
                        "symlink",
                        "SYMLINK_DIRECTORY_SKIPPED",
                    )
                )
                continue
            retained_directories.append(directory)
        directories[:] = retained_directories
        for name in sorted(names):
            observed_files += 1
            if observed_files > MAX_FILES:
                raise ValueError("FILE_COUNT_LIMIT_EXCEEDED")
            path = Path(current) / name
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                target = path.resolve(strict=False)
                try:
                    target.relative_to(root)
                except ValueError as exc:
                    raise ValueError(f"UNTRUSTED_SYMLINK_ESCAPE: {relative}") from exc
                inventory.append(InventoryEntry(relative, 0, None, "symlink", "SYMLINK_SKIPPED"))
                continue
            size = path.stat().st_size
            if _is_sensitive(path.relative_to(root)):
                sensitive_digests[relative] = file_sha256(path)
                inventory.append(
                    InventoryEntry(
                        relative,
                        size,
                        None,
                        "sensitive",
                        "SENSITIVE_PATH_SKIPPED",
                    )
                )
                continue
            if size > MAX_FILE_BYTES:
                inventory.append(InventoryEntry(relative, size, None, "skipped", "FILE_TOO_LARGE"))
                continue
            content_hash = file_sha256(path)
            blob_sha = (
                _git_blob_sha(path, snapshot.git_object_format)
                if snapshot is not None and snapshot.git_object_format is not None
                else None
            )
            if _is_binary(path):
                inventory.append(
                    InventoryEntry(
                        relative,
                        size,
                        content_hash,
                        "binary",
                        "BINARY_SKIPPED",
                        blob_sha,
                    )
                )
                continue
            analyzable.append(path)
            inventory.append(
                InventoryEntry(
                    relative,
                    size,
                    content_hash,
                    "source",
                    blob_sha=blob_sha,
                )
            )
    rows = [
        (
            item.path,
            item.size,
            item.content_sha256,
            sensitive_digests.get(item.path),
            item.classification,
            item.reason,
            item.blob_sha,
        )
        for item in inventory
    ]

    tree_sha256 = hashlib.sha256(canonical_json(rows).encode()).hexdigest()
    if snapshot is None:
        snapshot = RepositorySnapshot(
            "local-directory",
            root.name,
            f"local://{root.name}",
            None,
            None,
            tree_sha256,
            None,
        )
    else:
        snapshot = replace(snapshot, tree_sha256=tree_sha256)
    return ScanResult(
        root,
        tuple(analyzable),
        tuple(inventory),
        tree_sha256,
        snapshot,
    )
