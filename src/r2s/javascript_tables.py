from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from r2s.domain import Claim, DiscoveryIR, Evidence, SourceLocation
from r2s.scanner import ScanResult
from r2s.serialization import stable_id
from r2s.static_parameters import add_parameter, shape
from r2s.syntax import field, literal, parse, relative_import, text, walk


def analyze_tables(discovery: DiscoveryIR, scan: ScanResult, entry: Claim, target: Path) -> None:
    admitted = set(scan.source_index)
    visited: set[Path] = set()
    pending = [(target, entry.evidence_ids)]
    while pending and len(visited) < 64:
        path, hops = pending.pop(0)
        if path in visited:
            continue
        visited.add(path)
        tree = parse(scan.read_text(path), "javascript")
        if tree is None:
            continue
        imports = {}
        dynamic_loaders = set()
        for node in walk(tree):
            if node.type == "variable_declarator":
                value = field(node, "value")
                if value is not None and value.type == "new_expression" and text(field(value, "constructor")) == "Function":
                    arguments = field(value, "arguments").named_children
                    try:
                        values = [literal(argument) for argument in arguments]
                    except ValueError:
                        continue
                    if values == ["module", "return import(module)"]:
                        dynamic_loaders.add(text(field(node, "name")))
        for node in walk(tree):
            relative = None
            local = None
            try:
                if node.type == "import_statement":
                    relative = literal(field(node, "source"))
                    clause = next((child for child in node.named_children if child.type == "import_clause"), None)
                    local = next((text(child) for child in clause.named_children if child.type == "identifier"), None) if clause else None
                elif node.type == "call_expression" and text(field(node, "function")) in {"import", *dynamic_loaders}:
                    arguments = field(node, "arguments").named_children
                    if len(arguments) == 1:
                        relative = literal(arguments[0])
            except ValueError:
                continue
            if not isinstance(relative, str):
                continue
            resolved = relative_import(path, relative, admitted)
            if resolved is None:
                continue
            location = scan.source_index[path]
            source = SourceLocation(path.relative_to(scan.root).as_posix(), "ast:javascript:import", location.content_sha256 or "", node.start_point.row+1, node.end_point.row+1, scan.snapshot.resolved_commit_sha if scan.snapshot.git_dirty is False else None, location.blob_sha)
            value = {"import": relative, "target": resolved.relative_to(scan.root).as_posix()}
            identifier = stable_id("ev", [value, source.content_sha256, source.start_line])
            if not any(item.id == identifier for item in discovery.evidence):
                discovery.evidence.append(Evidence(identifier, "javascript.import", value, value, source, "javascript-table-graph@1", 0.9))
            chain = (*hops, identifier)
            if local:
                imports[local] = (resolved, chain)
            pending.append((resolved, chain))
        normalizations = [node for node in walk(tree) if node.type == "pair" and text(field(node, "key")) == "name" and text(field(node, "value")) == "option.cliName ?? dashify(option.name)"]
        if not normalizations:
            continue
        for node in walk(tree):
            if node.type != "call_expression" or text(field(node, "function")) != "normalizeOptionSettings":
                continue
            arguments = field(node, "arguments").named_children
            if len(arguments) != 1 or text(arguments[0]) not in imports:
                continue
            table_path, chain = imports[text(arguments[0])]
            _table(discovery, scan, entry, table_path, chain)


def _table(discovery: DiscoveryIR, scan: ScanResult, entry: Claim, path: Path, hops: tuple[str, ...]) -> None:
    tree = parse(scan.read_text(path), "javascript")
    if tree is None:
        return
    exports = [text(field(node, "value")) for node in tree.named_children if node.type == "export_statement"]
    objects = [field(node, "value") for node in walk(tree) if node.type == "variable_declarator" and text(field(node, "name")) in exports]
    for table in objects:
        if table is None or table.type != "object":
            continue
        for pair in table.named_children:
            if pair.type != "pair" or field(pair, "value").type != "object":
                continue
            name = text(field(pair, "key")).strip('"\'')
            fields: dict[str, Any] = {}
            children = {text(field(child, "key")): field(child, "value") for child in field(pair, "value").named_children if child.type == "pair"}
            for key in ("type", "default", "alias", "cliName"):
                if key in children:
                    try:
                        fields[key] = literal(children[key])
                    except ValueError:
                        pass
            if fields.get("type") not in {"boolean", "path", "int", "string", "choice"}:
                continue
            name = fields.get("cliName") or re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", name).lower()
            if not re.fullmatch(r"[a-z][a-z0-9-]*", name):
                continue
            option = "--" + name
            arity = 0 if fields["type"] == "boolean" else 1
            value = {"command": entry.object.get("command"), "option": option, "command_path": [],
                     "shape": shape("js-option-table", arity, [option], unknown=("custom_option_processing",) if "exception" in children else ())}
            semantics: dict[str, Any] = {"framework": "js-option-table", "scope": "explicit_source_keywords"}
            if fields["type"] == "choice":
                choices = children.get("choices")
                values = []
                if choices is not None and choices.type == "array":
                    for choice in choices.named_children:
                        try:
                            if choice.type == "object":
                                selected = [field(item, "value") for item in choice.named_children if item.type == "pair" and text(field(item, "key")) == "value"]
                                values.append(literal(selected[0]) if len(selected) == 1 else None)
                            else:
                                values.append(literal(choice))
                        except ValueError:
                            values.append(None)
                if values and all(isinstance(item, str) for item in values):
                    semantics["choices"] = values
                else:
                    value["shape"] = shape("js-option-table", arity, [option], unknown=("dynamic_choices",))
            if "default" in fields:
                semantics["default"] = fields["default"]
            kind = {"boolean": "bool", "path": "path", "int": "int", "string": "str"}.get(fields["type"])
            if kind:
                semantics["value_type"] = kind
            if len(semantics) > 2:
                value["semantics"] = semantics
            try:
                add_parameter(discovery, scan, entry, path, pair.start_point.row+1, value, "js-option-table", hops)
            except ValueError:
                continue
