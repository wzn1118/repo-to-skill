from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from r2s.domain import Claim, DiscoveryIR
from r2s.scanner import ScanResult
from r2s.static_parameters import add_parameter, add_trace, shape
from r2s.syntax import field, literal, parse, text, walk

HELPER = '''package demo
func helper() {
 *__pointer = __default
 __value := &__enum{__storage: __pointer, __options: __choices}
 __flag := __command.Flags().VarPF(__value, __name, __short, __usage)
 _ = __command.RegisterFlagCompletionFunc(__name, func(__command *__cobra.Command, __args []string, __complete string) ([]string, __cobra.ShellCompDirective) {
  return __choices, __cobra.ShellCompDirectiveNoFileComp
 })
 return __flag
}
'''
SETTER = '''package demo
func (__receiver *__enum) Set(__input string) error {
 if !__contains(__input, __receiver.__options) {
  return __fmt.Errorf(__literal_message, __format(__receiver.__options))
 }
 *__receiver.__storage = __input
 return nil
}
'''
INCLUSION = '''package demo
func __contains(__input string, __choices []string) bool {
 for _, __choice := range __choices {
  if __strings.EqualFold(__choice, __input) { return true }
 }
 return false
}
'''
FORMATTER = '''package demo
func __format(__choices []string) string {
 return __fmt.Sprintf(__literal_format, __strings.Join(__choices, __literal_separator))
}
'''


def _children(node: Any) -> list[Any]:
    return [child for child in node.children if child.type != "comment" and (child.is_named or text(child))]


def _match(pattern: Any, node: Any, captures: dict[str, Any]) -> bool:
    if pattern is None or node is None:
        return pattern is node
    name = text(pattern)
    if pattern.type in {"identifier", "field_identifier", "type_identifier", "package_identifier"} and name.startswith("__"):
        if name.startswith("__literal_"):
            try:
                if not isinstance(literal(node), str):
                    return False
            except ValueError:
                return False
        elif node.type not in {"identifier", "field_identifier", "type_identifier", "package_identifier"}:
            return False
        if name in captures:
            return text(captures[name]) == text(node)
        captures[name] = node
        return True
    if pattern.type != node.type:
        return False
    expected, actual = _children(pattern), _children(node)
    if len(expected) != len(actual):
        return False
    if not expected:
        return text(pattern) == text(node)
    return all(_match(left, right, captures) for left, right in zip(expected, actual, strict=True))


@lru_cache(maxsize=32)
def _template(source: str) -> Any:
    tree = parse(source, "go")
    if tree is None:
        return None
    return next((node for node in tree.named_children if node.type in {"function_declaration", "method_declaration"}), None)


def _parameters(function: Any) -> list[tuple[Any, str]]:
    result: list[tuple[Any, str]] = []
    for parameter in field(function, "parameters").named_children:
        kind = text(field(parameter, "type"))
        result.extend((child, kind) for child in parameter.named_children if child.type == "identifier")
    return result


def _proof(function: Any, imports: dict[str, str], tree: Any, functions: dict[tuple[Path, str], tuple[Path, Any, dict[str, str]]], filename: Path, peers: list[Any] | None = None) -> tuple[dict[str, Any], list[tuple[Path, Any]]] | None:
    parameters = _parameters(function)
    if len(parameters) != 7:
        return None
    command_type = parameters[0][1].removeprefix("*").split(".")
    if not parameters[0][1].startswith("*") or len(command_type) != 2 or command_type[1] != "Command" or imports.get(command_type[0]) != "github.com/spf13/cobra":
        return None
    if [kind for _, kind in parameters[1:]] != ["*string", "string", "string", "string", "[]string", "string"]:
        return None
    roles = ("__command", "__pointer", "__name", "__short", "__default", "__choices", "__usage")
    initial = dict(zip(roles, [name for name, _ in parameters], strict=True))
    captures = dict(initial)
    matched = _match(field(_template(HELPER), "body"), field(function, "body"), captures)
    if not matched:
        captures = dict(initial)
        formatted = HELPER.replace("__short, __usage)", '__short, __fmt.Sprintf(__literal_usage, __usage, __format(__choices)))')
        if not _match(field(_template(formatted), "body"), field(function, "body"), captures):
            return None
    if imports.get(text(captures["__cobra"])) != "github.com/spf13/cobra":
        return None
    if text(captures["__cobra"]) in {text(name) for name, _kind in parameters}:
        return None
    enum_name = text(captures["__enum"])
    types = [node for node in walk(tree) if node.type == "type_spec" and text(field(node, "name")) == enum_name]
    if len(types) != 1:
        return None
    enum_type = field(types[0], "type")
    fields = [(text(field(node, "name")), text(field(node, "type"))) for node in walk(enum_type) if node.type == "field_declaration"]
    if fields != [(text(captures["__storage"]), "*string"), (text(captures["__options"]), "[]string")]:
        return None
    methods = {}
    for node in tree.named_children:
        if node.type != "method_declaration":
            continue
        receiver = field(node, "receiver").named_children
        if len(receiver) == 1 and text(field(receiver[0], "type")) in {enum_name, "*" + enum_name}:
            name = text(field(node, "name"))
            if name in methods:
                return None
            methods[name] = node
    if set(methods) != {"Set", "String", "Type"}:
        return None
    for peer in peers or []:
        for node in peer.named_children:
            if node.type == "method_declaration" and any(text(field(receiver, "type")) in {enum_name, "*" + enum_name} for receiver in field(node, "receiver").named_children):
                return None
        if any(node.type == "type_spec" and text(field(node, "name")) == enum_name for node in walk(peer)):
            return None
    evidence = [(filename, function), (filename, types[0])]
    shared = {name: captures[name] for name in ("__enum", "__storage", "__options")}
    setter = dict(shared)
    if not _match(_template(SETTER), methods["Set"], setter):
        return None
    for method, returned in (("String", "*__receiver.__storage"), ("Type", '"string"')):
        pattern = _template(f"package demo\nfunc (__receiver *__enum) {method}() string {{ return {returned} }}")
        if not _match(pattern, methods[method], dict(shared)):
            return None
    evidence.extend((filename, node) for node in methods.values())
    for key, pattern in (("__contains", INCLUSION), ("__format", FORMATTER)):
        resolved = functions.get((filename.parent, text(setter[key])))
        if resolved is None:
            return None
        helper_path, helper, helper_imports = resolved
        bound: dict[str, Any] = {}
        if not _match(_template(pattern), helper, bound):
            return None
        for alias, package in (("__strings", "strings"), ("__fmt", "fmt")):
            if alias in bound and (helper_imports.get(text(bound[alias])) != package or text(bound[alias]) in {text(parameter) for parameter, _kind in _parameters(helper)}):
                return None
        evidence.append((helper_path, helper))
    if imports.get(text(setter["__fmt"])) != "fmt" or text(setter["__fmt"]) in {text(setter["__receiver"]), text(setter["__input"])}:
        return None
    if "__format" in captures and (text(captures["__format"]) != text(setter["__format"]) or imports.get(text(captures["__fmt"])) != "fmt" or text(captures["__fmt"]) in {text(name) for name, _kind in parameters}):
        return None
    return captures, evidence


