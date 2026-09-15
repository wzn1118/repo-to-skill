from __future__ import annotations

import json
import os
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from r2s.bundle_contracts import RelativePath, Sha256
from r2s.bundle_validation import bundle_digest, inventory, validate_plugin
from r2s.documents import slugify
from r2s.domain import Finding
from r2s.serialization import canonical_json


class InstalledVersion(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    id: Sha256
    path: RelativePath
    version: str


class InstallReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    format: Literal["r2s-install-receipt-v1"] = "r2s-install-receipt-v1"
    name: str
    digest: Sha256
    version: str
    installed_at: str
    previous: list[InstalledVersion]
    source_authenticity: Literal["not_independently_authenticated"] = "not_independently_authenticated"


def _write_json(path: Path, value: dict[str, Any]) -> None:
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="\n", dir=path.parent,
        prefix=f".{path.name}.", delete=False,
    ) as handle:
        temporary = Path(handle.name)
        handle.write(canonical_json(value))
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _no_links(path: Path) -> None:
    for parent in [path, *path.parents]:
        if parent.is_symlink():
            raise ValueError("INSTALL_SYMLINK_REJECTED")


def _current(destination: Path, name: str) -> InstallReceipt | None:
    target = destination / name
    receipt_path = destination / ".r2s" / f"{name}.json"
    _no_links(target)
    _no_links(receipt_path)
    if (destination / ".r2s" / f"{name}.transaction.json").exists():
        raise ValueError("INSTALL_RECOVERY_REQUIRED")
    if not target.exists() and not receipt_path.exists():
        return None
    if not receipt_path.is_file():
        raise ValueError("INSTALL_TARGET_UNMANAGED")
    if receipt_path.stat().st_size > 65536:
        raise ValueError("INSTALL_RECEIPT_INVALID")
    try:
        receipt = InstallReceipt.model_validate_json(receipt_path.read_bytes())
    except ValueError as exc:
        raise ValueError("INSTALL_RECEIPT_INVALID") from exc
    files, findings = inventory(target)
    if findings or bundle_digest(files) != receipt.digest or receipt.name != name:
        raise ValueError("INSTALL_USER_MODIFIED")
    return receipt


def install_plugin(
    plugin_root: Path,
    destination_root: Path,
    execute: bool = False,
    update: bool = False,
    expected_digest: str | None = None,
) -> tuple[Path | None, list[Finding], list[str]]:
    findings = validate_plugin(plugin_root, expected_digest)
    if findings:
        return None, findings, []
    files, findings = inventory(plugin_root)
    if findings:
        return None, findings, []
    manifest = json.loads(files[".codex-plugin/plugin.json"])
    name = manifest["name"]
    paths = sorted(files)
    destination = destination_root.absolute()
    target = destination / name
    try:
        _no_links(destination)
        current = _current(destination, name)
        if current is not None and not update:
            raise ValueError("INSTALL_REQUIRES_UPDATE")
        if current is None and update:
            raise ValueError("INSTALL_TARGET_UNMANAGED")
        if expected_digest is not None and bundle_digest(files) != expected_digest:
            raise ValueError("BUNDLE_DIGEST_MISMATCH")
        if not execute:
            return target, [], paths
        destination.mkdir(parents=True, exist_ok=True)
        state = destination / ".r2s"
        state.mkdir(exist_ok=True)
        _no_links(state)
        with (state / f"{name}.lock").open("x") as lock:
            lock.write(str(os.getpid()))
        try:
            if _current(destination, name) != current:
                raise ValueError("INSTALL_STATE_CHANGED")
            _install_transaction(destination, name, files, manifest["version"], current)
        finally:
            (state / f"{name}.lock").unlink()
    except FileExistsError:
        return target, [Finding("INSTALL_BUSY", "error", "Another installation holds the lock")], paths
    except (OSError, ValueError) as exc:
        code = str(exc) if isinstance(exc, ValueError) else "INSTALL_IO_FAILED"
        return target, [Finding(code, "error", "Installation stopped; review the finding code")], paths
    return target, [], paths


