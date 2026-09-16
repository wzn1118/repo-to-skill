from __future__ import annotations

import ast
import configparser
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any, Final

from r2s.command_graph import command_specs
from r2s.domain import (
    Capability,
    Claim,
    DiscoveryIR,
    Evidence,
    Finding,
    RepositorySnapshot,
    SourceLocation,
)
from r2s.fact_contracts import parse_fact
from r2s.policy import is_safe_command, is_safe_python_target
from r2s.python_graph import Hop, PythonGraph
from r2s.scan_policy import ScanPolicy, scan_coverage
from r2s.scanner import ScanResult, scan
from r2s.serialization import stable_id
from r2s.toml_compat import loads as toml_loads

SCHEMA_VERSION: Final = "1.3.0"


class _CaseSensitiveConfigParser(configparser.ConfigParser):
    def optionxform(self, optionstr: str) -> str:
        return optionstr


def _line_for(scan_result: ScanResult, path: Path, needle: str) -> int | None:
    for index, line in enumerate(scan_result.read_text(path).splitlines(), start=1):
        if needle in line:
            return index
    return None


def _location(
    scan_result: ScanResult,
    path: Path,
    pointer: str,
    start_line: int | None = None,
    end_line: int | None = None,
) -> SourceLocation:
    relative = path.relative_to(scan_result.root).as_posix()
    inventory_entry = scan_result.source_index[path]
    return SourceLocation(
        path=relative,
        pointer=pointer,
        content_sha256=inventory_entry.content_sha256 or "",
        start_line=start_line,
        end_line=end_line,
        commit_sha=(
            scan_result.snapshot.resolved_commit_sha
            if scan_result.snapshot.git_dirty is False
            else None
        ),
        blob_sha=inventory_entry.blob_sha,
    )


def _script_entries(scan_result: ScanResult) -> list[tuple[str, str, Path, str]]:
    root = scan_result.root
    entries: list[tuple[str, str, Path, str]] = []
    pyproject = root / "pyproject.toml"
    if pyproject in scan_result.source_index:
        data = toml_loads(scan_result.read_text(pyproject))
        tables: list[tuple[dict[str, Any], str]] = []
        project = data.get("project", {})
        if isinstance(project, dict):
            scripts = project.get("scripts", {})
            if isinstance(scripts, dict):
                tables.append((scripts, "$.project.scripts"))
        poetry = data.get("tool", {}).get("poetry", {})
        if isinstance(poetry, dict):
            scripts = poetry.get("scripts", {})
            if isinstance(scripts, dict):
                tables.append((scripts, "$.tool.poetry.scripts"))
        for table, pointer in tables:
            for command, target in table.items():
                if isinstance(command, str) and isinstance(target, str):
                    entries.append((command, target, pyproject, f"{pointer}.{command}"))
    setup_cfg = root / "setup.cfg"
    if setup_cfg in scan_result.source_index:
        parser = _CaseSensitiveConfigParser()
        parser.read_string(scan_result.read_text(setup_cfg))
        section = "options.entry_points"
        if parser.has_option(section, "console_scripts"):
            for line in parser.get(section, "console_scripts").splitlines():
                if "=" in line:
                    command, target = (part.strip() for part in line.split("=", 1))
                    entries.append(
                        (
                            command,
                            target,
                            setup_cfg,
                            "[options.entry_points].console_scripts",
                        )
                    )
    ordered = sorted(
        entries,
        key=lambda item: (
            item[0].casefold(),
            item[1],
            0 if item[2].name == "pyproject.toml" else 1,
            item[2].as_posix(),
            item[3],
        ),
    )
    unique: dict[tuple[str, str], tuple[str, str, Path, str]] = {}
    for entry in ordered:
        unique.setdefault((entry[0], entry[1]), entry)
    return list(unique.values())


