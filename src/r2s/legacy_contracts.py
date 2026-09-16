from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

from pydantic import TypeAdapter

from r2s.command_graph import command_specs
from r2s.contract_types import StrictRecord
from r2s.domain import (
    Capability,
    Claim,
    DiscoveryIR,
    Evidence,
    Finding,
    InventoryEntry,
    RepositorySnapshot,
)
from r2s.serialization import canonical_json


@dataclass
class LegacyDiscoveryIR(StrictRecord):
    schema_version: Literal["1.2.0", "1.3.0"]
    snapshot: RepositorySnapshot
    languages: list[Literal["python", "javascript", "typescript", "go", "rust"]]
    repository_types: list[Literal["cli", "library", "framework", "http", "data", "gui", "unknown"]]
    inventory: list[InventoryEntry]
    evidence: list[Evidence]
    claims: list[Claim]
    capabilities: list[Capability]
    findings: list[Finding]


LEGACY_ADAPTER = TypeAdapter(LegacyDiscoveryIR)


def import_structure(value: Any) -> DiscoveryIR:
    from r2s.discovery_contract import _parse_discovery_structure

    if not isinstance(value, dict) or value.get("schema_version") not in {"1.2.0", "1.3.0"}:
        return _parse_discovery_structure(value)
    legacy_value = dict(value)
    version = legacy_value["schema_version"]
    commands = legacy_value.pop("commands", None) if version == "1.3.0" else None
    if version == "1.3.0" and not isinstance(commands, list):
        raise ValueError("LEGACY_COMMAND_GRAPH_REQUIRED")
    legacy = LEGACY_ADAPTER.validate_json(canonical_json(legacy_value), strict=True)
    for claim in legacy.claims:
        if "semantics" in claim.object or (version == "1.2.0" and (claim.predicate == "supports_subcommand" or "command_path" in claim.object)):
            raise ValueError("LEGACY_FACT_SHAPE_INVALID")
    payload = asdict(legacy)
    payload["schema_version"] = "1.4.0"
    payload["commands"] = commands if version == "1.3.0" else [asdict(command) for command in command_specs(legacy.claims)]
    return _parse_discovery_structure(payload)
