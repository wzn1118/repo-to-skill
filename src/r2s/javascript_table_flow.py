from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from r2s import javascript_table_rules as rules
from r2s.javascript_patterns import function_match, match, template
from r2s.javascript_symbols import JavaScriptGraph, Resolved, Site, statements
from r2s.syntax import field, literal, relative_import, text, unconditional, walk


@dataclass(frozen=True)
class TableFlow:
    tables: tuple[Resolved, ...]
    sites: tuple[Site, ...]
    manifests: tuple[Path, ...]
    positional: str
    positional_site: Site


def local_names(node: Any) -> set[str]:
    names: set[str] = set()

    def bind(pattern: Any) -> None:
        if pattern is None:
            return
        if pattern.type in {"identifier", "shorthand_property_identifier_pattern"}:
            names.add(text(pattern))
        elif pattern.type in {"assignment_pattern", "object_assignment_pattern"}:
            bind(field(pattern, "left"))
        elif pattern.type == "pair_pattern":
            bind(field(pattern, "value"))
        elif pattern.type in {"formal_parameters", "object_pattern", "array_pattern", "rest_pattern", "required_parameter", "optional_parameter"}:
            for child in pattern.named_children:
                bind(child)

    for child in walk(node):
        selected = None
        if child.type == "variable_declarator":
            selected = field(child, "name")
        elif child.type in {"formal_parameters", "required_parameter", "optional_parameter"}:
            selected = child
        if selected is not None:
            bind(selected)
        if child.type == "arrow_function" and field(child, "parameter") is not None:
            names.add(text(field(child, "parameter")))
    return names


def assigned_names(node: Any) -> set[str]:
    names = set()
    for child in statements(node):
        if child.type not in {"assignment_expression", "augmented_assignment_expression", "update_expression"}:
            continue
        selected = field(child, "left") or field(child, "argument")
        while selected is not None and selected.type in {"member_expression", "subscript_expression"}:
            selected = field(selected, "object")
        if selected is not None:
            names.add(text(selected))
    return names