def wrapped_enum(discovery: DiscoveryIR, scan: ScanResult, root: Claim, filename: Path, call: Any, imports: dict[str, str], functions: dict[tuple[Path, str], tuple[Path, Any, dict[str, str]]], module_root: Path, module: str, owner: str, path: tuple[str, ...], declared: Claim, required: dict[str, str]) -> None:
    called = field(call, "function")
    directory, name = filename.parent, text(called)
    if called.type == "selector_expression":
        package = imports.get(text(field(called, "operand")), "")
        if not package.startswith(module + "/"):
            return
        directory, name = module_root / package[len(module)+1:], text(field(called, "field"))
    resolved = functions.get((directory, name))
    arguments = field(call, "arguments").named_children
    if resolved is None or len(arguments) != 7 or text(arguments[0]) != owner:
        return
    helper_path, function, helper_imports = resolved
    tree = function
    while tree.parent is not None:
        tree = tree.parent
    peers: list[Any] = []
    for candidate in scan.source_index:
        if candidate.parent != helper_path.parent or candidate == helper_path or candidate.suffix != ".go" or candidate.name.endswith("_test.go"):
            continue
        peer = parse(scan.read_text(candidate), "go")
        if peer is None or len(peers) >= 64:
            return
        peers.append(peer)
    proof = _proof(function, helper_imports, tree, functions, helper_path, peers)
    if proof is None:
        return
    try:
        flag_name, shorthand, default = [literal(argument) for argument in arguments[2:5]]
        choices_node = arguments[5]
        if choices_node.type != "composite_literal" or text(field(choices_node, "type")) != "[]string":
            return
        choices = [literal(item.named_children[0]) for item in field(choices_node, "body").named_children]
    except (ValueError, IndexError):
        return
    if not isinstance(flag_name, str) or not re.fullmatch(r"[A-Za-z0-9][\w-]*", flag_name) or not isinstance(shorthand, str) or shorthand and not re.fullmatch(r"[A-Za-z0-9]", shorthand):
        return
    if not isinstance(default, str) or not 1 <= len(choices) <= 32 or any(not isinstance(choice, str) or not choice.isascii() for choice in choices):
        return
    aliases = ["--" + flag_name, *(["-" + shorthand] if shorthand else [])]
    value = {"command": root.object.get("command"), "command_path": list(path), "option": aliases[0],
             "shape": shape("cobra", 1, aliases, required=flag_name in required),
             "semantics": {"framework": "cobra", "scope": "explicit_source_keywords", "value_type": "str", "choices": choices, "default": default, "validation": "ascii_case_insensitive_choices"}}
    from r2s.fact_contracts import parse_fact

    try:
        parse_fact(value)
    except ValueError:
        return
    traces = [add_trace(discovery, scan, source, node.start_point.row+1, node.end_point.row+1, "go.enum_validation", {"symbol": text(field(node, "name")), "rule": "literal_enum_helper_v1"}) for source, node in proof[1]]
    requirement = (required[flag_name],) if flag_name in required else ()
    add_parameter(discovery, scan, root, filename, call.start_point.row+1, value, "cobra", (*declared.evidence_ids, *traces, *requirement), call.end_point.row+1)
