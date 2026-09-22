from __future__ import annotations

from dataclasses import asdict, replace
from pathlib import Path
from typing import Any, Literal

from r2s.command_graph import command_path
from r2s.domain import Claim, DiscoveryIR, Evidence, SourceLocation
from r2s.fact_contracts import parse_fact
from r2s.scanner import ScanResult
from r2s.serialization import stable_id


def add_trace(discovery: DiscoveryIR, scan: ScanResult, path: Path, start: int, end: int, kind: str, value: dict[str, Any]) -> str:
    source = scan.source_index[path]
    location = SourceLocation(path.relative_to(scan.root).as_posix(), "ast:" + kind, source.content_sha256 or "", start, end, scan.snapshot.resolved_commit_sha if scan.snapshot.git_dirty is False else None, source.blob_sha)
    identifier = stable_id("ev", [value, asdict(location), kind])
    if not any(item.id == identifier for item in discovery.evidence):
        discovery.evidence.append(Evidence(identifier, kind, value, value, location, kind + "@1", 0.9))
    return identifier


def add_parameter(discovery: DiscoveryIR, scan: ScanResult, root: Claim, path: Path, line: int, value: dict[str, Any], framework: str, hops: tuple[str, ...] = (), end_line: int | None = None) -> str:
    predicate: Literal["supports_option", "supports_argument", "supports_subcommand"] = "supports_subcommand" if "option" not in value and "argument" not in value else "supports_argument" if "argument" in value else "supports_option"
    source = scan.source_index[path]
    location = SourceLocation(path.relative_to(scan.root).as_posix(), f"ast:{framework}:{predicate}", source.content_sha256 or "", line, end_line or line, scan.snapshot.resolved_commit_sha if scan.snapshot.git_dirty is False else None, source.blob_sha)
    evidence_id = stable_id("ev", [value, asdict(location)])
    evidence = Evidence(evidence_id, "cli.ast_declaration", value, value, location, framework + "-ast@1", 0.9)
    identifiers = tuple(dict.fromkeys([*root.evidence_ids, *hops, evidence_id]))
    identifier = stable_id("cl", [predicate, value, identifiers])
    if any(claim.subject == root.object.get("command") and claim.predicate == predicate and claim.object.get("option") == value.get("option") and claim.object.get("argument") == value.get("argument") and command_path(claim) == tuple(value.get("command_path", ())) for claim in discovery.claims):
        return ""
    discovery.evidence.append(evidence)
    discovery.claims.append(Claim(identifier, str(root.object.get("command")), predicate, parse_fact(value), identifiers, 0.9, True))
    discovery.capabilities = [replace(capability, claim_ids=(*capability.claim_ids, identifier)) if root.id in capability.claim_ids else capability for capability in discovery.capabilities]
    return identifier


def shape(framework: str, arity: int | str, aliases: list[str], required: bool = False, unknown: tuple[str, ...] = ()) -> dict[str, Any]:
    return {"framework": framework, "rule": "static-cli-v1", "arity": arity, "required": required,
            "repeatable": False, "aliases": aliases, "exclusive_group": None, "group_required": None, "unknown_reasons": list(unknown)}