class TableProof:
    def __init__(self, graph: JavaScriptGraph):
        self.graph = graph
        self.sites: list[Site] = []
        self.manifests: set[Path] = set()
        self.support: Resolved | None = None
        self.converter: Resolved | None = None

    def prove(self, resolved: Resolved | None, rule: str) -> dict[str, Any] | None:
        if resolved is None or resolved.external or resolved.namespace:
            return None
        captured = function_match(rule, resolved.node)
        if captured is None:
            return None
        module = self.graph.module(resolved.path)
        reserved = {"Object", "Array", "Number", "Boolean", "Error", "Promise", "Set"}
        if module is None or reserved & (module.bindings.keys() | local_names(resolved.node)):
            return None
        self.sites.extend((*resolved.sites, Site(resolved.path, resolved.node, "javascript.option_flow")))
        return captured

    def symbol(self, scope: Resolved, node: Any) -> Resolved | None:
        if text(node) in local_names(scope.node):
            return None
        return self.graph.resolve(scope.path, node)

    def external(self, scope: Resolved, node: Any, package: str, member: str) -> bool:
        resolved = self.symbol(scope, node)
        if resolved is None or resolved.external != (package, member):
            return False
        directory = scope.path.parent
        while directory.is_relative_to(self.graph.scan.root):
            manifest = directory / "package.json"
            if manifest in self.graph.admitted:
                try:
                    payload = json.loads(self.graph.scan.read_text(manifest))
                except (ValueError, TypeError):
                    return False
                if not isinstance(payload, dict) or any(not isinstance(payload.get(key, {}), dict) for key in ("devDependencies", "dependencies")):
                    return False
                dependencies = {**payload.get("devDependencies", {}), **payload.get("dependencies", {})}
                version = dependencies.get(package)
                if payload.get("name") == package or not isinstance(version, str) or not version.strip() or any(marker in version for marker in (":", "/", "\\", "@")):
                    return False
                self.manifests.add(manifest)
                self.sites.extend(resolved.sites)
                return True
            directory = directory.parent
        return False

    def detail(self, resolved: Resolved | None) -> bool:
        captured = self.prove(resolved, rules.DETAIL_NORMALIZER)
        return bool(captured and resolved and self.external(resolved, captured["__dashify"], "dashify", "default"))

    def normalize_values(self, resolved: Resolved | None) -> bool:
        captured = self.prove(resolved, rules.CLI_NORMALIZER)
        if not captured or resolved is None:
            return False
        normalizer = self.symbol(resolved, captured["__normalize"])
        normalized = self.prove(normalizer, rules.VALUE_NORMALIZER)
        if not normalized or normalizer is None or not self.external(normalizer, normalized["__library"], "vnopts", "*"):
            return False
        schema_list = self.symbol(normalizer, normalized["__create"])
        schemas = self.prove(schema_list, rules.SCHEMA_LIST)
        if not schemas or schema_list is None or not self.external(schema_list, schemas["__library"], "vnopts", "*"):
            return False
        factory = self.symbol(schema_list, schemas["__convert"])
        schema = self.prove(factory, rules.SCHEMA_FACTORY)
        return bool(schema and factory and self.external(factory, schema["__library"], "vnopts", "*"))

    def parser(self, resolved: Resolved | None) -> bool:
        captured = self.prove(resolved, rules.ARGUMENT_PARSER)
        if not captured or resolved is None or not self.external(resolved, captured["__camel"], "camelcase", "default"):
            return False
        if self.prove(self.symbol(resolved, captured["__pick"]), rules.PICK_FIELDS) is None:
            return False
        options = self.prove(self.symbol(resolved, captured["__create"]), rules.MINIMIST_OPTIONS)
        wrapper = self.symbol(resolved, captured["__minimist"])
        wrapped = self.prove(wrapper, rules.MINIMIST_WRAPPER)
        if options is None or not wrapped or wrapper is None or not self.external(wrapper, wrapped["__minimist"], "minimist", "default"):
            return False
        placeholder = self.symbol(wrapper, wrapped["__placeholder"])
        if placeholder is None:
            return False
        try:
            if literal(placeholder.node) is not None:
                return False
        except ValueError:
            return False
        self.sites.extend(placeholder.sites)
        return self.normalize_values(self.symbol(resolved, captured["__normalize"]))

    def provider(self, resolved: Resolved | None) -> tuple[Resolved, ...]:
        captured = self.prove(resolved, rules.CONTEXT_PROVIDER)
        if not captured or resolved is None:
            return ()
        converter = self.symbol(resolved, captured["__convert"])
        converted = self.prove(converter, rules.CONTEXT_OPTIONS)
        if not converted or converter is None:
            return ()
        api_mapper = self.symbol(converter, converted["__convert"])
        mapped = self.prove(api_mapper, rules.API_CONVERTER)
        if not mapped or api_mapper is None:
            return ()
        detail = self.symbol(api_mapper, mapped["__normalize"])
        if not self.detail(detail):
            return ()
        cli_list = self.symbol(converter, converted["__cli"])
        if cli_list is None or cli_list.node.type != "call_expression":
            return ()
        cli_pattern = field(template("const result = __normalize(__table).map((__option) => __detail(__option));").named_children[0], "value")
        cli: dict[str, Any] = {}
        if not match(cli_pattern, cli_list.node, cli):
            return ()
        cli_scope = Resolved(cli_list.path, cli_list.node)
        cli_detail = self.graph.resolve(cli_list.path, cli["__detail"])
        if cli_detail is None or detail is None or (cli_detail.path, cli_detail.node) != (detail.path, detail.node):
            return ()
        normalize_cli = self.graph.resolve(cli_scope.path, cli["__normalize"])
        if self.prove(normalize_cli, rules.TABLE_NORMALIZER) is None:
            return ()
        cli_table = self.graph.resolve(cli_scope.path, cli["__table"])
        if cli_table is None or cli_table.node.type != "object":
            return ()
        self.sites.extend((*cli_list.sites, *cli_detail.sites, *cli_table.sites))
        support_call = self.symbol(resolved, captured["__getSupport"])
        if support_call is None or support_call.node.type != "call_expression":
            return ()
        arguments = field(support_call.node, "arguments").named_children
        if len(arguments) != 2:
            return ()
        try:
            if literal(arguments[1]) != 0:
                return ()
        except ValueError:
            return ()
        wrapped = self.graph.resolve(support_call.path, field(support_call.node, "function"))
        if self.prove(wrapped, rules.PLUGIN_WRAPPER) is None:
            return ()
        support = self.graph.resolve(support_call.path, arguments[0])
        supported = self.prove(support, rules.SUPPORT_PROVIDER)
        if not supported or support is None:
            return ()
        if self.prove(self.symbol(support, supported["__collect"]), rules.COLLECT_CHOICES) is None:
            return ()
        normalize_core = self.symbol(support, supported["__normalize"])
        if normalize_core is None or normalize_cli is None or (normalize_core.path, normalize_core.node) != (normalize_cli.path, normalize_cli.node):
            return ()
        core_table = self.symbol(support, supported["__core"])
        if core_table is None or core_table.node.type != "object":
            return ()
        self.sites.extend((*support_call.sites, *normalize_core.sites, *core_table.sites))
        self.support, self.converter = support, converter
        return (cli_table, core_table)

    def initial_parser(self, init: Resolved, node: Any, parser: Resolved | None) -> bool:
        resolved = self.symbol(init, node)
        captured = self.prove(resolved, rules.INITIAL_PARSER)
        if not captured or resolved is None or parser is None:
            return False
        selected = self.symbol(resolved, captured["__parse"])
        if selected is None or (selected.path, selected.node) != (parser.path, parser.node):
            return False
        module = self.graph.module(resolved.path)
        link = module.bindings.get(text(captured["__detailed"])) if module else None
        if link is None or link.properties != ("detailedOptions",) or link.node.type != "call_expression" or field(link.node, "arguments").named_children:
            return False
        context = self.graph.resolve(resolved.path, field(link.node, "function"))
        base = self.prove(context, rules.BASE_CONTEXT)
        if not base or context is None:
            return False
        for name, expected in (("__getSupport", self.support), ("__convert", self.converter)):
            actual = self.symbol(context, base[name])
            if actual is None or expected is None or (actual.path, actual.node) != (expected.path, expected.node):
                return False
            self.sites.extend(actual.sites)
        self.sites.append(Site(resolved.path, link.site, "javascript.initial_parse"))
        return True


