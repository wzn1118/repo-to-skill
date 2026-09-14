from __future__ import annotations

from dataclasses import asdict
from typing import Any

from r2s.domain import Capability, CapabilityDelta, DiscoveryIR, DriftReport
from r2s.serialization import canonical_json, canonical_sha256


def _capability_key(discovery: DiscoveryIR, capability: Capability) -> str:
    claims = {claim.id: claim for claim in discovery.claims}
    entrypoints = [
        claims[claim_id]
        for claim_id in capability.claim_ids
        if claim_id in claims and claims[claim_id].predicate == "provides_cli"
    ]
    if len(entrypoints) == 1:
        command = str(entrypoints[0].object.get("command", "")).casefold()
        return f"cli:{command}"
    return f"capability:{capability.id}"


def _claim_payload(discovery: DiscoveryIR, capability: Capability) -> list[dict[str, Any]]:
    claims = {claim.id: claim for claim in discovery.claims}
    evidence = {item.id: item for item in discovery.evidence}
    payload: list[dict[str, Any]] = []
    for claim_id in capability.claim_ids:
        claim = claims.get(claim_id)
        if claim is None:
            payload.append({"missing_claim_id": claim_id})
            continue
        claim_value = asdict(claim)
        claim_value.pop("id", None)
        evidence_values = []
        for evidence_id in claim.evidence_ids:
            item = evidence.get(evidence_id)
            evidence_values.append(
                asdict(item) if item is not None else {"missing_evidence_id": evidence_id}
            )
        claim_value["evidence"] = evidence_values
        claim_value.pop("evidence_ids", None)
        payload.append(claim_value)
    return sorted(payload, key=canonical_json)


def capability_fingerprint(discovery: DiscoveryIR, capability: Capability) -> str:
    return canonical_sha256(
        {
            "key": _capability_key(discovery, capability),
            "title": capability.title,
            "intent": capability.intent,
            "support_level": capability.support_level,
            "claims": _claim_payload(discovery, capability),
        }
    )


def _policy_fingerprint(discovery: DiscoveryIR) -> str:
    claims = [
        claim
        for claim in discovery.claims
        if claim.predicate in {"has_license", "license_status"}
    ]
    evidence_by_id = {item.id: item for item in discovery.evidence}
    evidence = [
        evidence_by_id[evidence_id]
        for claim in claims
        for evidence_id in claim.evidence_ids
        if evidence_id in evidence_by_id
    ]
    return canonical_sha256(
        {
            "schema_version": discovery.schema_version,
            "scan_policy_id": discovery.snapshot.scan_policy_id,
            "languages": discovery.languages,
            "repository_types": discovery.repository_types,
            "findings": [asdict(item) for item in discovery.findings],
            "policy_claims": [asdict(item) for item in claims],
            "policy_evidence": [asdict(item) for item in evidence],
        }
    )


def _inventory_changes(
    old: DiscoveryIR,
    new: DiscoveryIR,
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    old_files = {item.path: asdict(item) for item in old.inventory}
    new_files = {item.path: asdict(item) for item in new.inventory}
    added = tuple(sorted(new_files.keys() - old_files.keys()))
    removed = tuple(sorted(old_files.keys() - new_files.keys()))
    changed = tuple(
        sorted(
            path
            for path in old_files.keys() & new_files.keys()
            if canonical_json(old_files[path]) != canonical_json(new_files[path])
        )
    )
    return added, removed, changed


def compare_discoveries(
    old: DiscoveryIR,
    new: DiscoveryIR,
    old_run_id: str,
    new_run_id: str,
) -> DriftReport:
    old_capabilities = {_capability_key(old, item): item for item in old.capabilities}
    new_capabilities = {_capability_key(new, item): item for item in new.capabilities}
    if len(old_capabilities) != len(old.capabilities):
        raise ValueError("OLD_CAPABILITY_KEY_CONFLICT")
    if len(new_capabilities) != len(new.capabilities):
        raise ValueError("NEW_CAPABILITY_KEY_CONFLICT")

    policy_changed = _policy_fingerprint(old) != _policy_fingerprint(new)
    added: list[CapabilityDelta] = []
    removed: list[CapabilityDelta] = []
    changed: list[CapabilityDelta] = []
    unchanged: list[CapabilityDelta] = []
    for key in sorted(old_capabilities.keys() | new_capabilities.keys()):
        old_capability = old_capabilities.get(key)
        new_capability = new_capabilities.get(key)
        old_fingerprint = (
            capability_fingerprint(old, old_capability) if old_capability is not None else None
        )
        new_fingerprint = (
            capability_fingerprint(new, new_capability) if new_capability is not None else None
        )
        delta = CapabilityDelta(
            key,
            old_capability.id if old_capability is not None else None,
            new_capability.id if new_capability is not None else None,
            old_fingerprint,
            new_fingerprint,
        )
        if old_capability is None:
            added.append(delta)
        elif new_capability is None:
            removed.append(delta)
        elif old_fingerprint != new_fingerprint or policy_changed:
            changed.append(delta)
        else:
            unchanged.append(delta)

    added_files, removed_files, changed_files = _inventory_changes(old, new)
    affected_ids = tuple(
        item.new_capability_id
        for item in [*added, *changed]
        if item.new_capability_id is not None
    )
    return DriftReport(
        schema_version="1.0.0",
        old_run_id=old_run_id,
        new_run_id=new_run_id,
        old_tree_sha256=old.tree_sha256,
        new_tree_sha256=new.tree_sha256,
        policy_changed=policy_changed,
        added_files=added_files,
        removed_files=removed_files,
        changed_files=changed_files,
        added_capabilities=tuple(added),
        removed_capabilities=tuple(removed),
        changed_capabilities=tuple(changed),
        unchanged_capabilities=tuple(unchanged),
        affected_new_capability_ids=affected_ids,
    )