def _python_evidence(
    scan_result: ScanResult, path: Path, node: ast.AST, kind: str,
    value: dict[str, Any], pointer: str, raw_value: dict[str, Any] | None = None,
) -> Evidence:
    source = _location(scan_result, path, pointer, getattr(node, "lineno", None), getattr(node, "end_lineno", None))
    return Evidence(
        stable_id("ev", [kind, value, asdict(source)]), kind,
        raw_value if raw_value is not None else value, value, source, "python-entrypoint-graph@1", 0.95,
    )


def _hop_evidence(scan_result: ScanResult, hop: Hop) -> Evidence:
    value = {"from_module": hop.source.module, "from_symbol": hop.source.name, "to_module": hop.target.module, "to_symbol": hop.target.name}
    return _python_evidence(scan_result, hop.path, hop.node, hop.kind, value, f"ast:{hop.kind}:{hop.source.name}:{hop.target.module}:{hop.target.name}")


def _initialize_discovery(scan_result: ScanResult) -> DiscoveryIR:
    root = scan_result.root
    discovery = DiscoveryIR(
        SCHEMA_VERSION,
        scan_result.snapshot,
        inventory=list(scan_result.inventory),
    )
    coverage = scan_coverage(scan_result.inventory, scan_result.snapshot.scan_policy_id)
    if not coverage["complete_within_policy"]:
        discovery.findings.append(Finding(
            "SCAN_INCOMPLETE", "error",
            f"Content budget excluded {coverage['budget_skipped_files']} files; affected paths and reasons remain in the inventory. Unscanned capabilities are unknown.",
        ))
    sensitive_count = sum(
        1
        for item in scan_result.inventory
        if item.reason in {"SENSITIVE_PATH_SKIPPED", "SENSITIVE_DIRECTORY_SKIPPED"}
    )
    if sensitive_count:
        discovery.findings.append(
            Finding(
                "SENSITIVE_INPUT_SKIPPED",
                "warning",
                f"Skipped {sensitive_count} sensitive path(s) under the active scan policy",
            )
        )
    license_path = next(
        (
            root / name
            for name in ("LICENSE", "LICENSE.txt", "LICENSE.md", "COPYING")
            if root / name in scan_result.source_index
        ),
        None,
    )
    if license_path is None:
        discovery.findings.append(
            Finding(
                "LICENSE_MISSING",
                "error",
                "No root license file was detected; generated artifacts are local-review only",
            )
        )
    else:
        license_source = _location(
            scan_result,
            license_path,
            "$",
            1,
            None,
        )
        license_value = {"path": license_path.name}
        license_evidence_id = stable_id(
            "ev",
            ["repository.license_file", license_value, asdict(license_source)],
        )
        discovery.evidence.append(
            Evidence(
                license_evidence_id,
                "repository.license_file",
                license_value,
                license_value,
                license_source,
                "root-license@1",
                0.8,
            )
        )
        license_claim_id = stable_id(
            "cl",
            ["repository", "has_license_file", license_value, license_evidence_id],
        )
        discovery.claims.append(
            Claim(
                license_claim_id,
                "repository",
                "has_license_file",
                parse_fact(license_value),
                (license_evidence_id,),
                0.8,
                False,
            )
        )
    return discovery