def _called_functions(graph: JavaScriptGraph, scope: Resolved) -> list[Resolved]:
    body = field(scope.node, "body") if scope.node.type in {"function_declaration", "function_expression"} else scope.node
    nodes = list(statements(body))
    loaders = set()
    for node in nodes:
        if node.type != "variable_declarator":
            continue
        value = field(node, "value")
        if value is None or value.type != "new_expression" or text(field(value, "constructor")) != "Function":
            continue
        try:
            arguments = [literal(item) for item in field(value, "arguments").named_children]
        except ValueError:
            continue
        if arguments == ["module", "return import(module)"]:
            loaders.add(text(field(node, "name")))
    module = graph.module(scope.path)
    if module is None:
        return []
    if "Function" in module.bindings or "Function" in local_names(scope.node):
        loaders.clear()
    loaders.difference_update(assigned_names(body))
    calls = []
    for node in nodes:
        if node.type != "call_expression":
            continue
        called, arguments = field(node, "function"), field(node, "arguments").named_children
        resolved = None
        if not arguments and text(called) not in local_names(scope.node):
            resolved = graph.resolve(scope.path, called)
        if called.type == "member_expression" and text(field(called, "property")) == "then" and len(arguments) == 1:
            imported = field(called, "object")
            callback = arguments[0]
            if imported.type != "call_expression" or text(field(imported, "function")) not in {"import", *loaders} or callback.type not in {"function_expression", "arrow_function"}:
                continue
            parameters = field(callback, "parameters")
            callback_body = field(callback, "body")
            content = [child for child in callback_body.named_children if child.type != "comment"]
            if parameters is None or len(parameters.named_children) != 1 or len(content) != 1 or content[0].type != "return_statement":
                continue
            returned = content[0].named_children[0]
            function = field(returned, "function")
            if returned.type != "call_expression" or function.type != "member_expression" or text(field(function, "object")) != text(parameters.named_children[0]) or field(returned, "arguments").named_children:
                continue
            try:
                import_args = field(imported, "arguments").named_children
                path = relative_import(scope.path, literal(import_args[0]), graph.admitted) if len(import_args) == 1 else None
            except ValueError:
                continue
            if path is not None:
                resolved = graph.exported(path, text(field(function, "property")))
        if resolved is not None and resolved.node is not None and resolved.node.type == "function_declaration":
            calls.append(Resolved(resolved.path, resolved.node, (*scope.sites, Site(scope.path, node, "javascript.call"), *resolved.sites)))
    return calls


