from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path, PurePosixPath
from typing import Any

from r2s.domain import Capability, Claim, DiscoveryIR, Evidence, Finding, SourceLocation
from r2s.policy import is_safe_command
from r2s.scanner import ScanResult
from r2s.serialization import file_sha256, stable_id


def _line_for(path: Path, needle: str) -> int | None:
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if needle in line:
            return number
    return None


def _location(
    scan_result: ScanResult,
    path: Path,
    pointer: str,
    start_line: int | None = None,
) -> SourceLocation:
    relative = path.relative_to(scan_result.root).as_posix()
    entry = next(
        (item for item in scan_result.inventory if item.path == relative),
        None,
    )
    return SourceLocation(
        path=relative,
        pointer=pointer,
        content_sha256=file_sha256(path),
        start_line=start_line,
        end_line=start_line,
        commit_sha=(
            scan_result.snapshot.resolved_commit_sha
            if scan_result.snapshot.git_dirty is False
            else None
        ),
        blob_sha=entry.blob_sha if entry else None,
    )


def _safe_target(package_root: Path, root: Path, value: str) -> Path | None:
    normalized = value.replace("\\", "/")
    relative = PurePosixPath(normalized)
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        return None
    candidate = (package_root / Path(*relative.parts)).resolve(strict=False)
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate


def _bin_entries(data: dict[str, Any]) -> list[tuple[str, str, str]]:
    package_name = data.get("name")
    bin_value = data.get("bin")
    if isinstance(bin_value, str) and isinstance(package_name, str):
        command = package_name.rsplit("/", 1)[-1]
        return [(command, bin_value, "$.bin")]
    if isinstance(bin_value, dict):
        return [
            (command, target, f"$.bin.{command}")
            for command, target in sorted(bin_value.items())
            if isinstance(command, str) and isinstance(target, str)
        ]
    return []


def _workspace_role(package_root: Path, repository_root: Path) -> str:
    relative_parts = package_root.relative_to(repository_root).parts
    lowered = {part.casefold() for part in relative_parts}
    if lowered & {
        ".fixture", ".fixtures", "test", "tests", "testdata", "fixture", "fixtures",
        "__tests__", "__fixtures__", "__utils__", "e2e", "dev", "node_modules",
    }:
        return "test"
    return "product"


def analyze_javascript(discovery: DiscoveryIR, scan_result: ScanResult) -> None:
    inventory = {item.path: item for item in scan_result.inventory}
    manifests = [
        path
        for path in scan_result.analyzable_files
        if path.name == "package.json"
    ]
    for manifest in sorted(manifests):
        relative_manifest = manifest.relative_to(scan_result.root).as_posix()
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            discovery.findings.append(
                Finding(
                    "JAVASCRIPT_MANIFEST_INVALID",
                    "warning",
                    str(exc),
                    relative_manifest,
                )
            )
            continue
        if not isinstance(data, dict):
            continue
        entries = _bin_entries(data)
        package_root = manifest.parent
        workspace = package_root.relative_to(scan_result.root).as_posix() or "."
        workspace_role = _workspace_role(package_root, scan_result.root)
        has_typescript = (package_root / "tsconfig.json").is_file() or any(
            path.suffix in {".ts", ".tsx"}
            and path.is_relative_to(package_root)
            for path in scan_result.analyzable_files
        )
        discovery.languages.append("typescript" if has_typescript else "javascript")
        discovery.repository_types.append("cli" if entries else "library")
        for command, target_value, pointer in entries:
            if not is_safe_command(command):
                discovery.findings.append(
                    Finding(
                        "UNSAFE_COMMAND_NAME",
                        "error",
                        f"Unsafe command name in package bin: {command}",
                        relative_manifest,
                    )
                )
                continue
            target = _safe_target(package_root, scan_result.root, target_value)
            if target is None:
                discovery.findings.append(
                    Finding(
                        "ENTRYPOINT_PATH_UNSAFE",
                        "error",
                        f"Unsafe package bin target: {target_value}",
                        relative_manifest,
                    )
                )
                continue
            relative_target = target.relative_to(scan_result.root).as_posix()
            target_entry = inventory.get(relative_target)
            if (
                not target.is_file()
                or target_entry is None
                or target_entry.classification != "source"
            ):
                discovery.findings.append(
                    Finding(
                        "ENTRYPOINT_TARGET_EXCLUDED",
                        "warning",
                        f"Package bin target is missing or excluded: {target_value}",
                        relative_manifest,
                    )
                )
                continue
            manifest_source = _location(
                scan_result,
                manifest,
                pointer,
                _line_for(
                    manifest,
                    '"bin"' if pointer == "$.bin" else f'"{command}"',
                ),
            )
            manifest_value = {
                "command": command,
                "target": relative_target,
                "workspace": workspace,
                "role": workspace_role,
            }
            manifest_evidence_id = stable_id(
                "ev",
                ["javascript.bin", manifest_value, asdict(manifest_source)],
            )
            target_source = _location(scan_result, target, "$", 1)
            target_value_normalized = {
                "path": relative_target,
                "language": "typescript"
                if target.suffix in {".ts", ".tsx"}
                else "javascript",
            }
            target_evidence_id = stable_id(
                "ev",
                [
                    "javascript.bin_target",
                    target_value_normalized,
                    asdict(target_source),
                ],
            )
            discovery.evidence.extend(
                [
                    Evidence(
                        manifest_evidence_id,
                        "javascript.bin",
                        {command: target_value},
                        manifest_value,
                        manifest_source,
                        "package-json@1",
                        1.0,
                    ),
                    Evidence(
                        target_evidence_id,
                        "javascript.bin_target",
                        target_value_normalized,
                        target_value_normalized,
                        target_source,
                        "javascript-source@1",
                        0.9,
                    ),
                ]
            )
            claim_id = stable_id(
                "cl",
                [
                    "repository",
                    "provides_cli",
                    manifest_value,
                    manifest_evidence_id,
                    target_evidence_id,
                ],
            )
            if workspace_role != "product":
                discovery.findings.append(
                    Finding(
                        "NON_PRODUCT_ENTRYPOINT_SKIPPED",
                        "info",
                        f"Skipped {workspace_role} workspace entrypoint: {command}",
                        relative_manifest,
                    )
                )
                continue
            discovery.claims.append(
                Claim(
                    claim_id,
                    "repository",
                    "provides_cli",
                    manifest_value,
                    (manifest_evidence_id, target_evidence_id),
                    0.95,
                    True,
                )
            )
            capability_id = stable_id(
                "cap",
                ["invoke_cli", command, workspace, claim_id],
            )
            discovery.capabilities.append(
                Capability(
                    capability_id,
                    f"Use the {command} CLI",
                    f"Invoke the {command} command",
                    (claim_id,),
                )
            )
