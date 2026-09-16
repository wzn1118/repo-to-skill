from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path

from r2s.python_bindings import BoundOption, bound_options, is_click_command
from r2s.scanner import ScanResult


@dataclass(frozen=True)
class SymbolRef:
    module: str
    name: str


@dataclass(frozen=True)
class Hop:
    kind: str
    path: Path
    node: ast.AST
    source: SymbolRef
    target: SymbolRef


@dataclass(frozen=True)
class ResolvedFunction:
    ref: SymbolRef
    path: Path
    module_tree: ast.Module
    node: ast.FunctionDef
    hops: tuple[Hop, ...]


@dataclass(frozen=True)
class ResolvedOption:
    option: str
    path: Path
    call: ast.Call
    hops: tuple[Hop, ...]
    framework: str
    owner: SymbolRef
    scope: ast.FunctionDef
    command_path: tuple[str, ...] = ()


@dataclass(frozen=True)
class ResolvedCommand:
    command_path: tuple[str, ...]
    path: Path
    call: ast.Call
    hops: tuple[Hop, ...]
    owner: SymbolRef
    scope: ast.FunctionDef


@dataclass
class GraphResult:
    entrypoint: ResolvedFunction | None = None
    options: list[ResolvedOption] = field(default_factory=list)
    diagnostics: set[str] = field(default_factory=set)
    commands: list[ResolvedCommand] = field(default_factory=list)


def dotted(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = dotted(node.value)
        return f"{prefix}.{node.attr}" if prefix else None
    return None


def stored_names(node: ast.AST) -> set[str]:
    result = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Name) and isinstance(child.ctx, (ast.Store, ast.Del)):
            result.add(child.id)
        elif isinstance(child, ast.Attribute) and isinstance(child.ctx, (ast.Store, ast.Del)):
            base = child.value
            while isinstance(base, ast.Attribute):
                base = base.value
            if isinstance(base, ast.Name):
                result.add(base.id)
        elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            result.add(child.name)
        elif isinstance(child, ast.Import):
            result.update(alias.asname or alias.name.split(".")[0] for alias in child.names)
        elif isinstance(child, ast.ImportFrom):
            result.update(alias.asname or alias.name for alias in child.names)
        elif isinstance(child, ast.ExceptHandler) and child.name:
            result.add(child.name)
    return result


