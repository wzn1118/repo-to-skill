from __future__ import annotations

import shutil
import tempfile
from dataclasses import asdict, replace
from pathlib import Path
from typing import Literal, cast

from r2s.adapters import adapt_portable_skills
from r2s.bundle_contracts import BundleProvenance
from r2s.bundle_validation import validate_path, validate_plugin, validate_skill, write_lock
from r2s.client_profiles import CLIENT_PROFILES, CODEX_PROFILE, PORTABLE_PROFILE
from r2s.compilation import check_compiler_lock, publish_generation
from r2s.compiler_identity import compiler_identity
from r2s.discovery_contract import parse_discovery
from r2s.distribution import install_plugin
from r2s.documents import render_document, slugify
from r2s.domain import (
    BuildResult,
    BundleReadiness,
    DiscoveryIR,
    Finding,
    Procedure,
    RunOutcome,
)
from r2s.planner import plan
from r2s.scan_policy import bundle_scan_scope
from r2s.serialization import canonical_json
from r2s.workflows import WorkflowRequest

__all__ = ["CODEX_PROFILE", "PORTABLE_PROFILE", "generate", "install_codex_plugin", "readiness", "slugify", "validate_path"]


def _skill_bundle(
    discovery: DiscoveryIR,
    procedure: Procedure,
    output: Path,
) -> Path:
    command = procedure.steps[0].action
    bundle = output / slugify(command)
    claim_by_id = {claim.id: claim for claim in discovery.claims}
    evidence_by_id = {evidence.id: evidence for evidence in discovery.evidence}
    capability = next(
        item for item in discovery.capabilities if item.id == procedure.capability_ids[0]
    )
    option_claim_ids = [
        claim_id for claim_id in capability.claim_ids
        if claim_id in claim_by_id and claim_by_id[claim_id].predicate == "supports_option"
    ]
    subcommand_claim_ids = [
        claim_id for claim_id in capability.claim_ids
        if claim_id in claim_by_id and claim_by_id[claim_id].predicate == "supports_subcommand"
    ]
    argument_claim_ids = [claim_id for claim_id in capability.claim_ids if claim_by_id[claim_id].predicate == "supports_argument"]
    all_claim_ids = sorted(set(capability.claim_ids) | set(procedure.precondition_claim_ids))
    all_evidence_ids = sorted({
        evidence_id for claim_id in all_claim_ids
        for evidence_id in claim_by_id[claim_id].evidence_ids
    })
    provenance = BundleProvenance.model_validate_json(canonical_json({
        "schema_version": discovery.schema_version,
        "source_snapshot": asdict(discovery.snapshot),
        "scan_scope": bundle_scan_scope(discovery.inventory, discovery.snapshot.scan_policy_id),
        "artifact_path": "SKILL.md",
        "procedure": asdict(procedure),
        "document": {
            "renderer": "r2s-cli-v4",
            "entrypoint_claim_id": procedure.precondition_claim_ids[0],
            "option_claim_ids": option_claim_ids,
            "subcommand_claim_ids": subcommand_claim_ids,
            "argument_claim_ids": argument_claim_ids,
        },
        "artifact_claims": {
            "SKILL.md": list(procedure.precondition_claim_ids),
            "references/cli.md": [*subcommand_claim_ids, *option_claim_ids, *argument_claim_ids],
            "references/provenance.md": all_claim_ids,
        },
        "claims": [asdict(claim_by_id[claim_id]) for claim_id in all_claim_ids],
        "evidence": [asdict(evidence_by_id[evidence_id]) for evidence_id in all_evidence_ids],
        "commands": [asdict(item) for item in discovery.commands if item.entrypoint_claim_id in all_claim_ids],
    }))
    documents = render_document(provenance)
    for relative, content in documents.items():
        path = bundle / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    (bundle / "PROVENANCE.json").write_text(
        canonical_json(provenance.model_dump(mode="json")), encoding="utf-8", newline="\n",
    )
    write_lock(bundle)
    return bundle


