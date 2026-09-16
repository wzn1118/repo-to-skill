from __future__ import annotations

import hashlib
import json
import math
import os
import re
import stat
import unicodedata
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ValidationError
from yaml.nodes import MappingNode, ScalarNode
from yaml.tokens import AliasToken, AnchorToken, TagToken

from r2s.bundle_contracts import BundleLock, BundleProvenance, PluginManifest, relative_path
from r2s.command_graph import command_specs
from r2s.documents import render_document
from r2s.domain import DiscoveryIR, Finding
from r2s.scan_policy import bundle_scan_scope
from r2s.serialization import canonical_json, canonical_sha256

LOCK_NAME = "BUNDLE.lock.json"
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_BUNDLE_BYTES = 32 * 1024 * 1024
MAX_FILES = 4096


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON object key")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError("Non-finite JSON number")


def _decode[Model: BaseModel](data: bytes, model: type[Model]) -> Model:
    json.loads(data, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    return model.model_validate_json(data)


def inventory(root: Path) -> tuple[dict[str, bytes], list[Finding]]:
    files: dict[str, bytes] = {}
    names: set[str] = set()
    total = 0
    count = 0
    try:
        if root.is_symlink() or not root.is_dir():
            raise ValueError("Bundle root must be a real directory")
        for directory, directories, filenames in os.walk(root, followlinks=False):
            for name in sorted([*directories, *filenames]):
                path = Path(directory) / name
                relative = path.relative_to(root).as_posix()
                relative_path(relative)
                count += 1
                if count > MAX_FILES or len(path.relative_to(root).parts) > 16:
                    raise ValueError("Bundle file count or depth exceeds the limit")
                key = unicodedata.normalize("NFC", relative).casefold()
                if key in names:
                    raise ValueError("Bundle contains a case or Unicode path collision")
                names.add(key)
                mode = path.lstat().st_mode
                if stat.S_ISDIR(mode):
                    continue
                if not stat.S_ISREG(mode):
                    raise ValueError("Symlinks and special files are forbidden")
                with path.open("rb") as handle:
                    data = handle.read(MAX_FILE_BYTES + 1)
                total += len(data)
                if len(data) > MAX_FILE_BYTES or total > MAX_BUNDLE_BYTES:
                    raise ValueError("Bundle byte limit exceeded")
                files[relative] = data
    except (OSError, ValueError):
        return {}, [Finding(
            "BUNDLE_UNSAFE", "error",
            "Bundle contains an unsafe path, link, special file, collision, or exceeds limits",
        )]
    return files, []


def bundle_digest(files: dict[str, bytes]) -> str:
    return canonical_sha256({
        name: hashlib.sha256(data).hexdigest() for name, data in files.items()
    })


def write_lock(root: Path) -> None:
    files, findings = inventory(root)
    if findings:
        raise ValueError("BUNDLE_UNSAFE")
    manifest = BundleLock(files={
        name: hashlib.sha256(data).hexdigest()
        for name, data in files.items() if name != LOCK_NAME
    })
    (root / LOCK_NAME).write_text(
        canonical_json(manifest.model_dump()), encoding="utf-8", newline="\n",
    )


def _check_lock(files: dict[str, bytes], expected_digest: str | None) -> list[Finding]:
    findings = []
    if expected_digest is not None and bundle_digest(files) != expected_digest:
        findings.append(Finding(
            "BUNDLE_DIGEST_MISMATCH", "error", "Bundle differs from the independently supplied digest",
        ))
    if LOCK_NAME not in files:
        return [*findings, Finding(
            "BUNDLE_LOCK_MISSING", "error", "Legacy or third-party bundle requires recompilation/review",
            LOCK_NAME,
        )]
    try:
        lock = _decode(files[LOCK_NAME], BundleLock)
    except (ValueError, UnicodeError, RecursionError):
        return [*findings, Finding("BUNDLE_LOCK_INVALID", "error", "Invalid bundle manifest", LOCK_NAME)]
    actual = {name: data for name, data in files.items() if name != LOCK_NAME}
    if set(actual) != set(lock.files):
        findings.append(Finding(
            "ARTIFACT_SET_MISMATCH", "error", "File set differs from bundle manifest", LOCK_NAME,
        ))
    for name in sorted(actual.keys() & lock.files.keys()):
        if hashlib.sha256(actual[name]).hexdigest() != lock.files[name]:
            findings.append(Finding("ARTIFACT_HASH_MISMATCH", "error", "Artifact hash mismatch", name))
    return findings


def _frontmatter(data: bytes, directory_name: str) -> list[Finding]:
    try:
        text = data.decode("utf-8")
        if not text.startswith("---\n") or "\n---\n" not in text[4:]:
            raise ValueError("Missing YAML frontmatter")
        header = text[4:text.index("\n---\n", 4)]
        if len(header) > 4096:
            raise ValueError("Frontmatter too long")
        if any(isinstance(token, (AliasToken, AnchorToken, TagToken)) for token in yaml.scan(header)):
            raise ValueError("YAML aliases, anchors and tags are forbidden")
        mapping = yaml.compose(header, Loader=yaml.SafeLoader)
        if not isinstance(mapping, MappingNode):
            raise TypeError("Frontmatter must be a mapping")
        metadata: dict[str, str] = {}
        for key, value in mapping.value:
            if (
                not isinstance(key, ScalarNode) or not isinstance(value, ScalarNode)
                or key.tag != "tag:yaml.org,2002:str" or value.tag != "tag:yaml.org,2002:str"
                or key.value in metadata
            ):
                raise ValueError("Frontmatter requires unique string keys and string values")
            metadata[key.value] = value.value
        if set(metadata) != {"name", "description"} or not metadata["description"].strip():
            raise ValueError("Unsupported frontmatter fields")
        if (
            not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", metadata["name"])
            or len(metadata["name"]) > 64 or metadata["name"] != directory_name
        ):
            return [Finding("INVALID_SKILL_NAME", "error", "Skill name must match directory", "SKILL.md")]
        if len(metadata["description"]) > 1024:
            return [Finding("DESCRIPTION_TOO_LONG", "error", "Description exceeds limit", "SKILL.md")]
    except (ValueError, TypeError, UnicodeError, yaml.YAMLError, RecursionError):
        return [Finding("INVALID_FRONTMATTER", "error", "Unsafe or invalid frontmatter", "SKILL.md")]
    return []


def _check_provenance(provenance: BundleProvenance) -> list[Finding]:
    claims = {claim.id: claim for claim in provenance.claims}
    evidence = {item.id: item for item in provenance.evidence}
    findings = []
    if len(claims) != len(provenance.claims) or len(evidence) != len(provenance.evidence):
        findings.append(Finding("PROVENANCE_DUPLICATE_ID", "error", "Duplicate claim or evidence ID"))
    used = set(provenance.procedure.precondition_claim_ids)
    used.add(provenance.document.entrypoint_claim_id)
    used.update(provenance.document.option_claim_ids)
    used.update(provenance.document.subcommand_claim_ids)
    for step in provenance.procedure.steps:
        used.update(step.claim_ids)
    for claim_ids in provenance.artifact_claims.values():
        used.update(claim_ids)
    if used - claims.keys():
        findings.append(Finding("UNKNOWN_CLAIM", "error", "Missing referenced claims"))
    expected_commit = (
        provenance.source_snapshot.resolved_commit_sha
        if provenance.source_snapshot.git_dirty is False else None
    )
    for claim in provenance.claims:
        if not claim.evidence_ids or set(claim.evidence_ids) - evidence.keys():
            findings.append(Finding("UNKNOWN_EVIDENCE", "error", "Claim lacks referenced evidence"))
        if not math.isfinite(claim.confidence) or not 0 <= claim.confidence <= 1:
            findings.append(Finding("PROVENANCE_INVALID", "error", "Invalid claim confidence"))
        witnesses = []
        for evidence_id in claim.evidence_ids:
            item = evidence.get(evidence_id)
            if item is None:
                continue
            value = dict(item.normalized_value)
            if item.kind == "manifest.entrypoint" and "module" in value and "symbol" in value:
                value["target"] = f"{value['module']}:{value['symbol']}"
            witnesses.append(all(canonical_json(value.get(key)) == canonical_json(field) for key, field in claim.object.items()))
        if claim.executable_fact and not any(witnesses):
            findings.append(Finding(
                "CLAIM_EVIDENCE_MISMATCH", "error", "Executable claim disagrees with evidence",
            ))
    for item in provenance.evidence:
        source = item.source
        if expected_commit and source.commit_sha != expected_commit:
            findings.append(Finding("EVIDENCE_COMMIT_MISMATCH", "error", "Evidence commit mismatch"))
        try:
            relative_path(source.path)
            if (
                not re.fullmatch(r"[0-9a-f]{64}", source.content_sha256)
                or not math.isfinite(item.confidence) or not 0 <= item.confidence <= 1
                or (source.start_line is not None and source.start_line < 1)
                or (source.end_line is not None and (
                    source.start_line is None or source.end_line < source.start_line
                ))
                or (source.commit_sha is not None and not re.fullmatch(
                    r"(?:[0-9a-f]{40}|[0-9a-f]{64})", source.commit_sha,
                ))
            ):
                raise ValueError("Invalid source location")
        except ValueError:
            findings.append(Finding("EVIDENCE_SOURCE_INVALID", "error", "Invalid source location"))
    try:
        if provenance.commands != command_specs(provenance.claims):
            raise ValueError("IR_COMMAND_GRAPH_MISMATCH")
    except ValueError as exc:
        findings.append(Finding("COMMAND_GRAPH_INVALID", "error", str(exc)))
    return findings


def _validate_skill_files(
    files: dict[str, bytes], name: str, expected_digest: str | None = None,
    discovery: DiscoveryIR | None = None,
) -> list[Finding]:
    findings = _check_lock(files, expected_digest)
    if "SKILL.md" not in files:
        return [*findings, Finding("SKILL_MISSING", "error", "SKILL.md is required")]
    findings.extend(_frontmatter(files["SKILL.md"], name))
    if "PROVENANCE.json" not in files:
        return [*findings, Finding("PROVENANCE_MISSING", "error", "PROVENANCE.json is required")]
    try:
        provenance = _decode(files["PROVENANCE.json"], BundleProvenance)
    except (ValidationError, ValueError, UnicodeError, RecursionError):
        return [*findings, Finding("PROVENANCE_INVALID", "error", "Invalid provenance contract")]
    findings.extend(_check_provenance(provenance))
    scope = provenance.scan_scope
    if scope is not None and scope.policy_id != provenance.source_snapshot.scan_policy_id:
        findings.append(Finding("SCAN_SCOPE_POLICY_MISMATCH", "error", "Bundle scan scope differs from snapshot policy"))
    if scope is None or scope.complete_within_policy is None:
        findings.append(Finding("SCAN_SCOPE_UNKNOWN", "error", "Source analysis scope has not been recorded under the current policy"))
    elif not scope.complete_within_policy or scope.budget_skipped_files:
        findings.append(Finding("SCAN_INCOMPLETE", "error", "Bundle comes from a partial scan; unscanned capabilities remain unknown"))
    if discovery is not None:
        trusted_claims = {claim.id: claim for claim in discovery.claims}
        trusted_evidence = {item.id: item for item in discovery.evidence}
        if (
            provenance.source_snapshot != discovery.snapshot
            or any(trusted_claims.get(claim.id) != claim for claim in provenance.claims)
            or any(trusted_evidence.get(item.id) != item for item in provenance.evidence)
            or scope is None
            or scope.model_dump() != bundle_scan_scope(discovery.inventory, discovery.snapshot.scan_policy_id)
        ):
            findings.append(Finding("SOURCE_IR_MISMATCH", "error", "Bundle differs from supplied discovery"))
    try:
        rendered = render_document(provenance)
    except (ValueError, KeyError):
        return [*findings, Finding("DOCUMENT_INVALID", "error", "Document has unsupported executable facts")]
    expected_mapping = {
        "SKILL.md": [provenance.document.entrypoint_claim_id],
        "references/cli.md": [*provenance.document.subcommand_claim_ids, *provenance.document.option_claim_ids],
        "references/provenance.md": sorted(claim.id for claim in provenance.claims),
    }
    if provenance.artifact_claims != expected_mapping:
        findings.append(Finding("ARTIFACT_PROVENANCE_INVALID", "error", "Document claim mapping mismatch"))
    if set(files) != {*rendered, "PROVENANCE.json", LOCK_NAME}:
        findings.append(Finding("DOCUMENT_FILE_SET_MISMATCH", "error", "Unsupported or missing document files"))
    for path, data in rendered.items():
        if files.get(path) != data:
            findings.append(Finding("DOCUMENT_CONTENT_MISMATCH", "error", "Content differs from evidenced document", path))
    return findings


def validate_skill(
    bundle: Path, expected_digest: str | None = None, discovery: DiscoveryIR | None = None,
) -> list[Finding]:
    files, findings = inventory(bundle)
    if findings:
        return findings
    return _validate_skill_files(files, bundle.name, expected_digest, discovery)


def validate_plugin(plugin_root: Path, expected_digest: str | None = None) -> list[Finding]:
    files, findings = inventory(plugin_root)
    if findings:
        return findings
    findings.extend(_check_lock(files, expected_digest))
    manifest_path = ".codex-plugin/plugin.json"
    if manifest_path not in files:
        return [*findings, Finding("PLUGIN_MANIFEST_MISSING", "error", "Missing plugin manifest")]
    try:
        manifest = _decode(files[manifest_path], PluginManifest)
    except (ValueError, UnicodeError, RecursionError):
        return [*findings, Finding("PLUGIN_MANIFEST_INVALID", "error", "Invalid plugin manifest")]
    if manifest.skills != "./skills/":
        findings.append(Finding("PLUGIN_SKILLS_INVALID", "error", "skills must be './skills/'"))
    skill_names = sorted({
        path.split("/")[1] for path in files
        if path.startswith("skills/") and len(path.split("/")) >= 3
    })
    if not skill_names:
        findings.append(Finding("PLUGIN_SKILLS_MISSING", "error", "Plugin must contain at least one skill"))
    allowed = {manifest_path, LOCK_NAME}
    for name in skill_names:
        prefix = f"skills/{name}/"
        child_files = {path[len(prefix):]: data for path, data in files.items() if path.startswith(prefix)}
        allowed.update(prefix + path for path in child_files)
        findings.extend(_validate_skill_files(child_files, name))
    if set(files) != allowed:
        findings.append(Finding("PLUGIN_FILE_SET_MISMATCH", "error", "Unexpected plugin files"))
    return findings


def validate_path(path: Path, expected_digest: str | None = None) -> list[Finding]:
    if (path / ".codex-plugin").exists():
        return validate_plugin(path, expected_digest)
    return validate_skill(path, expected_digest)