def analyze_python(discovery: DiscoveryIR, scan_result: ScanResult) -> None:
    root = scan_result.root
    script_entries = _script_entries(scan_result)
    if root / "pyproject.toml" in scan_result.source_index or root / "setup.cfg" in scan_result.source_index:
        discovery.languages.append("python")
        discovery.repository_types.append("cli" if script_entries else "library")
    for command, target, manifest, pointer in script_entries:
        if not is_safe_command(command):
            discovery.findings.append(
                Finding(
                    "UNSAFE_COMMAND_NAME",
                    "error",
                    f"Unsafe command name in manifest: {command}",
                    manifest.relative_to(root).as_posix(),
                )
            )
            continue
        clean_target = target.split("[", 1)[0].strip()
        if ":" not in clean_target:
            discovery.findings.append(
                Finding(
                    "INVALID_ENTRYPOINT",
                    "warning",
                    f"Unsupported entrypoint: {target}",
                    manifest.name,
                )
            )
            continue
        module, symbol = (part.strip() for part in clean_target.split(":", 1))
        if not is_safe_python_target(module, symbol):
            discovery.findings.append(
                Finding(
                    "UNSAFE_PYTHON_ENTRYPOINT",
                    "error",
                    f"Unsafe Python entrypoint target: {clean_target}",
                    manifest.relative_to(root).as_posix(),
                )
            )
            continue
        source = _location(
            scan_result,
            manifest,
            pointer,
            _line_for(scan_result, manifest, command),
            _line_for(scan_result, manifest, command),
        )
        normalized = {"command": command, "module": module, "symbol": symbol}
        entry_id = stable_id("ev", ["manifest.entrypoint", normalized, asdict(source)])
        discovery.evidence.append(
            Evidence(
                entry_id,
                "manifest.entrypoint",
                {command: target},
                normalized,
                source,
                "python-manifest@2",
                1.0,
            )
        )
        entry_evidence_ids = [entry_id]
        option_evidence: list[tuple[Evidence, tuple[str, ...]]] = []
        graph = PythonGraph(scan_result).analyze(module, symbol)
        for code in sorted(graph.diagnostics):
            discovery.findings.append(Finding(code, "warning", f"Static Python entrypoint analysis for {command}: {code}; unresolved branches do not supply option facts.", source.path))
        entry = graph.entrypoint
        if entry is None:
            discovery.findings.append(
                Finding(
                    "ENTRYPOINT_SYMBOL_UNRESOLVED",
                    "warning",
                    f"Static symbol resolution unavailable: {module}:{symbol}",
                    source.path,
                )
            )
        else:
            chain = [_hop_evidence(scan_result, hop) for hop in entry.hops]
            symbol_value = {"module": entry.ref.module, "symbol": entry.ref.name, "kind": type(entry.node).__name__}
            chain.append(_python_evidence(scan_result, entry.path, entry.node, "python.symbol", symbol_value, f"ast:symbol:{entry.ref.name}"))
            discovery.evidence.extend(chain)
            entry_evidence_ids.extend(item.id for item in chain)
        subcommand_ids: list[str] = []
        subcommand_evidence: dict[tuple[str, ...], tuple[str, ...]] = {(): tuple(entry_evidence_ids)}
        for declared in sorted(graph.commands, key=lambda item: (len(item.command_path), item.command_path)):
            chain = [_hop_evidence(scan_result, hop) for hop in declared.hops]
            declared_value = {"command": command, "command_path": list(declared.command_path)}
            item = _python_evidence(scan_result, declared.path, declared.call, "cli.subcommand", declared_value, f"ast:subcommand:{':'.join(declared.command_path)}")
            discovery.evidence.extend([*chain, item])
            identifiers = tuple(dict.fromkeys([*subcommand_evidence[declared.command_path[:-1]], *[hop.id for hop in chain], item.id]))
            subcommand_evidence[declared.command_path] = identifiers
            declared_id = stable_id("cl", [command, "supports_subcommand", declared_value, identifiers])
            discovery.claims.append(Claim(declared_id, command, "supports_subcommand", parse_fact(declared_value), identifiers, 0.95, True))
            subcommand_ids.append(declared_id)
        seen_options: set[tuple[tuple[str, ...], str]] = set()
        for option in graph.options:
            key = (option.command_path, option.option)
            if key in seen_options:
                continue
            seen_options.add(key)
            chain = [_hop_evidence(scan_result, hop) for hop in option.hops]
            symbol_value = {"module": option.owner.module, "symbol": option.owner.name, "kind": type(option.scope).__name__}
            chain.append(_python_evidence(scan_result, option.path, option.scope, "python.symbol", symbol_value, f"ast:symbol:{option.owner.name}"))
            value = {"command": command, "option": option.option, "command_path": list(option.command_path)}
            item = _python_evidence(
                scan_result, option.path, option.call, "cli.option", value,
                f"ast:bound-option:{option.owner.module}:{option.owner.name}:{option.option}",
                {**value, "framework": option.framework, "declarations": [argument.value for argument in option.call.args if isinstance(argument, ast.Constant) and isinstance(argument.value, str)]},
            )
            discovery.evidence.extend([*chain, item])
            identifiers = tuple(dict.fromkeys([*subcommand_evidence[option.command_path], *[hop.id for hop in chain], item.id]))
            option_evidence.append((item, identifiers))
        claim_value = {"command": command, "target": clean_target}
        claim_id = stable_id("cl", ["repository", "provides_cli", claim_value, entry_evidence_ids])
        discovery.claims.append(
            Claim(
                claim_id,
                "repository",
                "provides_cli",
                parse_fact(claim_value),
                tuple(entry_evidence_ids),
                1.0,
                True,
            )
        )
        option_claim_ids: list[str] = []
        for item, identifiers in option_evidence:
            option_claim_id = stable_id(
                "cl",
                [command, "supports_option", item.normalized_value, identifiers],
            )
            option_claim_ids.append(option_claim_id)
            discovery.claims.append(
                Claim(
                    option_claim_id,
                    command,
                    "supports_option",
                    parse_fact(item.normalized_value),
                    identifiers,
                    item.confidence,
                    True,
                )
            )
        capability_id = stable_id("cap", ["invoke_cli", command, claim_id, subcommand_ids, option_claim_ids])
        discovery.capabilities.append(
            Capability(
                capability_id,
                f"Use the {command} CLI",
                f"Invoke the {command} command",
                (claim_id, *subcommand_ids, *option_claim_ids),
            )
        )
