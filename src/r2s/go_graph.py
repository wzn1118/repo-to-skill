from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from r2s.domain import Claim, DiscoveryIR, Finding
from r2s.scan_policy import path_role
from r2s.scanner import ScanResult
from r2s.static_parameters import add_parameter, shape
from r2s.syntax import field, literal, parse, text, walk


def analyze_commands(discovery: DiscoveryIR, scan: ScanResult, root: Claim, main_path: Path, module_root: Path, module: str | None) -> None:
    functions: dict[tuple[Path, str], tuple[Path, Any, dict[str, str]]] = {}
    for path in scan.analyzable_files:
        if path.suffix != ".go" or not path.is_relative_to(module_root) or path.name.endswith("_test.go") or path_role(path.relative_to(scan.root).as_posix()) == "test":
            continue
        source = scan.read_text(path)
        if re.search(r"^//(?:go:build| \+build) ", source, re.MULTILINE) or re.search(r"_(?:windows|linux|darwin|freebsd|amd64|arm64)\.go$", path.name):
            continue
        tree = parse(source, "go")
        if tree is None:
            continue
        imports = {}
        for node in walk(tree):
            if node.type == "import_spec":
                try:
                    value = literal(field(node, "path"))
                except ValueError:
                    continue
                name = text(field(node, "name")) or value.rsplit("/", 1)[-1]
                imports[name] = value
        for node in tree.named_children:
            if node.type == "function_declaration":
                key = (path.parent, text(field(node, "name")))
                if key in functions:
                    functions.pop(key)
                else:
                    functions[key] = (path, node, imports)
    if (main_path.parent, "main") not in functions:
        return
    visited: set[tuple[tuple[Path, str], frozenset[int]]] = set()
    pending: list[tuple[tuple[Path, str], set[int]]] = [((main_path.parent, "main"), set())]
    while pending and len(visited) < 128:
        key, tainted_positions = pending.pop(0)
        visit_key = (key, frozenset(tainted_positions))
        if visit_key in visited or key not in functions:
            continue
        visited.add(visit_key)
        path, function, imports = functions[key]
        if module:
            from r2s.go_cobra import expand_cobra

            expand_cobra(discovery, scan, root, functions, key, module_root, module)
        parameters: list[str] = []
        for parameter in field(function, "parameters").named_children:
            parameters.extend(text(child) for child in parameter.named_children if child.type == "identifier")
        tainted = {parameters[index] for index in tainted_positions if index < len(parameters)}
        consumers = set()
        for declaration in walk(field(function, "body")):
            if declaration.type != "short_var_declaration":
                continue
            right = field(declaration, "right")
            left = field(declaration, "left")
            if right is None or left is None or len(right.named_children) != 1 or right.named_children[0].type != "func_literal":
                continue
            body = right.named_children[0]
            indexes = [item for item in walk(body) if item.type == "index_expression" and text(field(item, "operand")) in tainted]
            increments = [item for item in walk(body) if item.type == "inc_statement"]
            loops = [item for item in walk(body) if item.type in {"for_statement", "range_clause"}]
            if len(indexes) == len(increments) == 1 and not loops and len(left.named_children) == 1:
                consumers.add(text(left.named_children[0]))
        for node in walk(field(function, "body")):
            if node.type == "short_var_declaration":
                right = field(node, "right")
                left = field(node, "left")
                if right is not None and left is not None and len(right.named_children) == len(left.named_children) == 1:
                    expression = right.named_children[0]
                    if expression.type == "index_expression" and text(field(expression, "operand")) in tainted:
                        tainted.add(text(left.named_children[0]))
            if node.type == "call_expression":
                called = field(node, "function")
                directory = path.parent
                name = text(called)
                if called.type == "selector_expression":
                    owner = text(field(called, "operand"))
                    imported = imports.get(owner, "")
                    name = text(field(called, "field"))
                    if module and imported.startswith(module + "/"):
                        directory = module_root / imported[len(module)+1:]
                    elif imported in {"flag", "github.com/spf13/pflag"}:
                        _flag(discovery, scan, root, path, node, name, imported)
                        continue
                    else:
                        continue
                arguments = field(node, "arguments").named_children
                positions = {index for index, argument in enumerate(arguments) if text(argument) in tainted or text(argument).startswith("os.Args[")}
                pending.append(((directory, name), positions))
            if node.type == "expression_switch_statement" and text(field(node, "value")) in tainted:
                for case in node.named_children:
                    if case.type != "expression_case":
                        continue
                    flags = []
                    for value in field(case, "value").named_children:
                        try:
                            flag = literal(value)
                        except ValueError:
                            continue
                        if isinstance(flag, str) and re.fullmatch(r"--?[A-Za-z0-9][\w-]*", flag):
                            flags.append(flag)
                    if not flags:
                        continue
                    body = next((child for child in case.named_children if child.type == "statement_list"), None)
                    arity: int | str = "unknown"
                    unknown: tuple[str, ...] = ("custom_argument_consumption",)
                    assignments = [item for item in walk(body) if item.type == "assignment_statement"] if body is not None else []
                    calls = [item for item in walk(body) if item.type == "call_expression"] if body is not None else []
                    if len(assignments) == 1 and not calls:
                        right = field(assignments[0], "right")
                        if right and len(right.named_children) == 1 and right.named_children[0].type in {"true", "false"}:
                            arity, unknown = 0, ()
                    if len([item for item in calls if text(field(item, "function")) in consumers]) == 1 and all(text(field(item, "function")) in consumers for item in calls):
                        arity, unknown = 1, ()
                    for flag in flags:
                        value = {"command": root.object.get("command"), "option": flag, "command_path": [], "shape": shape("go-switch", arity, flags, unknown=unknown)}
                        add_parameter(discovery, scan, root, path, case.start_point.row+1, value, "go-switch")
    if pending:
        discovery.findings.append(Finding("GO_AST_TRAVERSAL_LIMIT", "warning", "Go call graph remains partial", main_path.relative_to(scan.root).as_posix()))


def _flag(discovery: DiscoveryIR, scan: ScanResult, root: Claim, path: Path, node: Any, method: str, package: str) -> None:
    match = re.fullmatch(r"(String|Bool|Int|Int64|Float64|Uint|Duration)(Var)?(P)?", method)
    if not match:
        return
    arguments = field(node, "arguments").named_children
    offset = 1 if match.group(2) else 0
    try:
        name = literal(arguments[offset])
        default = literal(arguments[offset + (2 if match.group(3) else 1)])
    except (ValueError, IndexError):
        return
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9][\w-]*", name):
        return
    flag = ("-" if package == "flag" else "--") + name
    value_type = {"String": "str", "Bool": "bool", "Int": "int", "Int64": "int", "Float64": "float", "Uint": "int"}.get(match.group(1))
    if value_type is None:
        return
    value: dict[str, Any] = {"command": root.object.get("command"), "option": flag, "command_path": [],
             "shape": shape("go-flag", 0 if value_type == "bool" else 1, [flag]),
             "semantics": {"framework": "go-flag", "scope": "explicit_source_keywords", "default": default, "value_type": value_type}}
    try:
        add_parameter(discovery, scan, root, path, node.start_point.row+1, value, "go-flag")
    except ValueError:
        return
