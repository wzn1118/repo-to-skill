from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from dataclasses import field as data_field
from pathlib import Path
from typing import Any

from r2s.scanner import ScanResult
from r2s.syntax import field, literal, parse, relative_import, text


@dataclass(frozen=True)
class Site:
    path: Path
    node: Any
    kind: str = "javascript.symbol"


@dataclass(frozen=True)
class Resolved:
    path: Path
    node: Any
    sites: tuple[Site, ...] = ()
    external: tuple[str, str] | None = None
    namespace: Path | None = None


@dataclass(frozen=True)
class Link:
    node: Any
    site: Any
    properties: tuple[str, ...] = ()
    imported: tuple[str, str] | None = None


@dataclass
class Module:
    tree: Any
    bindings: dict[str, Link] = data_field(default_factory=dict)
    exports: dict[str, Link] = data_field(default_factory=dict)
    blocked: set[str] = data_field(default_factory=set)
    blocked_exports: set[str] = data_field(default_factory=set)


def property_name(node: Any) -> str | None:
    if node is None:
        return None
    if node.type in {"identifier", "property_identifier", "shorthand_property_identifier", "shorthand_property_identifier_pattern"}:
        return text(node)
    try:
        value = literal(node)
    except ValueError:
        return None
    return value if isinstance(value, str) else None


def statements(node: Any) -> Iterator[Any]:
    yield node
    if node.type in {"function_declaration", "function_expression", "generator_function_declaration", "arrow_function", "class_declaration", "class"}:
        return
    for child in node.named_children:
        yield from statements(child)