def _resolve_command_conflicts(discovery: DiscoveryIR) -> None:
    by_command: dict[str, list[Claim]] = {}
    for claim in discovery.claims:
        if claim.predicate == "provides_cli" and claim.status == "supported":
            command = str(claim.object.get("command", ""))
            by_command.setdefault(command.casefold(), []).append(claim)
    conflicted_ids: set[str] = set()
    for command, claims in by_command.items():
        identities = {
            (
                str(claim.object.get("target", "")),
                str(claim.object.get("workspace", "")),
            )
            for claim in claims
        }
        if len(identities) < 2:
            continue
        conflicted_ids.update(claim.id for claim in claims)
        discovery.findings.append(
            Finding(
                "COMMAND_CONFLICT",
                "error",
                f"Multiple entrypoints claim the command name: {command}",
            )
        )
    if conflicted_ids:
        discovery.claims = [
            replace(claim, status="conflicted")
            if claim.id in conflicted_ids
            else claim
            for claim in discovery.claims
        ]


def _normalize_classification(discovery: DiscoveryIR) -> None:
    discovery.languages = sorted(set(discovery.languages))
    discovery.repository_types = sorted(set(discovery.repository_types))
    unique_evidence: dict[str, Evidence] = {}
    for item in discovery.evidence:
        existing = unique_evidence.get(item.id)
        if existing is not None and existing != item:
            raise ValueError("EVIDENCE_ID_COLLISION")
        unique_evidence.setdefault(item.id, item)
    discovery.evidence = list(unique_evidence.values())


def discover(
    root_value: str | Path,
    snapshot: RepositorySnapshot | None = None,
    committed_blob_oids: dict[str, str] | None = None,
    scan_policy: ScanPolicy | None = None,
) -> DiscoveryIR:
    scan_result = scan(root_value, snapshot, committed_blob_oids, scan_policy)
    discovery = _initialize_discovery(scan_result)
    from r2s.go_analyzer import analyze_go
    from r2s.javascript_analyzer import analyze_javascript

    analyze_python(discovery, scan_result)
    analyze_javascript(discovery, scan_result)
    analyze_go(discovery, scan_result)
    _resolve_command_conflicts(discovery)
    _normalize_classification(discovery)
    discovery.commands = command_specs(discovery.claims)
    return discovery
