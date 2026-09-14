from __future__ import annotations

from pathlib import Path
from typing import Any

from r2s.analyzers import SCHEMA_VERSION, discover
from r2s.domain import DiscoveryIR
from r2s.drift import compare_discoveries
from r2s.generator import generate, readiness, validate_path
from r2s.planner import plan
from r2s.serialization import canonical_json, file_sha256, stable_id
from r2s.source import resolve_source, update_source
from r2s.storage import load_discovery, resolve_discovery, write_discovery

__all__ = [
    "SCHEMA_VERSION",
    "canonical_json",
    "compare_discoveries",
    "discover",
    "discover_source",
    "file_sha256",
    "generate",
    "load_discovery",
    "plan",
    "readiness",
    "resolve_discovery",
    "schema_catalog",
    "stable_id",
    "update_source",
    "validate_path",
    "write_discovery",
]


def schema_catalog() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"https://r2s.local/schema/discovery-{SCHEMA_VERSION}.json",
        "title": "Repo-to-Skill Discovery IR",
        "type": "object",
        "required": [
            "schema_version",
            "snapshot",
            "languages",
            "repository_types",
            "inventory",
            "evidence",
            "claims",
            "capabilities",
            "findings",
        ],
        "properties": {
            "schema_version": {"const": SCHEMA_VERSION},
            "snapshot": {
                "type": "object",
                "required": [
                    "kind",
                    "source_name",
                    "locator",
                    "requested_ref",
                    "resolved_commit_sha",
                    "tree_sha256",
                    "git_dirty",
                    "scan_policy_id",
                    "git_object_format",
                ],
            },
            "languages": {"type": "array", "items": {"type": "string"}},
            "repository_types": {
                "type": "array",
                "items": {"type": "string"},
            },
            "inventory": {"type": "array"},
            "evidence": {"type": "array"},
            "claims": {"type": "array"},
            "capabilities": {"type": "array"},
            "findings": {"type": "array"},
        },
        "additionalProperties": False,
    }


def discover_source(
    source: str,
    output_root: Path,
    ref: str | None = None,
) -> DiscoveryIR:
    resolved = resolve_source(source, output_root, ref)
    return discover(resolved.root, resolved.snapshot)