class JavaScriptGraph:
    def __init__(self, scan: ScanResult, max_modules: int = 128, max_depth: int = 32):
        self.scan = scan
        self.admitted = set(scan.source_index)
        self.modules: dict[Path, Module | None] = {}
        self.max_modules = max_modules
        self.max_depth = max_depth
        self.diagnostics: set[str] = set()

    def module(self, path: Path) -> Module | None:
        if path in self.modules:
            return self.modules[path]
        if path not in self.admitted or len(self.modules) >= self.max_modules:
            self.diagnostics.add("JS_SYMBOL_MODULE_LIMIT_OR_UNSCANNED")
            return None
        tree = parse(self.scan.read_text(path), "typescript" if path.suffix == ".ts" else "javascript")
        module = Module(tree) if tree is not None else None
        self.modules[path] = module
        if module is None:
            self.diagnostics.add("JS_SYMBOL_PARSE_FAILED")
            return None

        def bind(name: str, link: Link) -> None:
            if name in module.bindings:
                module.blocked.add(name)
            module.bindings[name] = link

        def export(name: str, link: Link) -> None:
            if name in module.exports:
                module.blocked_exports.add(name)
            module.exports[name] = link

        for statement in tree.named_children:
            if statement.type == "import_statement":
                try:
                    imported = literal(field(statement, "source"))
                except ValueError:
                    continue
                clause = next((item for item in statement.named_children if item.type == "import_clause"), None)
                for item in clause.named_children if clause else ():
                    if item.type == "identifier":
                        bind(text(item), Link(item, statement, imported=(imported, "default")))
                    elif item.type == "namespace_import":
                        bind(text(item.named_children[0]), Link(item, statement, imported=(imported, "*")))
                    elif item.type == "named_imports":
                        for specifier in item.named_children:
                            name = field(specifier, "name")
                            bind(text(field(specifier, "alias") or name), Link(name, statement, imported=(imported, text(name))))
                continue
            exported = statement.type == "export_statement"
            declaration = field(statement, "declaration") if exported else statement
            if declaration is not None:
                if declaration.type in {"function_declaration", "generator_function_declaration", "class_declaration"}:
                    name = text(field(declaration, "name"))
                    bind(name, Link(declaration, declaration))
                    if exported:
                        export("default" if any(text(item) == "default" for item in statement.children) else name, Link(field(declaration, "name"), statement))
                elif declaration.type in {"lexical_declaration", "variable_declaration"}:
                    for item in declaration.named_children:
                        if item.type != "variable_declarator":
                            continue
                        name, value = field(item, "name"), field(item, "value")
                        names: list[tuple[str, tuple[str, ...]]] = []
                        if name.type == "identifier":
                            names.append((text(name), ()))
                        elif name.type == "object_pattern":
                            for selected in name.named_children:
                                if selected.type == "shorthand_property_identifier_pattern":
                                    names.append((text(selected), (text(selected),)))
                                elif selected.type == "pair_pattern" and field(selected, "value").type == "identifier":
                                    key = property_name(field(selected, "key"))
                                    if key is not None:
                                        names.append((text(field(selected, "value")), (key,)))
                        for local, properties in names:
                            bind(local, Link(value, item, properties))
                            if exported:
                                export(local, Link(name if name.type == "identifier" else value, statement, properties))
            if not exported:
                continue
            value = field(statement, "value")
            if value is not None:
                export("default", Link(value, statement))
            clause = next((item for item in statement.named_children if item.type == "export_clause"), None)
            for specifier in clause.named_children if clause else ():
                original = field(specifier, "name")
                name = text(field(specifier, "alias") or original)
                source = field(statement, "source")
                if source is not None:
                    try:
                        imported = literal(source)
                    except ValueError:
                        continue
                    original_name = text(original) if original is not None else "default"
                    export(name, Link(original, statement, imported=(imported, original_name)))
                else:
                    export(name, Link(original, statement))
        for node in statements(tree):
            if node.type in {"assignment_expression", "augmented_assignment_expression", "update_expression"}:
                target = field(node, "left") or field(node, "argument")
                while target is not None and target.type in {"member_expression", "subscript_expression"}:
                    target = field(target, "object")
                if target is not None:
                    module.blocked.add(text(target))
        return module

    def local(self, path: Path, name: str, seen: frozenset[tuple[Path, str]] = frozenset()) -> Resolved | None:
        key = (path, "local:" + name)
        if key in seen or len(seen) >= self.max_depth:
            self.diagnostics.add("JS_SYMBOL_CYCLE_OR_DEPTH")
            return None
        module = self.module(path)
        if module is None or name in module.blocked or name not in module.bindings:
            return None
        return self._link(path, module.bindings[name], seen | {key})

    def exported(self, path: Path, name: str, seen: frozenset[tuple[Path, str]] = frozenset()) -> Resolved | None:
        key = (path, "export:" + name)
        if key in seen or len(seen) >= self.max_depth:
            self.diagnostics.add("JS_SYMBOL_CYCLE_OR_DEPTH")
            return None
        module = self.module(path)
        if module is None or name in module.blocked_exports or name in module.blocked or name not in module.exports:
            return None
        return self._link(path, module.exports[name], seen | {key})

    def _link(self, path: Path, link: Link, seen: frozenset[tuple[Path, str]]) -> Resolved | None:
        site = Site(path, link.site, "javascript.import" if link.imported else "javascript.symbol")
        if link.imported:
            source, member = link.imported
            if not source.startswith("."):
                return Resolved(path, link.node, (site,), external=(source, member))
            target = relative_import(path, source, self.admitted)
            if target is None:
                self.diagnostics.add("JS_SYMBOL_IMPORT_UNRESOLVED")
                return None
            resolved = Resolved(target, None, namespace=target) if member == "*" else self.exported(target, member, seen)
        else:
            resolved = self.resolve(path, link.node, seen)
        for name in link.properties:
            resolved = self.select(resolved, name, seen)
        if resolved is None:
            return None
        return Resolved(resolved.path, resolved.node, (site, *resolved.sites), resolved.external, resolved.namespace)

    def resolve(self, path: Path, node: Any, seen: frozenset[tuple[Path, str]] = frozenset()) -> Resolved | None:
        if node is None:
            return None
        if node.type in {"identifier", "shorthand_property_identifier"}:
            return self.local(path, text(node), seen)
        if node.type == "member_expression":
            name = property_name(field(node, "property"))
            return self.select(self.resolve(path, field(node, "object"), seen), name, seen) if name else None
        return Resolved(path, node, (Site(path, node),))

    def select(self, resolved: Resolved | None, name: str, seen: frozenset[tuple[Path, str]] = frozenset()) -> Resolved | None:
        if resolved is None:
            return None
        if resolved.namespace:
            selected = self.exported(resolved.namespace, name, seen)
        elif resolved.external:
            package, member = resolved.external
            return Resolved(resolved.path, resolved.node, resolved.sites, (package, name if member == "*" else member + "." + name))
        elif resolved.node.type == "object":
            selected = None
            for item in reversed(resolved.node.named_children):
                if item.type == "pair":
                    key = property_name(field(item, "key"))
                    if key is None:
                        return None
                    if key == name:
                        selected = self.resolve(resolved.path, field(item, "value"), seen)
                        break
                elif item.type == "shorthand_property_identifier" and text(item) == name:
                    selected = self.local(resolved.path, name, seen)
                    break
                elif item.type == "spread_element":
                    return None
        else:
            return None
        if selected is None:
            return None
        return Resolved(selected.path, selected.node, (*resolved.sites, *selected.sites), selected.external, selected.namespace)
