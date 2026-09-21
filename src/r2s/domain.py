from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import StringConstraints

from r2s.contract_types import (
    ByteCount,
    CapabilityId,
    ClaimId,
    Confidence,
    EvidenceId,
    GitOid,
    PositiveLine,
    Sha256,
    SourcePath,
    StrictRecord,
    Text,
)
from r2s.fact_contracts import CommandName, CommandPath, FactValue


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
class SourceLocation(StrictRecord):
    path: SourcePath
    pointer: Text
    content_sha256: Sha256
    start_line: PositiveLine | None = None
    end_line: PositiveLine | None = None
    commit_sha: GitOid | None = None
    blob_sha: GitOid | None = None


@dataclass(frozen=True)
class InventoryEntry(StrictRecord):
    path: SourcePath
    size: ByteCount
    content_sha256: Sha256 | None
    classification: Literal["source", "binary", "sensitive", "sensitive-directory", "skipped", "symlink"]
    reason: str | None = None
    blob_sha: GitOid | None = None


@dataclass(frozen=True)
class Evidence(StrictRecord):
    id: EvidenceId
    kind: Text
    raw_value: dict[str, Any]
    normalized_value: dict[str, Any]
    source: SourceLocation
    extractor: Text
    confidence: Confidence


@dataclass(frozen=True)
class Claim(StrictRecord):
    id: ClaimId
    subject: Text
    predicate: Literal["provides_cli", "supports_subcommand", "supports_option", "supports_argument", "has_license_file"]
    object: FactValue
    evidence_ids: tuple[EvidenceId, ...]
    confidence: Confidence
    executable_fact: bool
    status: Literal["supported", "conflicted", "unknown"] = "supported"


@dataclass(frozen=True)
class Capability(StrictRecord):
    id: CapabilityId
    title: Text
    intent: Text
    claim_ids: tuple[ClaimId, ...]
    support_level: Literal["statically_verified", "unknown"] = "statically_verified"


@dataclass(frozen=True)
class CommandSpec(StrictRecord):
    command: CommandName
    path: CommandPath
    entrypoint_claim_id: ClaimId
    declaration_claim_id: ClaimId
    parent_claim_id: ClaimId | None
    option_claim_ids: tuple[ClaimId, ...]
    completeness: Literal["partial"] = "partial"
    argument_claim_ids: tuple[ClaimId, ...] = ()


@dataclass(frozen=True)
class ParameterBinding(StrictRecord):
    claim_id: ClaimId
    values: tuple[str, ...]
    origin: Literal["user_input", "model_candidate"] = "user_input"


@dataclass(frozen=True)
class ProcedureStep(StrictRecord):
    action: Text
    arguments: tuple[str, ...]
    claim_ids: tuple[str, ...]
    expected_observation: str
    risk: str = "read_only"
    command_path: CommandPath = ()
    bindings: tuple[ParameterBinding, ...] = ()
    mode: Literal["inventory", "invocation"] = "inventory"
    stdout_file: SourcePath | None = None
    stdin: Annotated[str, StringConstraints(max_length=16384)] | None = None


@dataclass(frozen=True)
class Procedure(StrictRecord):
    id: str
    title: str
    intent: str
    capability_ids: tuple[str, ...]
    precondition_claim_ids: tuple[str, ...]
    steps: tuple[ProcedureStep, ...]
    execution_class: str = "read_only"


@dataclass(frozen=True)
class Finding(StrictRecord):
    code: Text
    severity: Literal["info", "warning", "error"]
    message: Text
    path: SourcePath | None = None


@dataclass(frozen=True)
class ClientProfile:
    id: str
    target: str
    skill_spec_version: str
    plugin_manifest_version: str | None = None


@dataclass(frozen=True)
class RepositorySnapshot(StrictRecord):
    kind: Literal["local-directory", "local-git", "github", "github-archive"]
    source_name: Text
    locator: Text
    requested_ref: str | None
    resolved_commit_sha: GitOid | None
    tree_sha256: Sha256
    git_dirty: bool | None
    scan_policy_id: Text = "static-safe-v1"
    git_object_format: Literal["sha1", "sha256"] | None = None


@dataclass
class DiscoveryIR(StrictRecord):
    schema_version: Literal["1.5.0"]
    snapshot: RepositorySnapshot
    languages: list[Literal["python", "javascript", "typescript", "go", "rust"]] = field(default_factory=list)
    repository_types: list[Literal["cli", "library", "framework", "http", "data", "gui", "unknown"]] = field(default_factory=list)
    inventory: list[InventoryEntry] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    claims: list[Claim] = field(default_factory=list)
    capabilities: list[Capability] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    commands: list[CommandSpec] = field(default_factory=list)

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
        from r2s.discovery_contract import parse_discovery

        return parse_discovery(value)


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