def entry_functions(graph: JavaScriptGraph, target: Path) -> list[Resolved]:
    module = graph.module(target)
    if module is None:
        return []
    pending = [Resolved(target, module.tree)]
    visited: set[tuple[Path, int]] = set()
    result = []
    while pending and len(visited) < 64:
        scope = pending.pop(0)
        key = (scope.path, scope.node.start_byte)
        if key in visited:
            continue
        visited.add(key)
        result.append(scope)
        pending.extend(_called_functions(graph, scope))
    return result


def flows(graph: JavaScriptGraph, target: Path) -> list[TableFlow]:
    result = []
    for scope in entry_functions(graph, target):
        if scope.node.type != "function_declaration":
            continue
        parameters = field(scope.node, "parameters").named_children
        if len(parameters) != 1 or text(parameters[0]).replace(" ", "") != "rawArguments=process.argv.slice(2)":
            continue
        module = graph.module(scope.path)
        if module is None or "process" in module.bindings or "process" in local_names(scope.node):
            continue
        body = field(scope.node, "body")
        if "rawArguments" in assigned_names(body):
            continue
        if any(node.type == "call_expression" and field(node, "function").type == "member_expression" and text(field(field(node, "function"), "object")) == "rawArguments" for node in statements(body)):
            continue
        for declaration in statements(body):
            if declaration.type != "variable_declarator" or not unconditional(declaration, scope.node):
                continue
            value = field(declaration, "value")
            if value is None or value.type != "new_expression":
                continue
            arguments = field(value, "arguments").named_children
            constructor = graph.resolve(scope.path, field(value, "constructor"))
            if len(arguments) != 1 or text(arguments[0]).replace(" ", "") != "{rawArguments,logger}" or constructor is None or constructor.node.type != "class_declaration":
                continue
            owner = text(field(declaration, "name"))
            replacements = {owner, owner + ".rawArguments", owner + ".detailedOptions", owner + ".init"}
            if any(node.type in {"assignment_expression", "augmented_assignment_expression", "update_expression"} and text(field(node, "left") or field(node, "argument")) in replacements for node in statements(body)) or text(field(value, "constructor")) in local_names(scope.node):
                continue
            if not any(node.type == "call_expression" and text(field(node, "function")) == owner + ".init" and not field(node, "arguments").named_children and unconditional(node, scope.node) for node in statements(body)):
                continue
            methods = {text(field(node, "name")): node for node in field(constructor.node, "body").named_children if node.type == "method_definition"}
            initializer = methods.get("constructor")
            if function_match("function construct({rawArguments, logger}) {this.rawArguments=rawArguments;this.logger=logger;}", initializer) is None:
                continue
            proof = TableProof(graph)
            proof.sites.extend((*scope.sites, *constructor.sites, Site(scope.path, declaration)))
            init = Resolved(constructor.path, methods.get("init"))
            initialized = proof.prove(init, rules.CONTEXT_INIT)
            if not initialized:
                continue
            if {"rawArguments", "argv", "detailedOptions", text(initialized["__positional"])} & methods.keys():
                continue
            push = Resolved(constructor.path, methods.get(text(initialized["__push"])))
            pushed = proof.prove(push, rules.CONTEXT_PUSH)
            parser = proof.symbol(init, initialized["__parse"])
            if not pushed or not proof.parser(parser):
                continue
            tables = proof.provider(proof.symbol(push, pushed["__provider"]))
            if tables and proof.initial_parser(init, initialized["__initial"], parser):
                result.append(TableFlow(tables, tuple(proof.sites), tuple(sorted(proof.manifests)), text(initialized["__positional"]), Site(constructor.path, init.node)))
    return result