class PythonGraph:
    def __init__(self, scan: ScanResult, max_modules: int = 64, max_symbols: int = 128, max_depth: int = 12):
        self.scan = scan
        if min(max_modules, max_symbols, max_depth) < 1:
            raise ValueError("PYTHON_GRAPH_INVALID_LIMIT")
        self.max_modules = max_modules
        self.max_symbols = max_symbols
        self.max_depth = max_depth
        self.modules: dict[str, tuple[Path, ast.Module] | None] = {}
        self.symbol_count = 0
        self.diagnostics: set[str] = set()
        self.cli_roots: set[SymbolRef] = set()
        self.commands: list[ResolvedCommand] = []
        paths = {item.path for item in scan.inventory}
        self.inventory_paths = paths
        self.blocked_frameworks = frozenset(
            name for name in ("argparse", "click", "typer")
            if any(candidate in paths for base in ("", "src/") for candidate in (f"{base}{name}.py", f"{base}{name}/__init__.py", f"{base}{name}"))
        )

    def module_path(self, module: str) -> Path | None:
        if not all(part.isidentifier() for part in module.split(".")):
            return None
        relative = Path(*module.split("."))
        candidates = [
            self.scan.root / base / suffix
            for base in (Path(), Path("src"))
            for suffix in (Path(f"{relative}.py"), relative / "__init__.py")
            if (base / suffix).as_posix() in self.inventory_paths
        ]
        if len(candidates) > 1:
            self.diagnostics.add("PYTHON_MODULE_AMBIGUOUS")
            return None
        if candidates and candidates[0] not in self.scan.source_index:
            self.diagnostics.add("PYTHON_MODULE_NOT_SCANNED")
            return None
        return candidates[0] if candidates else None

    def module(self, name: str) -> tuple[Path, ast.Module] | None:
        if name in self.modules:
            return self.modules[name]
        if len(self.modules) >= self.max_modules:
            self.diagnostics.add("PYTHON_GRAPH_MODULE_LIMIT")
            return None
        path = self.module_path(name)
        if path is None:
            return None
        try:
            tree = ast.parse(self.scan.read_text(path), filename=path.relative_to(self.scan.root).as_posix())
        except (SyntaxError, UnicodeError, RecursionError):
            self.diagnostics.add("PYTHON_GRAPH_PARSE_FAILED")
            self.modules[name] = None
            return None
        self.modules[name] = (path, tree)
        return path, tree

    def import_target(self, module: str, path: Path, node: ast.ImportFrom, name: str) -> SymbolRef | None:
        if node.level:
            package = module.split(".") if path.name == "__init__.py" else module.split(".")[:-1]
            if node.level > len(package):
                return None
            prefix = package[:len(package) - node.level + 1]
            imported = ".".join([*prefix, *([node.module] if node.module else [])])
        else:
            imported = node.module or ""
        return SymbolRef(imported, name) if imported else None

    def bindings(self, module: str, path: Path, tree: ast.Module) -> dict[str, tuple[SymbolRef, ast.AST]]:
        bindings: dict[str, tuple[SymbolRef, ast.AST]] = {}
        overwritten: set[str] = set()
        for statement in tree.body:
            values: dict[str, tuple[SymbolRef, ast.AST]] = {}
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
                values[statement.name] = (SymbolRef(module, statement.name), statement)
            elif isinstance(statement, ast.ImportFrom):
                for alias in statement.names:
                    if alias.name == "*":
                        self.diagnostics.add("PYTHON_WILDCARD_IMPORT")
                        return {}
                    target = self.import_target(module, path, statement, alias.name)
                    if target:
                        values[alias.asname or alias.name] = (target, statement)
            elif isinstance(statement, ast.Import):
                for alias in statement.names:
                    values[alias.asname or alias.name.split(".")[0]] = (SymbolRef(alias.name if alias.asname else alias.name.split(".")[0], ""), statement)
            elif isinstance(statement, (ast.Assign, ast.AnnAssign)):
                targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
                value = dotted(statement.value) if statement.value is not None else None
                if value and self.reference(value, bindings):
                    values = {name.id: (SymbolRef(module, value), statement) for name in targets if isinstance(name, ast.Name)}
            names = {statement.name} if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)) else stored_names(statement)
            overwritten.update(names & bindings.keys())
            for name in names:
                bindings.pop(name, None)
            bindings.update(values)
        return {name: value for name, value in bindings.items() if name not in overwritten}

    def reference(self, name: str, bindings: dict[str, tuple[SymbolRef, ast.AST]]) -> tuple[SymbolRef, ast.AST] | None:
        first, *rest = name.split(".")
        bound = bindings.get(first)
        if bound is None:
            return None
        target, node = bound
        if not rest:
            return bound
        if target.name:
            self.diagnostics.add("PYTHON_ATTRIBUTE_BINDING_UNRESOLVED")
            return None
        requested_module = ".".join([target.module, *rest[:-1]])
        imported_modules = {alias.name for alias in node.names} if isinstance(node, ast.Import) else set()
        if not any(imported == requested_module or imported.startswith(f"{requested_module}.") for imported in imported_modules):
            self.diagnostics.add("PYTHON_ATTRIBUTE_BINDING_UNRESOLVED")
            return None
        return SymbolRef(requested_module, rest[-1]), node

    def resolve(self, ref: SymbolRef, seen: frozenset[SymbolRef] = frozenset()) -> ResolvedFunction | None:
        if ref in seen:
            self.diagnostics.add("PYTHON_IMPORT_CYCLE")
            return None
        if len(seen) > self.max_depth:
            self.diagnostics.add("PYTHON_GRAPH_DEPTH_LIMIT")
            return None
        loaded = self.module(ref.module)
        if loaded is None:
            return None
        path, tree = loaded
        bound = self.reference(ref.name, self.bindings(ref.module, path, tree))
        if bound is None:
            return None
        target, node = bound
        if isinstance(node, ast.AsyncFunctionDef):
            self.diagnostics.add("PYTHON_ASYNC_ENTRY_UNSUPPORTED")
            return None
        if isinstance(node, ast.FunctionDef):
            return ResolvedFunction(SymbolRef(ref.module, node.name), path, tree, node, ())
        resolved = self.resolve(target, seen | {ref})
        if resolved is None:
            return None
        hop = Hop("python.import" if isinstance(node, (ast.Import, ast.ImportFrom)) else "python.symbol_alias", path, node, ref, target)
        return ResolvedFunction(resolved.ref, resolved.path, resolved.module_tree, resolved.node, (hop, *resolved.hops))

    def callees(self, function: ResolvedFunction) -> list[tuple[SymbolRef, tuple[Hop, ...]]]:
        bindings = self.bindings(function.ref.module, function.path, function.module_tree)
        arguments = function.node.args
        shadowed = {arg.arg for arg in [*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs]}
        shadowed.update(arg.arg for arg in [arguments.vararg, arguments.kwarg] if arg is not None)
        for statement in function.node.body:
            shadowed.update(stored_names(statement))
        bindings = {name: value for name, value in bindings.items() if name not in shadowed}
        result: list[tuple[SymbolRef, tuple[Hop, ...]]] = []
        for statement in function.node.body:
            if isinstance(statement, ast.Raise):
                break
            if not isinstance(statement, (ast.Expr, ast.Return, ast.Assign, ast.AnnAssign)):
                continue
            node = statement.value
            if isinstance(node, ast.Call) and not node.args and not node.keywords:
                name = dotted(node.func)
                bound = self.reference(name, bindings) if name else None
                if bound is not None and name is not None:
                    target = SymbolRef(function.ref.module, name)
                    hops = (Hop("python.call", function.path, node, function.ref, target),)
                    result.append((target, hops))
            if isinstance(statement, ast.Return):
                break
        return result

    def visit(self, function: ResolvedFunction, via: tuple[Hop, ...], visited: frozenset[SymbolRef]) -> list[ResolvedOption]:
        if function.ref in visited:
            self.diagnostics.add("PYTHON_CALL_CYCLE")
            return []
        self.symbol_count += 1
        if self.symbol_count > self.max_symbols or len(visited) > self.max_depth:
            self.diagnostics.add("PYTHON_GRAPH_TRAVERSAL_LIMIT")
            return []
        from r2s.python_argparse import ArgparseFlow

        options = [option for option in bound_options(function.module_tree, function.node, self.blocked_frameworks, require_parse=True) if option.framework != "argparse"]
        click_command = is_click_command(function.module_tree, function.node, self.blocked_frameworks)
        if not click_command:
            options = [option for option in options if option.framework != "click"]
            if function.node.decorator_list:
                self.diagnostics.add("PYTHON_DECORATED_CALL_UNRESOLVED")
                return []
        if any(option.framework == "typer" for option in options):
            self.diagnostics.add("PYTHON_TYPER_REGISTRATION_UNRESOLVED")
            options = [option for option in options if option.framework != "typer"]
        if not click_command and (
            len(function.node.args.posonlyargs) + len(function.node.args.args) > len(function.node.args.defaults)
            or any(value is None for value in function.node.args.kw_defaults)
        ):
            self.diagnostics.add("PYTHON_CALL_ARGUMENTS_UNRESOLVED")
            return []
        if not click_command:
            flow = ArgparseFlow(self)
            parsed_options, commands, parsed = flow.analyze(function, via)
            self.diagnostics.update(flow.diagnostics)
            if parsed:
                self.cli_roots.add(function.ref)
                self.commands.extend(commands)
                return parsed_options
        result = [
            ResolvedOption(flag, function.path, option.call, via, option.framework, function.ref, function.node)
            for option in options for flag in declarations(option)
        ]
        if options or click_command:
            self.cli_roots.add(function.ref)
            return result
        for target, hops in self.callees(function):
            resolved = self.resolve(target)
            if resolved is not None:
                result.extend(self.visit(resolved, (*via, *hops, *resolved.hops), visited | {function.ref}))
        if len({item.owner for item in result}) > 1:
            self.diagnostics.add("PYTHON_CLI_DELEGATION_AMBIGUOUS")
            return []
        return result

    def analyze(self, module: str, symbol: str) -> GraphResult:
        entry = self.resolve(SymbolRef(module, symbol))
        options = self.visit(entry, entry.hops, frozenset()) if entry is not None else []
        if len(self.cli_roots) > 1:
            self.diagnostics.add("PYTHON_CLI_DELEGATION_AMBIGUOUS")
            options = []
            self.commands = []
        if any(code.endswith("LIMIT") for code in self.diagnostics):
            options = []
            self.commands = []
        return GraphResult(entry, options, self.diagnostics, self.commands)


def declarations(option: BoundOption) -> list[str]:
    arguments = option.call.args[1:] if option.framework == "typer" else option.call.args
    result = []
    for argument in arguments:
        if not isinstance(argument, ast.Constant) or not isinstance(argument.value, str):
            continue
        values = argument.value.split("/") if option.framework == "click" else [argument.value]
        if all(re.fullmatch(r"--?[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", value) for value in values):
            result.extend(values)
    return list(dict.fromkeys(result))
