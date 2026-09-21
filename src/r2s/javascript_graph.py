from __future__ import annotations

import re
from pathlib import Path

from r2s.domain import Claim, DiscoveryIR, Finding
from r2s.scanner import ScanResult
from r2s.static_parameters import add_parameter, shape
from r2s.syntax import field, literal, parse, text, walk


def analyze_commands(discovery: DiscoveryIR, scan: ScanResult, entry: Claim, target: Path) -> None:
    tree = parse(scan.read_text(target), "typescript" if target.suffix == ".ts" else "javascript")
    if tree is None:
        discovery.findings.append(Finding("JS_AST_UNAVAILABLE_OR_INVALID", "warning", "Install the analysis extra for bounded JS/TS declaration analysis", target.relative_to(scan.root).as_posix()))
        return
    from r2s.javascript_tables import analyze_tables

    analyze_tables(discovery, scan, entry, target)
    constructors = set()
    for node in tree.named_children:
        if node.type == "import_statement":
            try:
                module = literal(field(node, "source"))
            except ValueError:
                continue
            if module == "commander":
                for item in walk(node):
                    if item.type == "import_specifier" and text(field(item, "name")) == "Command":
                        constructors.add(text(field(item, "alias") or field(item, "name")))
    programs = set()
    for node in tree.named_children:
        if node.type == "lexical_declaration":
            for declaration in node.named_children:
                value = field(declaration, "value")
                if value is not None and value.type == "new_expression" and text(field(value, "constructor")) in constructors:
                    programs.add(text(field(declaration, "name")))
    calls = []
    parsed = set()
    for node in tree.named_children:
        if node.type != "expression_statement" or len(node.named_children) != 1:
            continue
        call = node.named_children[0]
        function = field(call, "function")
        if call.type != "call_expression" or function is None or function.type != "member_expression":
            continue
        owner = text(field(function, "object"))
        method = text(field(function, "property"))
        if owner not in programs:
            continue
        if method in {"parse", "parseAsync"}:
            parsed.add(owner)
        elif owner not in parsed and method in {"option", "requiredOption", "argument"}:
            calls.append((owner, method, call))
    positions = 0
    for owner, method, call in calls:
        if owner not in parsed:
            continue
        arguments = field(call, "arguments").named_children
        if not arguments:
            continue
        try:
            declaration = literal(arguments[0])
        except ValueError:
            continue
        if not isinstance(declaration, str):
            continue
        if method == "argument":
            match = re.fullmatch(r"([<\[])([A-Za-z][A-Za-z0-9_-]*)(\.\.\.)?[>\]]", declaration)
            if not match:
                continue
            required = match.group(1) == "<"
            arity = ("+" if required else "*") if match.group(3) else (1 if required else "?")
            value = {"command": entry.object.get("command"), "command_path": [], "argument": match.group(2), "position": positions, "shape": shape("commander", arity, [], required)}
            positions += 1
        else:
            match = re.fullmatch(r"(?P<flags>--?[A-Za-z][\w-]*(?:[, |]+--?[A-Za-z][\w-]*)*)(?:\s+(?P<value><[\w-]+>|\[[\w-]+\]))?", declaration)
            if not match:
                continue
            flags = re.findall(r"--?[A-Za-z][\w-]*", match.group("flags"))
            placeholder = match.group("value")
            arity = "?" if placeholder and placeholder.startswith("[") else 1 if placeholder else 0
            for flag in flags:
                value = {"command": entry.object.get("command"), "command_path": [], "option": flag,
                         "shape": shape("commander", arity, flags, method == "requiredOption", ("custom_processor",) if len(arguments) > 2 else ())}
                add_parameter(discovery, scan, entry, target, call.start_point.row + 1, value, "commander")
            continue
        add_parameter(discovery, scan, entry, target, call.start_point.row + 1, value, "commander")
