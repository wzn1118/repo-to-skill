from __future__ import annotations

import json
import math
from collections.abc import Sequence
from typing import Any

from pydantic import TypeAdapter

from r2s.command_graph import command_specs
from r2s.domain import DiscoveryIR
from r2s.policy import is_safe_command
from r2s.scan_policy import INCOMPLETE_REASONS
from r2s.serialization import canonical_json

DISCOVERY_ADAPTER = TypeAdapter(DiscoveryIR)
MAX_JSON_DEPTH = 64


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("JSON_DUPLICATE_KEY")
        result[key] = value
    return result


def _constant(value: str) -> Any:
    raise ValueError("JSON_NON_FINITE_NUMBER")


def _json_values(value: Any, depth: int = 0) -> None:
    if depth > MAX_JSON_DEPTH:
        raise ValueError("JSON_DEPTH_LIMIT")
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise ValueError("JSON_KEY_INVALID")
        for item in value.values():
            _json_values(item, depth + 1)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _json_values(item, depth + 1)
    elif isinstance(value, float) and not math.isfinite(value):
        raise ValueError("JSON_NON_FINITE_NUMBER")
    elif value is not None and type(value) not in {str, bool, int, float}:
        raise ValueError("JSON_VALUE_INVALID")


def strict_json_loads(value: str | bytes) -> Any:
    try:
        decoded = json.loads(value, object_pairs_hook=_pairs, parse_constant=_constant)
        _json_values(decoded)
        return decoded
    except (RecursionError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("JSON_INVALID") from exc


def _unique(values: Sequence[str], label: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"IR_DUPLICATE_{label}")


def validate_relations(discovery: DiscoveryIR) -> None:
    _unique(discovery.languages, "LANGUAGE")
    _unique(discovery.repository_types, "REPOSITORY_TYPE")
    _unique([item.path for item in discovery.inventory], "INVENTORY_PATH")
    _unique([item.id for item in discovery.evidence], "EVIDENCE_ID")
    _unique([item.id for item in discovery.claims], "CLAIM_ID")
    _unique([item.id for item in discovery.capabilities], "CAPABILITY_ID")
    inventory = {item.path: item for item in discovery.inventory}
    evidence = {item.id: item for item in discovery.evidence}
    claims = {item.id: item for item in discovery.claims}
    snapshot = discovery.snapshot
    if any(item.reason in INCOMPLETE_REASONS for item in discovery.inventory) and not any(
        finding.code == "SCAN_INCOMPLETE" and finding.severity == "error" for finding in discovery.findings
    ) and snapshot.scan_policy_id.startswith("workspace-bounded-v1:"):
        raise ValueError("IR_INCOMPLETE_SCAN_NOT_DECLARED")
    expected_commit = snapshot.resolved_commit_sha if snapshot.git_dirty is False else None
    oid_length = {"sha1": 40, "sha256": 64}.get(snapshot.git_object_format or "")
    if snapshot.resolved_commit_sha is not None and (
        oid_length is None or len(snapshot.resolved_commit_sha) != oid_length
    ):
        raise ValueError("IR_GIT_OBJECT_FORMAT_MISMATCH")
    for entry in discovery.inventory:
        if entry.classification in {"source", "binary"} and entry.content_sha256 is None:
            raise ValueError("IR_INVENTORY_HASH_MISSING")
        if entry.classification in {"sensitive", "sensitive-directory"} and entry.content_sha256 is not None:
            raise ValueError("IR_SENSITIVE_HASH_FORBIDDEN")
        if entry.blob_sha is not None and (
            expected_commit is None or oid_length is None or len(entry.blob_sha) != oid_length
        ):
            raise ValueError("IR_BLOB_IDENTITY_INVALID")
    for item in discovery.evidence:
        source = item.source
        source_entry = inventory.get(source.path)
        if source_entry is None or source_entry.classification != "source":
            raise ValueError("IR_EVIDENCE_SOURCE_MISSING")
        if source.content_sha256 != source_entry.content_sha256 or source.blob_sha != source_entry.blob_sha:
            raise ValueError("IR_EVIDENCE_SOURCE_MISMATCH")
        if source.commit_sha != expected_commit:
            raise ValueError("IR_EVIDENCE_COMMIT_MISMATCH")
        if source.end_line is not None and (source.start_line is None or source.end_line < source.start_line):
            raise ValueError("IR_EVIDENCE_LINE_RANGE_INVALID")
    for claim in discovery.claims:
        _unique(claim.evidence_ids, "CLAIM_EVIDENCE_REFERENCE")
        if not claim.evidence_ids or any(identifier not in evidence for identifier in claim.evidence_ids):
            raise ValueError("IR_CLAIM_EVIDENCE_MISSING")
        executable = claim.predicate in {"provides_cli", "supports_subcommand", "supports_option", "supports_argument"}
        required_field = {"provides_cli": "target", "supports_subcommand": "command_path", "supports_option": "option", "supports_argument": "argument", "has_license_file": "path"}[claim.predicate]
        if required_field not in claim.object:
            raise ValueError("IR_FACT_PAYLOAD_MISMATCH")
        allowed_fields = {
            "provides_cli": {"command", "target", "workspace", "role"},
            "supports_subcommand": {"command", "command_path"},
            "supports_option": {"command", "option", "command_path", "semantics", "shape"},
            "supports_argument": {"command", "argument", "position", "command_path", "semantics", "shape"},
            "has_license_file": {"path"},
        }
        if set(claim.object) - allowed_fields[claim.predicate]:
            raise ValueError("IR_FACT_PAYLOAD_MISMATCH")
        if claim.executable_fact != executable:
            raise ValueError("IR_EXECUTABLE_CLASSIFICATION_MISMATCH")
        if executable:
            command = claim.object.get("command")
            if not isinstance(command, str) or not is_safe_command(command):
                raise ValueError("IR_COMMAND_INVALID")
            if claim.predicate in {"supports_option", "supports_subcommand", "supports_argument"} and claim.subject != command:
                raise ValueError("IR_OPTION_OWNER_MISMATCH")
            if claim.predicate == "provides_cli" and claim.subject != "repository":
                raise ValueError("IR_ENTRYPOINT_OWNER_MISMATCH")
            if claim.predicate == "provides_cli" and claim.object.get("role", "product") != "product":
                raise ValueError("IR_NON_PRODUCT_ENTRYPOINT")
        witnesses = []
        for identifier in claim.evidence_ids:
            witness = dict(evidence[identifier].normalized_value)
            if evidence[identifier].kind == "manifest.entrypoint":
                witness["target"] = f"{witness.get('module')}:{witness.get('symbol')}"
            witnesses.append(all(canonical_json(witness.get(key)) == canonical_json(value) for key, value in claim.object.items()))
        if not any(witnesses):
            raise ValueError("IR_CLAIM_EVIDENCE_MISMATCH")
        if claim.status == "supported" and any(evidence[identifier].confidence <= 0 for identifier in claim.evidence_ids):
            raise ValueError("IR_CLAIM_SUPPORT_INVALID")
    for capability in discovery.capabilities:
        _unique(capability.claim_ids, "CAPABILITY_CLAIM_REFERENCE")
        if not capability.claim_ids or any(identifier not in claims for identifier in capability.claim_ids):
            raise ValueError("IR_CAPABILITY_CLAIM_MISSING")
        entries = [claims[identifier] for identifier in capability.claim_ids if claims[identifier].predicate == "provides_cli"]
        if len(entries) != 1:
            raise ValueError("IR_CAPABILITY_ENTRYPOINT_AMBIGUOUS")
        command = entries[0].object.get("command")
        if any(claims[identifier].predicate in {"supports_option", "supports_subcommand", "supports_argument"} and claims[identifier].subject != command for identifier in capability.claim_ids):
            raise ValueError("IR_CAPABILITY_OPTION_OWNER_MISMATCH")
    if discovery.commands != command_specs(discovery.claims):
        raise ValueError("IR_COMMAND_GRAPH_MISMATCH")


def _parse_discovery_structure(value: Any) -> DiscoveryIR:
    _json_values(value)
    if not isinstance(value, dict):
        raise TypeError("DISCOVERY_OBJECT_REQUIRED")
    if "snapshot" not in value:
        raise ValueError("DISCOVERY_MIGRATION_REQUIRED")
    if value.get("schema_version") in {"1.2.0", "1.3.0", "1.4.0", "1.5.0"}:
        raise ValueError("DISCOVERY_MIGRATION_REQUIRED")
    if value.get("schema_version") != "1.6.0":
        raise ValueError("DISCOVERY_SCHEMA_UNSUPPORTED")
    return DISCOVERY_ADAPTER.validate_json(json.dumps(value, allow_nan=False), strict=True)


def parse_discovery(value: Any) -> DiscoveryIR:
    discovery = _parse_discovery_structure(value)
    validate_relations(discovery)
    return discovery


def discovery_schema() -> dict[str, Any]:
    schema = DISCOVERY_ADAPTER.json_schema()
    schema.update({
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://r2s.local/schema/discovery-1.6.0.json",
        "title": "Repo-to-Skill Discovery IR with scoped commands",
    })
    return schema
