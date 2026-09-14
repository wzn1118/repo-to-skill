from __future__ import annotations

import json
import re
import shutil
from dataclasses import asdict
from pathlib import Path, PurePosixPath

from r2s.domain import BuildResult, BundleReadiness, ClientProfile, DiscoveryIR, Finding, Procedure
from r2s.planner import plan
from r2s.serialization import canonical_json

SKILL_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
PORTABLE_PROFILE = ClientProfile("portable-agent-skills-v1", "portable", "1")
CODEX_PROFILE = ClientProfile("codex-plugin-skills-2026-09", "codex", "1", "1")


def slugify(value: str) -> str:
    parts = re.findall(r"[a-z0-9]+", value.lower().replace("_", "-"))
    return "-".join(parts)[:64].rstrip("-") or "repository-skill"


def _yaml_string(value: str) -> str:
    return json.dumps(" ".join(value.split()), ensure_ascii=False)


def _skill_bundle(
    discovery: DiscoveryIR,
    procedure: Procedure,
    output: Path,
) -> Path:
    command = procedure.steps[0].action
    skill_name = slugify(command)
    bundle = output / skill_name
    references = bundle / "references"
    references.mkdir(parents=True, exist_ok=True)
    claim_by_id = {claim.id: claim for claim in discovery.claims}
    evidence_by_id = {evidence.id: evidence for evidence in discovery.evidence}
    capability = next(
        item
        for item in discovery.capabilities
        if item.id == procedure.capability_ids[0]
    )
    option_claims = [
        claim_by_id[claim_id]
        for claim_id in capability.claim_ids
        if claim_id in claim_by_id and claim_by_id[claim_id].predicate == "supports_option"
    ]
    option_lines = [f"- `{claim.object['option']}`" for claim in option_claims]
    description = f"Use the {command} CLI when the user needs to {procedure.intent}."
    skill = (
        f"---\nname: {skill_name}\ndescription: {_yaml_string(description)}\n---\n\n"
        f"# {procedure.title}\n\n"
        "## Workflow\n\n"
        f"1. Treat `{command}` as the evidence-backed executable name; confirm it is available "
        "in the user's environment without assuming an installation method.\n"
        "2. Select only options listed in `references/cli.md` or arguments explicitly supplied "
        "by the user. Do not invent flags.\n"
        "3. Preview the complete invocation and identify its side effects before asking for "
        "execution approval.\n"
        "4. After execution, verify the user-requested result rather than relying only on the "
        "process exit code.\n\n"
        "See `references/cli.md` for statically discovered options and `references/provenance.md` "
        "for source evidence.\n"
    )
    (bundle / "SKILL.md").write_text(skill, encoding="utf-8", newline="\n")
    cli_reference = (
        f"# {command} CLI\n\n## Statically discovered options\n\n"
        + (
            "\n".join(option_lines)
            if option_lines
            else (
                "No options were statically discovered. Do not infer flags; obtain additional "
                "evidence or explicit user input before constructing an invocation."
            )
        )
        + "\n"
    )
    (references / "cli.md").write_text(cli_reference, encoding="utf-8", newline="\n")
    all_claim_ids = sorted(set(capability.claim_ids) | set(procedure.precondition_claim_ids))
    all_evidence_ids = sorted(
        {
            evidence_id
            for claim_id in all_claim_ids
            if claim_id in claim_by_id
            for evidence_id in claim_by_id[claim_id].evidence_ids
        }
    )
    (references / "provenance.md").write_text(
        "# Provenance\n\n"
        + "\n".join(f"- Claim `{claim_id}`" for claim_id in all_claim_ids)
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    provenance = {
        "schema_version": discovery.schema_version,
        "source_snapshot": asdict(discovery.snapshot),
        "artifact_path": "SKILL.md",
        "procedure": asdict(procedure),
        "artifact_claims": {
            "SKILL.md": [procedure.precondition_claim_ids[0]],
            "references/cli.md": [claim.id for claim in option_claims],
            "references/provenance.md": all_claim_ids,
        },
        "claims": [asdict(claim_by_id[claim_id]) for claim_id in all_claim_ids],
        "evidence": [asdict(evidence_by_id[evidence_id]) for evidence_id in all_evidence_ids],
    }
    (bundle / "PROVENANCE.json").write_text(canonical_json(provenance), encoding="utf-8")
    return bundle


def generate(
    discovery: DiscoveryIR,
    goal: str,
    run_root: Path,
    target: str,
    capability_ids: set[str] | None = None,
) -> BuildResult:
    profiles = {"portable": PORTABLE_PROFILE, "codex": CODEX_PROFILE}
    profile = profiles.get(target)
    if profile is None:
        finding = Finding("CLIENT_PROFILE_UNKNOWN", "error", f"Unsupported target: {target}")
        return BuildResult(target, None, (), BundleReadiness.REVIEW_REQUIRED, (finding,))
    generation_scope = "capability_delta" if capability_ids is not None else "full"
    procedures = plan(discovery, goal, capability_ids)
    if not procedures:
        finding = Finding(
            "NO_ACTIONABLE_CAPABILITY",
            "error",
            "No supported CLI entrypoint was found",
        )
        no_capability_findings = (*discovery.findings, finding)
        status = (
            BundleReadiness.REVIEW_REQUIRED
            if any(
                item.severity in {"error", "critical", "high"}
                for item in no_capability_findings[:-1]
            )
            else BundleReadiness.UNSUITABLE
        )
        return BuildResult(target, None, (), status, no_capability_findings)
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
        findings.extend(validate_skill(bundle))
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
            "skills": ["./skills/"],
        }
        (manifest_root / "plugin.json").write_text(canonical_json(manifest), encoding="utf-8")
        findings.extend(validate_plugin(plugin_root))
        root = plugin_root
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
                "findings": [asdict(item) for item in findings],
            }
        ),
        encoding="utf-8",
    )
    return result


