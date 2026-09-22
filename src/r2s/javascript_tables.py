from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from r2s.domain import Claim, DiscoveryIR, Finding
from r2s.javascript_symbols import JavaScriptGraph, Resolved, property_name
from r2s.javascript_table_flow import flows
from r2s.scanner import ScanResult
from r2s.static_parameters import add_parameter, add_trace, shape
from r2s.syntax import field, literal, text


def _properties(node: Any) -> dict[str, Any] | None:
    if node is None or node.type != "object":
        return None
    result = {}
    for item in node.named_children:
        if item.type == "comment":
            continue
        key = property_name(field(item, "key"))
        if item.type != "pair" or key is None or key in result:
            return None
        result[key] = field(item, "value")
    return result


def _pure_exception(node: Any) -> bool:
    if node.type != "arrow_function" or any(child.type == "async" for child in node.children):
        return False
    parameter = field(node, "parameter")
    if parameter is None:
        parameters = field(node, "parameters")
        parameter = parameters.named_children[0] if parameters is not None and len(parameters.named_children) == 1 else None
    if parameter is None or parameter.type != "identifier":
        return False

    def pure(expression: Any) -> bool:
        if expression is None:
            return False
        if expression.type == "parenthesized_expression":
            return len(expression.named_children) == 1 and pure(expression.named_children[0])
        if expression.type == "identifier":
            return text(expression) == text(parameter)
        if expression.type == "unary_expression":
            return text(field(expression, "operator")) in {"typeof", "!"} and pure(field(expression, "argument"))
        if expression.type == "binary_expression":
            return text(field(expression, "operator")) in {"===", "!==", "&&", "||"} and pure(field(expression, "left")) and pure(field(expression, "right"))
        try:
            literal(expression)
            return True
        except ValueError:
            return False

    return pure(field(node, "body"))


def _parameter(entry: Claim, key: str, node: Any) -> dict[str, Any] | None:
    fields = _properties(node)
    if fields is None:
        return None
    values = {}
    for attribute in ("type", "name", "default", "alias", "cliName", "array", "deprecated"):
        if attribute not in fields:
            continue
        try:
            values[attribute] = literal(fields[attribute])
        except ValueError:
            pass
    kind = values.get("type")
    if kind not in {"boolean", "path", "int", "string", "choice"}:
        return None
    name: Any = values.get("name", key)
    if "name" in fields and "name" not in values:
        return None
    if "cliName" in fields:
        name = values.get("cliName")
    elif isinstance(name, str) and re.fullmatch(r"[a-z][a-z0-9]*(?:[A-Z][a-z0-9]+)*|[a-z][a-z0-9]*(?:-[a-z0-9]+)+", name):
        name = re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", name).lower()
    else:
        return None
    if not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9-]*", name):
        return None
    option = "--" + name
    aliases = [option]
    unknown = []
    if "alias" in fields:
        alias = values.get("alias")
        if isinstance(alias, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]*", alias):
            aliases.append(("-" if len(alias) == 1 else "--") + alias)
        else:
            unknown.append("dynamic_alias")
    if "array" in fields and values.get("array") is not False:
        unknown.append("array_arity_not_modeled")
    if "redirect" in fields:
        unknown.append("redirect_processing_not_modeled")
    if "exception" in fields and not _pure_exception(fields["exception"]):
        unknown.append("custom_option_processing")
    semantics: dict[str, Any] = {"framework": "js-option-table", "scope": "explicit_source_keywords", "value_type": {"boolean": "bool", "path": "path", "int": "int"}.get(kind, "str")}
    if kind == "choice":
        declared = fields.get("choices")
        choices: list[Any] = []
        if declared is not None and declared.type == "array":
            for choice in declared.named_children:
                if choice.type == "comment":
                    continue
                if choice.type == "object":
                    properties = _properties(choice)
                    if properties is None or "redirect" in properties:
                        choices.append(None)
                        continue
                    choice = properties.get("value")
                try:
                    choices.append(literal(choice))
                except ValueError:
                    choices.append(None)
        if choices and all(isinstance(item, str) for item in choices):
            semantics["choices"] = choices
        else:
            unknown.append("dynamic_choices")
    if "default" in values:
        semantics["default"] = values["default"]
    return {"command": entry.object.get("command"), "option": option, "command_path": [],
            "shape": shape("js-option-table", 0 if kind == "boolean" else 1, aliases, unknown=tuple(unknown)), "semantics": semantics}


def _table(entry: Claim, table: Resolved) -> list[tuple[Any, dict[str, Any]]]:
    properties = _properties(table.node)
    if properties is None:
        return []
    result = []
    for name, node in properties.items():
        value = _parameter(entry, name, node)
        if value is not None:
            result.append((node, value))
    return result


def analyze_tables(discovery: DiscoveryIR, scan: ScanResult, entry: Claim, target: Path) -> None:
    graph = JavaScriptGraph(scan)
    selected = flows(graph, target)
    if len(selected) != 1:
        if selected:
            discovery.findings.append(Finding("JS_OPTION_FLOW_AMBIGUOUS", "warning", "Multiple declarative argument flows require review", target.relative_to(scan.root).as_posix()))
        return
    flow = selected[0]
    traces = list(entry.evidence_ids)
    for site in flow.sites:
        traces.append(add_trace(discovery, scan, site.path, site.node.start_point.row+1, site.node.end_point.row+1, site.kind, {"rule": "normalized-minimist-flow-v1", "syntax": site.node.type}))
    for path in flow.manifests:
        traces.append(add_trace(discovery, scan, path, 1, len(scan.read_text(path).splitlines()), "javascript.framework_dependencies", {"rule": "normalized-minimist-flow-v1"}))
    hops = tuple(dict.fromkeys(traces))
    parameters = [(table, node, value) for table in flow.tables for node, value in _table(entry, table)]
    aliases = [alias for _, _, value in parameters for alias in value["shape"]["aliases"]]
    if len(aliases) != len(set(aliases)):
        discovery.findings.append(Finding("JS_OPTION_FLOW_ALIAS_COLLISION", "warning", "Competing normalized option spellings require review", target.relative_to(scan.root).as_posix()))
        return
    for table, node, value in parameters:
        try:
            add_parameter(discovery, scan, entry, table.path, node.start_point.row+1, value, "js-option-table", hops, node.end_point.row+1)
        except ValueError:
            continue
    site = flow.positional_site
    value = {"command": entry.object.get("command"), "command_path": [], "argument": flow.positional, "position": 0,
             "shape": shape("js-option-table", "*", [], required=False),
             "semantics": {"framework": "js-option-table", "scope": "explicit_source_keywords", "value_type": "str"}}
    add_parameter(discovery, scan, entry, site.path, site.node.start_point.row+1, value, "js-option-table", hops, site.node.end_point.row+1)