def generate(
    discovery: DiscoveryIR,
    goal: str,
    run_root: Path,
    target: str,
    capability_ids: set[str] | None = None,
    workflow: WorkflowRequest | None = None,
) -> BuildResult:
    discovery = parse_discovery(discovery.to_dict())
    if target not in CLIENT_PROFILES:
        finding = Finding("CLIENT_PROFILE_UNKNOWN", "error", f"Unsupported target: {target}")
        return BuildResult(target, None, (), BundleReadiness.REVIEW_REQUIRED, (finding,))
    identity = compiler_identity(target)
    if run_root.is_symlink():
        raise ValueError("COMPILATION_PATH_SYMLINK")
    request = check_compiler_lock(run_root, discovery, goal, target, capability_ids, identity, workflow)
    run_root.mkdir(parents=True, exist_ok=True)
    reservation = run_root / ".generation-in-progress"
    try:
        with reservation.open("x", encoding="utf-8"):
            pass
    except FileExistsError as exc:
        raise ValueError("COMPILATION_BUSY_OR_INTERRUPTED") from exc
    try:
        with tempfile.TemporaryDirectory(prefix=".generation-stage-", dir=run_root) as directory:
            staging = Path(directory)
            result = _generate(discovery, " ".join(goal.split()), staging, target, capability_ids, workflow)
            if compiler_identity(target) != identity:
                raise ValueError("COMPILER_CHANGED_DURING_GENERATION")
            if check_compiler_lock(run_root, discovery, goal, target, capability_ids, identity, workflow) != request:
                raise ValueError("COMPILATION_INPUT_CHANGED")
            if result.root is None:
                return result
            publish_generation(staging, run_root, identity, request)
            return replace(
                result,
                root=str(run_root / Path(result.root).relative_to(staging)),
                bundles=tuple(str(run_root / Path(bundle).relative_to(staging)) for bundle in result.bundles),
            )
    finally:
        reservation.unlink()