def _frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---\n", 4)
    if end < 0:
        return {}
    result: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if ":" not in line:
            continue
        key, raw = line.split(":", 1)
        value = raw.strip()
        try:
            decoded = json.loads(value)
            result[key.strip()] = decoded if isinstance(decoded, str) else value
        except json.JSONDecodeError:
            result[key.strip()] = value
    return result


def validate_skill(bundle: Path) -> list[Finding]:
    findings: list[Finding] = []
    skill_path = bundle / "SKILL.md"
    provenance_path = bundle / "PROVENANCE.json"
    if not skill_path.is_file():
        return [Finding("SKILL_MISSING", "error", "SKILL.md is required", "SKILL.md")]
    text = skill_path.read_text(encoding="utf-8")
    metadata = _frontmatter(text)
    name = metadata.get("name", "")
    description = metadata.get("description", "")
    if not name or not description:
        findings.append(
            Finding(
                "INVALID_FRONTMATTER",
                "error",
                "name and description are required",
                "SKILL.md",
            )
        )
    if name and (
        not SKILL_NAME_RE.fullmatch(name)
        or len(name) > 64
        or name != bundle.name
    ):
        findings.append(
            Finding(
                "INVALID_SKILL_NAME",
                "error",
                "Skill name must match its directory and use lowercase hyphens",
                "SKILL.md",
            )
        )
    if len(description) > 1024:
        findings.append(
            Finding(
                "DESCRIPTION_TOO_LONG",
                "error",
                "Description exceeds 1024 characters",
                "SKILL.md",
            )
        )
    for match in re.findall(r"`(references/[^`]+)`", text):
        if not (bundle / PurePosixPath(match)).is_file():
            findings.append(
                Finding(
                    "REFERENCE_MISSING",
                    "error",
                    f"Missing reference: {match}",
                    "SKILL.md",
                )
            )
    if not provenance_path.is_file():
        findings.append(Finding("PROVENANCE_MISSING", "error", "PROVENANCE.json is required"))
    else:
        try:
            provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            findings.append(Finding("PROVENANCE_INVALID", "error", str(exc), "PROVENANCE.json"))
        else:
            claims = {claim["id"]: claim for claim in provenance.get("claims", [])}
            evidence = {item["id"]: item for item in provenance.get("evidence", [])}
            source_snapshot = provenance.get("source_snapshot", {})
            expected_commit = (
                source_snapshot.get("resolved_commit_sha")
                if source_snapshot.get("git_dirty") is False
                else None
            )
            procedure = provenance.get("procedure", {})
            used_claims = set(procedure.get("precondition_claim_ids", []))
            for step in procedure.get("steps", []):
                used_claims.update(step.get("claim_ids", []))
            artifact_claims = provenance.get("artifact_claims", {})
            if not isinstance(artifact_claims, dict):
                findings.append(
                    Finding(
                        "ARTIFACT_PROVENANCE_INVALID",
                        "error",
                        "artifact_claims must be an object",
                        "PROVENANCE.json",
                    )
                )
            else:
                for artifact_path, claim_ids in artifact_claims.items():
                    if artifact_path != "SKILL.md" and not (bundle / artifact_path).is_file():
                        findings.append(
                            Finding(
                                "ARTIFACT_PROVENANCE_INVALID",
                                "error",
                                f"Mapped artifact does not exist: {artifact_path}",
                                "PROVENANCE.json",
                            )
                        )
                    if isinstance(claim_ids, list):
                        used_claims.update(claim_ids)
            missing_claims = used_claims - claims.keys()
            missing_evidence = {
                evidence_id
                for claim_id in used_claims & claims.keys()
                for evidence_id in claims[claim_id].get("evidence_ids", [])
                if evidence_id not in evidence
            }
            if missing_claims:
                findings.append(
                    Finding(
                        "UNKNOWN_CLAIM",
                        "error",
                        f"Missing claims: {sorted(missing_claims)}",
                    )
                )
            if missing_evidence:
                findings.append(
                    Finding(
                        "UNKNOWN_EVIDENCE",
                        "error",
                        f"Missing evidence: {sorted(missing_evidence)}",
                    )
                )
            if expected_commit:
                mismatched = [
                    evidence_id
                    for evidence_id, item in evidence.items()
                    if item.get("source", {}).get("commit_sha") != expected_commit
                ]
                if mismatched:
                    findings.append(
                        Finding(
                            "EVIDENCE_COMMIT_MISMATCH",
                            "error",
                            f"Evidence does not match source commit: {mismatched}",
                        )
                    )
    return findings


