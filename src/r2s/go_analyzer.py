from __future__ import annotations

import re
from dataclasses import asdict
from pathlib import Path

from r2s.domain import Capability, Claim, DiscoveryIR, Evidence, Finding, SourceLocation
from r2s.policy import is_safe_command
from r2s.scanner import ScanResult
from r2s.serialization import file_sha256, stable_id

MODULE_RE = re.compile(r"^\s*module\s+(\S+)\s*$", re.MULTILINE)
PACKAGE_MAIN_RE = re.compile(r"^\s*package\s+main\s*$", re.MULTILINE)
FUNC_MAIN_RE = re.compile(r"^\s*func\s+main\s*\(", re.MULTILINE)
FLAG_RE = re.compile(
    r"(?P<prefix>(?:flag|pflag)\.|\.Flags\(\)\.)"
    r"(?:String|Bool|Int|Int64|Uint|Duration|Float64|StringSlice|StringVar|BoolVar)"
    r"\s*\(\s*\"(?P<name>[A-Za-z0-9][A-Za-z0-9_.-]*)\""
)


def _location(
    scan_result: ScanResult,
    path: Path,
    pointer: str,
    line: int | None = None,
) -> SourceLocation:
    relative = path.relative_to(scan_result.root).as_posix()
    entry = next(
        (item for item in scan_result.inventory if item.path == relative),
        None,
    )
    return SourceLocation(
        path=relative,
        pointer=pointer,
        content_sha256=file_sha256(path),
        start_line=line,
        end_line=line,
        commit_sha=(
            scan_result.snapshot.resolved_commit_sha
            if scan_result.snapshot.git_dirty is False
            else None
        ),
        blob_sha=entry.blob_sha if entry else None,
    )


def _mask_non_code(source: str, preserve_strings: bool) -> str:
    output: list[str] = []
    index = 0
    state = "code"
    quote = ""
    while index < len(source):
        char = source[index]
        next_char = source[index + 1] if index + 1 < len(source) else ""
        if state == "code":
            if char == "/" and next_char == "/":
                output.extend("  ")
                index += 2
                state = "line-comment"
                continue
            if char == "/" and next_char == "*":
                output.extend("  ")
                index += 2
                state = "block-comment"
                continue
            if char in {'"', "'", "`"}:
                quote = char
                state = "string"
                output.append(char if preserve_strings else " ")
            else:
                output.append(char)
            index += 1
            continue
        if state == "line-comment":
            output.append("\n" if char == "\n" else " ")
            if char == "\n":
                state = "code"
            index += 1
            continue
        if state == "block-comment":
            if char == "*" and next_char == "/":
                output.extend("  ")
                index += 2
                state = "code"
            else:
                output.append("\n" if char == "\n" else " ")
                index += 1
            continue
        output.append(char if preserve_strings else ("\n" if char == "\n" else " "))
        if char == "\\" and quote != "`" and next_char:
            output.append(next_char if preserve_strings else " ")
            index += 2
            continue
        if char == quote:
            state = "code"
        index += 1
    return "".join(output)


def _line_number(source: str, offset: int) -> int:
    return source.count("\n", 0, offset) + 1


def _module_name(go_mod: Path) -> str | None:
    match = MODULE_RE.search(go_mod.read_text(encoding="utf-8"))
    return match.group(1) if match else None


def _command_for(module_root: Path, source: Path, module: str | None) -> str | None:
    relative = source.relative_to(module_root)
    if len(relative.parts) >= 3 and relative.parts[0] == "cmd":
        return relative.parts[1]
    if len(relative.parts) == 1:
        candidate = module.rsplit("/", 1)[-1] if module else module_root.name
        version_match = re.fullmatch(r"(.+)/v[0-9]+", module or "")
        return version_match.group(1).rsplit("/", 1)[-1] if version_match else candidate
    return None


def _go_modules(scan_result: ScanResult) -> list[Path]:
    return sorted(
        path
        for path in scan_result.analyzable_files
        if path.name == "go.mod"
    )


def _go_role(repository_root: Path, main_path: Path, command: str) -> str:
    relative = main_path.relative_to(repository_root).parts[:-1]
    lowered = {part.casefold() for part in relative}
    if lowered & {"test", "tests", "testdata", "fixture", "fixtures", "e2e", "dev"}:
        return "test"
    if command.casefold() in {"release", "gen-docs", "gen-doc", "sleepit", "testapp"}:
        return "developer"
    return "product"