def _generate(
    discovery: DiscoveryIR, goal: str, run_root: Path, target: str,
    capability_ids: set[str] | None,
    workflow: WorkflowRequest | None = None,
) -> BuildResult:
    profile = CLIENT_PROFILES.get(target)
    if profile is None:
        finding = Finding("CLIENT_PROFILE_UNKNOWN", "error", f"Unsupported target: {target}")
        return BuildResult(target, None, (), BundleReadiness.REVIEW_REQUIRED, (finding,))
    generation_scope = "capability_delta" if capability_ids is not None else "full"
    procedures = plan(discovery, goal, capability_ids, workflow)
    if not procedures:
        has_supported_entrypoint = any(
            claim.predicate == "provides_cli" and claim.status == "supported"
            for claim in discovery.claims
        )
        finding = Finding(
            "GOAL_UNSUPPORTED" if has_supported_entrypoint else "NO_ACTIONABLE_CAPABILITY",
            "error",
            "Select a discovered command or request a general CLI inventory; this goal has no verified workflow"
            if has_supported_entrypoint else "No supported CLI entrypoint was found",
        )
        no_capability_findings = (*discovery.findings, finding)
        status = (
            BundleReadiness.REVIEW_REQUIRED
            if any(
                item.severity in {"error", "critical", "high"}
                for item in no_capability_findings[:-1]
            )
            else (
                BundleReadiness.REVIEW_REQUIRED
                if has_supported_entrypoint
                else BundleReadiness.UNSUITABLE
            )
        )
        return BuildResult(
            target, None, (), status, no_capability_findings,
            RunOutcome.NEEDS_INPUT if has_supported_entrypoint else RunOutcome.COMPLETED,
        )
    skill_names = [slugify(procedure.steps[0].action) for procedure in procedures]
    colliding_names = sorted(
        {name for name in skill_names if skill_names.count(name) > 1}
    )
    if colliding_names:
        finding = Finding(
            "SKILL_NAME_CONFLICT",
            "error",
            f"Multiple procedures map to the same Skill name: {colliding_names}",
        )
        return BuildResult(
            target,
            None,
            (),
            BundleReadiness.REVIEW_REQUIRED,
            (*discovery.findings, finding),
        )
    portable_root = run_root / "portable"
    if portable_root.exists():
        shutil.rmtree(portable_root)
    bundles = tuple(_skill_bundle(discovery, procedure, portable_root) for procedure in procedures)
    (run_root / "goal.json").write_text(
        canonical_json({"raw": goal, "normalized": " ".join(goal.split())}),
        encoding="utf-8",
    )
    (run_root / "procedures.json").write_text(
        canonical_json([asdict(item) for item in procedures]),
        encoding="utf-8",
    )
    (run_root / "client-profile.lock.json").write_text(
        canonical_json(asdict(profile)),
        encoding="utf-8",
    )
    (run_root / "generation-scope.json").write_text(
        canonical_json(
            {
                "scope": generation_scope,
                "capability_ids": sorted(capability_ids or ()),
            }
        ),
        encoding="utf-8",
    )
    findings: list[Finding] = list(discovery.findings)
    for bundle in bundles:
        findings.extend(validate_skill(bundle, discovery=discovery))
    if target == "portable":
        root = portable_root
        target_bundles = bundles
    elif target == "codex":
        plugin_root = run_root / "codex-plugin"
        if plugin_root.exists():
            shutil.rmtree(plugin_root)
        skills_root = plugin_root / "skills"
        skills_root.mkdir(parents=True)
        target_bundles = tuple(skills_root / bundle.name for bundle in bundles)
        for source, destination in zip(bundles, target_bundles):
            shutil.copytree(source, destination)
        manifest_root = plugin_root / ".codex-plugin"
        manifest_root.mkdir()
        plugin_suffix = "-delta" if generation_scope == "capability_delta" else ""
        manifest = {
            "name": slugify(f"{discovery.source_name}-skills{plugin_suffix}"),
            "version": "0.1.0",
            "description": (
                f"Evidence-driven {generation_scope.replace('_', ' ')} skills generated from "
                f"{discovery.source_name}"
            ),
            "skills": "./skills/",
            "author": {"name": "Repo-to-Skill"},
            "interface": {
                "displayName": slugify(f"{discovery.source_name}-skills{plugin_suffix}"),
                "shortDescription": "Source-linked CLI reference generated by Repo-to-Skill.",
                "longDescription": "Static CLI facts with pinned source references. Runtime task success and semantic completeness are not established.",
                "developerName": "Repo-to-Skill",
                "category": "Developer Tools",
                "capabilities": ["Interactive"],
                "defaultPrompt": "Inspect the available CLI facts and their source references.",
            },
        }
        (manifest_root / "plugin.json").write_text(canonical_json(manifest), encoding="utf-8")
        write_lock(plugin_root)
        findings.extend(validate_plugin(plugin_root))
        root = plugin_root
    else:
        target_bundles, adapter_findings = adapt_portable_skills(
            portable_root, run_root, cast(Literal["claude", "cursor"], target), PORTABLE_PROFILE.id,
        )
        findings.extend(adapter_findings)
        root = run_root / target
    status = readiness(findings)
    result = BuildResult(
        target,
        str(root),
        tuple(str(item) for item in target_bundles),
        status,
        tuple(findings),
    )
    (run_root / "validation.json").write_text(
        canonical_json(
            {
                "readiness": status.value,
                "integrity": "deterministic_document_and_file_manifest",
                "source_authenticity": "not_independently_authenticated",
                "compiler_input": "compared_to_discovery_ir",
                "findings": [asdict(item) for item in findings],
            }
        ),
        encoding="utf-8",
    )
    return result


def readiness(findings: list[Finding]) -> BundleReadiness:
    blocking = {"error", "critical", "high"}
    return (
        BundleReadiness.REVIEW_REQUIRED
        if any(item.severity in blocking for item in findings)
        else BundleReadiness.STATIC_READY
    )


def install_codex_plugin(
    plugin_root: Path,
    destination_root: Path,
    execute: bool = False,
    update: bool = False,
) -> tuple[Path | None, list[Finding], list[str]]:
    return install_plugin(plugin_root, destination_root, execute, update)