def _install_transaction(
    destination: Path, name: str, files: dict[str, bytes], version: str,
    current: InstallReceipt | None,
) -> None:
    target = destination / name
    state = destination / ".r2s"
    receipt_path = state / f"{name}.json"
    journal_path = state / f"{name}.transaction.json"
    backup_relative = f".r2s/history/{name}/{uuid.uuid4().hex}"
    backup = destination / backup_relative
    _no_links(backup)
    previous = list(current.previous) if current is not None else []
    if current is not None:
        previous.append(InstalledVersion(id=current.digest, path=backup_relative, version=current.version))
    receipt = InstallReceipt(
        name=name, digest=bundle_digest(files), version=version,
        installed_at=datetime.now(UTC).isoformat(), previous=previous,
    )
    with tempfile.TemporaryDirectory(prefix=f".{name}.staging-", dir=destination) as directory:
        staged = Path(directory) / name
        for relative, content in files.items():
            path = staged / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        if validate_plugin(staged, receipt.digest):
            raise ValueError("INSTALL_STAGING_INVALID")
        if _current(destination, name) != current:
            raise ValueError("INSTALL_STATE_CHANGED")
        journal = {
            "format": "r2s-install-transaction-v1", "name": name,
            "before": current.model_dump() if current else None,
            "after": receipt.model_dump(), "backup": backup_relative,
        }
        _write_json(journal_path, journal)
        retired = False
        switched = False
        try:
            if current is not None:
                backup.parent.mkdir(parents=True, exist_ok=True)
                target.rename(backup)
                retired = True
            staged.rename(target)
            switched = True
            _write_json(receipt_path, receipt.model_dump())
        except OSError:
            if switched:
                target.rename(staged)
            if retired:
                backup.rename(target)
            journal_path.unlink()
            raise
        try:
            journal_path.unlink()
        except OSError:
            raise ValueError("INSTALL_RECOVERY_REQUIRED")


def rollback_plugin(
    destination: Path, name: str, version_id: str, execute: bool = False,
) -> tuple[Path | None, list[Finding], list[str]]:
    if name != slugify(name):
        return None, [Finding("INSTALL_NAME_INVALID", "error", "Invalid installation name")], []
    try:
        current = _current(destination.absolute(), name)
        if current is None:
            raise ValueError("INSTALL_TARGET_UNMANAGED")
        previous = next((item for item in reversed(current.previous) if item.id == version_id), None)
        if previous is None or not previous.path.startswith(f".r2s/history/{name}/"):
            raise ValueError("INSTALL_VERSION_UNKNOWN")
        source = destination / previous.path
        _no_links(source)
        return install_plugin(source, destination, execute, True, previous.id)
    except ValueError as exc:
        return None, [Finding(str(exc), "error", "Rollback cannot use this version")], []


def recover_installation(destination: Path, name: str, execute: bool = False) -> list[Finding]:
    if name != slugify(name):
        return [Finding("INSTALL_NAME_INVALID", "error", "Invalid installation name")]
    state = destination.absolute() / ".r2s"
    try:
        _no_links(state)
        journal_path = state / f"{name}.transaction.json"
        _no_links(journal_path)
        if not journal_path.is_file() or journal_path.stat().st_size > 131072:
            raise ValueError("INSTALL_TRANSACTION_INVALID")
        journal = json.loads(journal_path.read_bytes())
        after = InstallReceipt.model_validate(journal["after"])
        target = destination / name
        files, findings = inventory(target)
        if findings or bundle_digest(files) != after.digest or after.name != name:
            raise ValueError("INSTALL_RECOVERY_CONFLICT")
        if execute:
            _no_links(state / f"{name}.json")
            _write_json(state / f"{name}.json", after.model_dump())
            journal_path.unlink()
    except (OSError, ValueError, KeyError, TypeError):
        return [Finding("INSTALL_RECOVERY_CONFLICT", "error", "Transaction needs manual review; files preserved")]
    return []