def validate_plugin(plugin_root: Path) -> list[Finding]:
    manifest_path = plugin_root / ".codex-plugin" / "plugin.json"
    if not manifest_path.is_file():
        return [Finding("PLUGIN_MANIFEST_MISSING", "error", "Missing .codex-plugin/plugin.json")]
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [Finding("PLUGIN_MANIFEST_INVALID", "error", str(exc), ".codex-plugin/plugin.json")]
    findings: list[Finding] = []
    for key in ("name", "version", "description"):
        if not isinstance(manifest.get(key), str) or not manifest[key].strip():
            findings.append(
                Finding(
                    "PLUGIN_MANIFEST_INVALID",
                    "error",
                    f"Missing manifest field: {key}",
                )
            )
    skills = manifest.get("skills")
    if skills != ["./skills/"]:
        findings.append(Finding("PLUGIN_SKILLS_INVALID", "error", "skills must be ['./skills/']"))
    skills_root = plugin_root / "skills"
    if not skills_root.is_dir():
        findings.append(
            Finding(
                "PLUGIN_SKILLS_MISSING",
                "error",
                "Plugin skills directory is missing",
            )
        )
    else:
        for child in sorted(skills_root.iterdir()):
            if child.is_dir():
                findings.extend(validate_skill(child))
    return findings


def validate_path(path: Path) -> list[Finding]:
    if (path / ".codex-plugin" / "plugin.json").is_file():
        return validate_plugin(path)
    return validate_skill(path)


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
) -> tuple[Path | None, list[Finding], list[str]]:
    findings = validate_plugin(plugin_root)
    if findings:
        return None, findings, []
    for path in plugin_root.rglob("*"):
        if path.is_symlink():
            return (
                None,
                [
                    Finding(
                        "INSTALL_SYMLINK_REJECTED",
                        "error",
                        f"Plugin contains a symlink: {path.relative_to(plugin_root)}",
                    )
                ],
                [],
            )
    manifest = json.loads(
        (plugin_root / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    target = destination_root.resolve() / slugify(manifest["name"])
    destination = destination_root.resolve()
    try:
        target.relative_to(destination)
    except ValueError:
        return (
            None,
            [Finding("INSTALL_PATH_ESCAPE", "error", "Install path escapes destination")],
            [],
        )
    files = [
        path.relative_to(plugin_root).as_posix()
        for path in sorted(plugin_root.rglob("*"))
        if path.is_file()
    ]
    if target.exists():
        return (
            target,
            [
                Finding(
                    "INSTALL_TARGET_EXISTS",
                    "error",
                    f"Target already exists: {target}",
                )
            ],
            files,
        )
    if execute:
        destination.mkdir(parents=True, exist_ok=True)
        shutil.copytree(plugin_root, target)
    return target, [], files
