from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from r2s.discovery_contract import parse_discovery, strict_json_loads
from r2s.domain import Evidence, Finding
from r2s.legacy_contracts import import_structure
from r2s.serialization import canonical_json, canonical_sha256, file_sha256
from r2s.storage import MAX_DISCOVERY_ARTIFACT_BYTES, _load_discovery_envelope, write_discovery


def migrate_discovery(source: Path, output: Path) -> dict[str, Any]:
    if source.is_symlink():
        raise ValueError("MIGRATION_SOURCE_SYMLINK")
    source = source.resolve(strict=True)
    output = output.resolve()
    if source.is_dir() and output.is_relative_to(source):
        raise ValueError("MIGRATION_OUTPUT_INSIDE_SOURCE")
    input_file = source / "discovery.json" if source.is_dir() else source
    if input_file.is_symlink() or not input_file.is_file() or input_file.stat().st_size > MAX_DISCOVERY_ARTIFACT_BYTES:
        raise ValueError("MIGRATION_SOURCE_INVALID")
    original_sha256 = file_sha256(input_file)
    original_payload = strict_json_loads(input_file.read_bytes())
    original = (
        _load_discovery_envelope(source, migration=True) if source.is_dir()
        else import_structure(original_payload)
    )
    unique: dict[str, Evidence] = {}
    removed = []
    for item in original.evidence:
        previous = unique.get(item.id)
        if previous is not None:
            if previous != item:
                raise ValueError("MIGRATION_EVIDENCE_COLLISION")
            removed.append(item.id)
        else:
            unique[item.id] = item
    payload = original.to_dict()
    payload["evidence"] = [asdict(item) for item in unique.values()]
    payload["findings"].append(asdict(Finding(
        "MIGRATION_REVIEW_REQUIRED", "error",
        "Imported through bound-workflows-1.5; prior readiness is not inherited. Parameter bindings and operational semantics are not inferred during migration.",
    )))
    migrated = parse_discovery(payload)
    if file_sha256(input_file) != original_sha256:
        raise ValueError("MIGRATION_SOURCE_CHANGED")
    run_root = write_discovery(migrated, output)
    report = {
        "format": "r2s-discovery-migration-v1",
        "ruleset": "bound-workflows-1.5",
        "source_name": source.name,
        "original_schema": original_payload["schema_version"],
        "target_schema": migrated.schema_version,
        "source_discovery_sha256": original_sha256,
        "target_discovery_sha256": canonical_sha256(migrated.to_dict()),
        "target_run_id": run_root.name,
        "removed_identical_evidence_ids": removed,
        "source_integrity": "envelope checked" if source.is_dir() else "untrusted standalone JSON",
        "source_authenticity": "not_independently_authenticated",
        "readiness": "REVIEW_REQUIRED",
    }
    report_path = run_root / "migration.json"
    if report_path.exists():
        if report_path.is_symlink() or strict_json_loads(report_path.read_bytes()) != report:
            raise ValueError("MIGRATION_REPORT_CONFLICT")
    else:
        with report_path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(canonical_json(report))
    return {"run_root": str(run_root), "report": report}
