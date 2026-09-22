from __future__ import annotations

from pathlib import Path
from typing import Any

from r2s.analyzers import SCHEMA_VERSION, discover
from r2s.discovery_contract import discovery_schema
from r2s.domain import DiscoveryIR
from r2s.drift import compare_discoveries
from r2s.generator import generate, readiness, validate_path
from r2s.planner import plan
from r2s.scan_policy import scan_policy_for
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
    return discovery_schema()


def discover_source(
    source: str,
    output_root: Path,
    ref: str | None = None,
    scan_profile: str = "default",
) -> DiscoveryIR:
    policy = scan_policy_for(scan_profile)
    resolved = resolve_source(source, output_root, ref)
    return discover(resolved.root, resolved.snapshot, resolved.committed_blob_oids, policy)
