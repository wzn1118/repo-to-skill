from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class RunOutcome(str, Enum):
    COMPLETED = "COMPLETED"
    NEEDS_INPUT = "NEEDS_INPUT"
    POLICY_DENIED = "POLICY_DENIED"
    FAILED = "FAILED"


class BundleReadiness(str, Enum):
    STATIC_READY = "STATIC_READY"
    RUNTIME_READY = "RUNTIME_READY"
    MAP_ONLY = "MAP_ONLY"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    UNSUITABLE = "UNSUITABLE"


@dataclass(frozen=True)
class SourceLocation:
    path: str
    pointer: str
    content_sha256: str
    start_line: int | None = None
    end_line: int | None = None
    commit_sha: str | None = None
    blob_sha: str | None = None


@dataclass(frozen=True)
class InventoryEntry:
    path: str
    size: int
    content_sha256: str | None
    classification: str
    reason: str | None = None
    blob_sha: str | None = None


@dataclass(frozen=True)
class Evidence:
    id: str
    kind: str
    raw_value: dict[str, Any]
    normalized_value: dict[str, Any]
    source: SourceLocation
    extractor: str
    confidence: float


@dataclass(frozen=True)
class Claim:
    id: str
    subject: str
    predicate: str
    object: dict[str, Any]
    evidence_ids: tuple[str, ...]
    confidence: float
    executable_fact: bool
    status: str = "supported"


@dataclass(frozen=True)
class Capability:
    id: str
    title: str
    intent: str
    claim_ids: tuple[str, ...]
    support_level: str = "statically_verified"


@dataclass(frozen=True)
class ProcedureStep:
    action: str
    arguments: tuple[str, ...]
    claim_ids: tuple[str, ...]
    expected_observation: str
    risk: str = "read_only"


@dataclass(frozen=True)
class Procedure:
    id: str
    title: str
    intent: str
    capability_ids: tuple[str, ...]
    precondition_claim_ids: tuple[str, ...]
    steps: tuple[ProcedureStep, ...]
    execution_class: str = "read_only"


@dataclass(frozen=True)
class Finding:
    code: str
    severity: str
    message: str
    path: str | None = None


@dataclass(frozen=True)
class ClientProfile:
    id: str
    target: str
    skill_spec_version: str
    plugin_manifest_version: str | None = None


@dataclass(frozen=True)
class RepositorySnapshot:
    kind: str
    source_name: str
    locator: str
    requested_ref: str | None
    resolved_commit_sha: str | None
    tree_sha256: str
    git_dirty: bool | None
    scan_policy_id: str = "static-safe-v1"
    git_object_format: str | None = None


@dataclass
class DiscoveryIR:
    schema_version: str
    snapshot: RepositorySnapshot
    languages: list[str] = field(default_factory=list)
    repository_types: list[str] = field(default_factory=list)
    inventory: list[InventoryEntry] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    claims: list[Claim] = field(default_factory=list)
    capabilities: list[Capability] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def source_name(self) -> str:
        return self.snapshot.source_name

    @property
    def tree_sha256(self) -> str:
        return self.snapshot.tree_sha256

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> DiscoveryIR:
        snapshot_value = value.get("snapshot")
        if snapshot_value is None:
            snapshot_value = {
                "kind": "local",
                "source_name": value["source_name"],
                "locator": f"local://{value['source_name']}",
                "requested_ref": None,
                "resolved_commit_sha": None,
                "tree_sha256": value["tree_sha256"],
                "git_dirty": None,
            }
        evidence = [
            Evidence(
                id=item["id"],
                kind=item["kind"],
                raw_value=item["raw_value"],
                normalized_value=item["normalized_value"],
                source=SourceLocation(**item["source"]),
                extractor=item["extractor"],
                confidence=item["confidence"],
            )
            for item in value.get("evidence", [])
        ]
        claims = [
            Claim(
                id=item["id"],
                subject=item["subject"],
                predicate=item["predicate"],
                object=item["object"],
                evidence_ids=tuple(item["evidence_ids"]),
                confidence=item["confidence"],
                executable_fact=item["executable_fact"],
                status=item.get("status", "supported"),
            )
            for item in value.get("claims", [])
        ]
        capabilities = [
            Capability(
                id=item["id"],
                title=item["title"],
                intent=item["intent"],
                claim_ids=tuple(item["claim_ids"]),
                support_level=item.get("support_level", "statically_verified"),
            )
            for item in value.get("capabilities", [])
        ]
        return cls(
            schema_version=value["schema_version"],
            snapshot=RepositorySnapshot(**snapshot_value),
            languages=list(value.get("languages", [])),
            repository_types=list(value.get("repository_types", [])),
            inventory=[InventoryEntry(**item) for item in value.get("inventory", [])],
            evidence=evidence,
            claims=claims,
            capabilities=capabilities,
            findings=[Finding(**item) for item in value.get("findings", [])],
        )


@dataclass(frozen=True)
class BuildResult:
    target: str
    root: str | None
    bundles: tuple[str, ...]
    readiness: BundleReadiness
    findings: tuple[Finding, ...]
    outcome: RunOutcome = RunOutcome.COMPLETED


@dataclass(frozen=True)
class CapabilityDelta:
    key: str
    old_capability_id: str | None
    new_capability_id: str | None
    old_fingerprint: str | None
    new_fingerprint: str | None


@dataclass(frozen=True)
class DriftReport:
    schema_version: str
    old_run_id: str
    new_run_id: str
    old_tree_sha256: str
    new_tree_sha256: str
    policy_changed: bool
    added_files: tuple[str, ...]
    removed_files: tuple[str, ...]
    changed_files: tuple[str, ...]
    added_capabilities: tuple[CapabilityDelta, ...]
    removed_capabilities: tuple[CapabilityDelta, ...]
    changed_capabilities: tuple[CapabilityDelta, ...]
    unchanged_capabilities: tuple[CapabilityDelta, ...]
    affected_new_capability_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
