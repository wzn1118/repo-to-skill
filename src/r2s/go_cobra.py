from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from r2s.domain import Claim, DiscoveryIR
from r2s.scanner import ScanResult
from r2s.static_parameters import add_parameter, shape
from r2s.syntax import field, literal, text, unconditional, walk


def expand_cobra(discovery: DiscoveryIR, scan: ScanResult, root: Claim, functions: dict[tuple[Path, str], tuple[Path, Any, dict[str, str]]], key: tuple[Path, str], module_root: Path, module: str, path: tuple[str, ...] = (), parent: Claim | None = None, visited: frozenset[tuple[Path, str]] = frozenset()) -> None:
    if key in visited or key not in functions or len(path) > 8 or len(visited) > 100:
        return
    filename, function, imports = functions[key]
    constructors = []
    for node in walk(field(function, "body")):
        if node.type != "short_var_declaration" or not unconditional(node, function):
            continue
        left, right = field(node, "left"), field(node, "right")
        if left is None or right is None or len(left.named_children) != 1:
            continue
        for value in walk(right):
            if value.type != "composite_literal":
                continue
            kind = field(value, "type")
            if kind is None or text(field(kind, "name")) != "Command" or imports.get(text(field(kind, "package"))) != "github.com/spf13/cobra":
                continue
            for item in field(value, "body").named_children:
                if item.type == "keyed_element" and text(field(item, "key")) == "Use":
                    try:
                        use = literal(field(item, "value").named_children[0])
                    except (ValueError, IndexError):
                        continue
                    if isinstance(use, str):
                        constructors.append((text(left.named_children[0]), use, value))
    if len(constructors) != 1:
        return
    owner, use, declaration = constructors[0]
    name = use.split()[0] if use.split() else ""
    if not re.fullmatch(r"[A-Za-z0-9][\w-]*", name):
        return
    if parent is None:
        if name != root.object.get("command"):
            return
        declared = root
    else:
        path = (*path, name)
        identifier = add_parameter(discovery, scan, root, filename, declaration.start_point.row+1,
                                   {"command": root.object.get("command"), "command_path": list(path)}, "cobra", parent.evidence_ids)
        if not identifier:
            return
        declared = next(claim for claim in discovery.claims if claim.id == identifier)
    required = set()
    for node in walk(field(function, "body")):
        if node.type == "call_expression" and unconditional(node, function) and text(field(node, "function")) == owner + ".MarkFlagRequired":
            try:
                required.add(literal(field(node, "arguments").named_children[0]))
            except (ValueError, IndexError):
                pass
    for node in walk(field(function, "body")):
        if node.type != "call_expression" or not unconditional(node, function):
            continue
        called = field(node, "function")
        call_name = text(called)
        if call_name == owner + ".AddCommand":
            for argument in field(node, "arguments").named_children:
                if argument.type != "call_expression":
                    continue
                factory = field(argument, "function")
                directory, symbol = filename.parent, text(factory)
                if factory.type == "selector_expression":
                    imported = imports.get(text(field(factory, "operand")), "")
                    if not imported.startswith(module + "/"):
                        continue
                    directory = module_root / imported[len(module)+1:]
                    symbol = text(field(factory, "field"))
                expand_cobra(discovery, scan, root, functions, (directory, symbol), module_root, module, path, declared, visited | {key})
        match = re.fullmatch(re.escape(owner) + r"\.(Flags|PersistentFlags)\(\)\.(String|Bool|Int|StringSlice)(Var)?(P)?", call_name)
        if not match:
            continue
        arguments = field(node, "arguments").named_children
        offset = 1 if match.group(3) else 0
        try:
            flag_name = literal(arguments[offset])
        except (ValueError, IndexError):
            continue
        if not isinstance(flag_name, str) or not re.fullmatch(r"[A-Za-z0-9][\w-]*", flag_name):
            continue
        option = "--" + flag_name
        unknown = ("inherited_scope_not_modeled",) if match.group(1) == "PersistentFlags" else ()
        aliases = [option]
        default_index = offset + (2 if match.group(4) else 1)
        if match.group(4):
            try:
                shorthand = literal(arguments[offset+1])
                if isinstance(shorthand, str) and re.fullmatch(r"[A-Za-z0-9]", shorthand):
                    aliases.append("-" + shorthand)
            except (ValueError, IndexError):
                unknown = (*unknown, "dynamic_shorthand")
        if match.group(2) == "StringSlice":
            unknown = (*unknown, "slice_conversion_not_modeled")
        semantics = {"framework": "cobra", "scope": "explicit_source_keywords", "value_type": {"Bool": "bool", "Int": "int"}.get(match.group(2), "str")}
        try:
            semantics["default"] = literal(arguments[default_index])
        except (ValueError, IndexError):
            pass
        value = {"command": root.object.get("command"), "command_path": list(path), "option": option,
                 "shape": shape("cobra", 0 if match.group(2) == "Bool" else 1, aliases, flag_name in required, unknown), "semantics": semantics}
        add_parameter(discovery, scan, root, filename, node.start_point.row+1, value, "cobra", declared.evidence_ids)