def analyze_go(discovery: DiscoveryIR, scan_result: ScanResult) -> None:
    modules = _go_modules(scan_result)
    for go_mod in modules:
        module_root = go_mod.parent
        module_name = _module_name(go_mod)
        discovery.languages.append("go")
        go_files = [
            path
            for path in scan_result.analyzable_files
            if path.suffix == ".go" and path.is_relative_to(module_root)
        ]
        main_files: list[tuple[Path, str, str]] = []
        for path in sorted(go_files):
            try:
                source = path.read_text(encoding="utf-8")
            except UnicodeDecodeError as exc:
                discovery.findings.append(
                    Finding(
                        "GO_PARSE_FAILED",
                        "warning",
                        str(exc),
                        path.relative_to(scan_result.root).as_posix(),
                    )
                )
                continue
            lexical_source = _mask_non_code(source, preserve_strings=True)
            structural_source = _mask_non_code(source, preserve_strings=False)
            if PACKAGE_MAIN_RE.search(structural_source) and FUNC_MAIN_RE.search(
                structural_source
            ):
                main_files.append((path, lexical_source, structural_source))
        discovery.repository_types.append("cli" if main_files else "library")
        module_source = _location(scan_result, go_mod, "$.module", 1)
        module_value = {"module": module_name or "", "workspace": module_root.name}
        module_evidence_id = stable_id(
            "ev",
            ["go.module", module_value, asdict(module_source)],
        )
        discovery.evidence.append(
            Evidence(
                module_evidence_id,
                "go.module",
                module_value,
                module_value,
                module_source,
                "go-mod@1",
                1.0 if module_name else 0.7,
            )
        )
        for main_path, lexical_source, structural_source in main_files:
            command = _command_for(module_root, main_path, module_name)
            if command is None:
                continue
            if not is_safe_command(command):
                discovery.findings.append(
                    Finding(
                        "UNSAFE_COMMAND_NAME",
                        "error",
                        f"Unsafe command name derived from Go module: {command}",
                        main_path.relative_to(scan_result.root).as_posix(),
                    )
                )
                continue
            relative_target = main_path.parent.relative_to(scan_result.root).as_posix() or "."
            main_match = FUNC_MAIN_RE.search(structural_source)
            main_source = _location(
                scan_result,
                main_path,
                "go:func:main",
                _line_number(structural_source, main_match.start())
                if main_match
                else None,
            )
            main_value = {
                "command": command,
                "target": relative_target,
                "workspace": module_root.relative_to(scan_result.root).as_posix() or ".",
                "role": _go_role(scan_result.root, main_path, command),
            }
            main_evidence_id = stable_id(
                "ev",
                ["go.main", main_value, asdict(main_source)],
            )
            discovery.evidence.append(
                Evidence(
                    main_evidence_id,
                    "go.main",
                    main_value,
                    main_value,
                    main_source,
                    "go-lexical@1",
                    0.9,
                )
            )
            claim_id = stable_id(
                "cl",
                [
                    "repository",
                    "provides_cli",
                    main_value,
                    module_evidence_id,
                    main_evidence_id,
                ],
            )
            if main_value["role"] != "product":
                discovery.findings.append(
                    Finding(
                        "NON_PRODUCT_ENTRYPOINT_SKIPPED",
                        "info",
                        f"Skipped {main_value['role']} Go entrypoint: {command}",
                        main_path.relative_to(scan_result.root).as_posix(),
                    )
                )
                continue
            discovery.claims.append(
                Claim(
                    claim_id,
                    "repository",
                    "provides_cli",
                    main_value,
                    (module_evidence_id, main_evidence_id),
                    0.9,
                    True,
                )
            )
            option_claim_ids: list[str] = []
            for match in FLAG_RE.finditer(lexical_source):
                name = match.group("name")
                prefix = match.group("prefix")
                option = f"--{name}" if prefix != "flag." else f"-{name}"
                option_source = _location(
                    scan_result,
                    main_path,
                    f"go:flag:{name}",
                    _line_number(lexical_source, match.start()),
                )
                option_value = {"command": command, "option": option}
                option_evidence_id = stable_id(
                    "ev",
                    ["go.cli_option", option_value, asdict(option_source)],
                )
                discovery.evidence.append(
                    Evidence(
                        option_evidence_id,
                        "go.cli_option",
                        {"name": name, "prefix": prefix},
                        option_value,
                        option_source,
                        "go-lexical@1",
                        0.85,
                    )
                )
                option_claim_id = stable_id(
                    "cl",
                    [command, "supports_option", option_value, option_evidence_id],
                )
                option_claim_ids.append(option_claim_id)
                discovery.claims.append(
                    Claim(
                        option_claim_id,
                        command,
                        "supports_option",
                        option_value,
                        (option_evidence_id,),
                        0.85,
                        True,
                    )
                )
            capability_id = stable_id(
                "cap",
                ["invoke_cli", command, relative_target, claim_id, option_claim_ids],
            )
            discovery.capabilities.append(
                Capability(
                    capability_id,
                    f"Use the {command} CLI",
                    f"Invoke the {command} command",
                    (claim_id, *option_claim_ids),
                )
            )
