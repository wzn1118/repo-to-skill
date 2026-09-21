from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field, replace

from r2s.python_bindings import framework_bindings
from r2s.python_graph import (
    Hop,
    PythonGraph,
    ResolvedCommand,
    ResolvedFunction,
    ResolvedOption,
    SymbolRef,
    stored_names,
)


@dataclass(frozen=True)
class Qualified:
    name: str


@dataclass(frozen=True)
class ParserRef:
    identity: str
    path: tuple[str, ...]
    hops: tuple[Hop, ...]
    subparsers: bool = False
    group: bool = False
    exclusive_group: str | None = None
    group_required: bool | None = None


@dataclass
class FunctionBinding:
    function: ResolvedFunction
    captured: dict[str, Value] = field(default_factory=dict)


type Value = Qualified | ParserRef | FunctionBinding | str | None


class ArgparseFlow:
    def __init__(self, graph: PythonGraph):
        self.graph = graph
        self.options: list[tuple[str, ResolvedOption]] = []
        self.commands: list[tuple[str, ResolvedCommand]] = []
        self.parsed: dict[str, Hop] = {}
        self.visits = 0
        self.diagnostics: set[str] = set()

    def hop(self, function: ResolvedFunction, node: ast.AST, kind: str, target: SymbolRef | None = None) -> Hop:
        return Hop(kind, function.path, node, function.ref, target or function.ref)

    def globals(self, function: ResolvedFunction) -> dict[str, Value]:
        return {name: Qualified(value) for name, value in framework_bindings(function.module_tree, self.graph.blocked_frameworks).items()}

    def lookup(self, name: str, environment: dict[str, Value], function: ResolvedFunction) -> Value:
        if name in environment:
            return environment[name]
        resolved = self.graph.resolve(SymbolRef(function.ref.module, name))
        if resolved is not None:
            return FunctionBinding(resolved)
        return None

    def expression(self, node: ast.AST | None, environment: dict[str, Value], function: ResolvedFunction, via: tuple[Hop, ...], stack: tuple[SymbolRef, ...]) -> Value:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.Name):
            return self.lookup(node.id, environment, function)
        if isinstance(node, ast.Attribute):
            parent = self.expression(node.value, environment, function, via, stack)
            return Qualified(f"{parent.name}.{node.attr}") if isinstance(parent, Qualified) else None
        if not isinstance(node, ast.Call):
            return None
        if isinstance(node.func, ast.Attribute):
            receiver = self.expression(node.func.value, environment, function, via, stack)
            if isinstance(receiver, ParserRef):
                return self.method(receiver, node.func.attr, node, environment, function, via, stack)
            called: Value = Qualified(f"{receiver.name}.{node.func.attr}") if isinstance(receiver, Qualified) else None
        else:
            called = self.expression(node.func, environment, function, via, stack)
        if isinstance(called, Qualified) and called.name == "argparse.ArgumentParser":
            prefix = next((item.value for item in node.keywords if item.arg == "prefix_chars"), None)
            if any(item.arg is None or item.arg == "parents" for item in node.keywords) or node.args:
                self.diagnostics.add("PYTHON_ARGPARSE_CONSTRUCTION_UNRESOLVED")
                return None
            if prefix is not None and (not isinstance(prefix, ast.Constant) or not isinstance(prefix.value, str) or "-" not in prefix.value):
                return None
            location = f"{function.ref.module}:{node.lineno}:{node.col_offset}:{self.visits}"
            return ParserRef(location, (), (*via, self.hop(function, node, "python.parser")))
        if isinstance(called, FunctionBinding):
            if called.function.node.decorator_list or any(item.arg is None for item in node.keywords) or any(isinstance(item, ast.Starred) for item in node.args):
                return None
            arguments = called.function.node.args
            if arguments.vararg or arguments.kwarg:
                return None
            positional = [*arguments.posonlyargs, *arguments.args]
            if len(node.args) > len(positional):
                return None
            supplied: dict[str, Value] = {}
            for parameter, argument in zip(positional, node.args):
                supplied[parameter.arg] = self.expression(argument, environment, function, via, stack)
            allowed = {item.arg for item in [*arguments.args, *arguments.kwonlyargs]}
            for keyword in node.keywords:
                if keyword.arg is None or keyword.arg not in allowed or keyword.arg in supplied:
                    return None
                supplied[keyword.arg] = self.expression(keyword.value, environment, function, via, stack)
            required = [item.arg for item in positional[:len(positional) - len(arguments.defaults)]]
            required += [item.arg for item, default in zip(arguments.kwonlyargs, arguments.kw_defaults, strict=True) if default is None]
            if set(required) - supplied.keys():
                return None
            for parameter in [*positional, *arguments.kwonlyargs]:
                supplied.setdefault(parameter.arg, None)
            hops = (*via, self.hop(function, node, "python.call", called.function.ref), *called.function.hops)
            return self.function(called.function, supplied, called.captured, hops, stack)
        return None

    def method(self, parser: ParserRef, name: str, node: ast.Call, environment: dict[str, Value], function: ResolvedFunction, via: tuple[Hop, ...], stack: tuple[SymbolRef, ...]) -> Value:
        hops = tuple(dict.fromkeys([*parser.hops, *via]))
        if parser.identity in self.parsed and name.startswith("add_"):
            self.diagnostics.add("PYTHON_REGISTRATION_AFTER_PARSE")
            return None
        if name in {"parse_args", "parse_known_args", "parse_intermixed_args", "parse_known_intermixed_args"} and not parser.path and not parser.subparsers and not parser.group:
            self.parsed.setdefault(parser.identity, self.hop(function, node, "python.parse"))
        elif name == "add_subparsers" and not parser.subparsers and not parser.group:
            if node.args or any(item.arg is None or item.arg == "parser_class" for item in node.keywords):
                self.diagnostics.add("PYTHON_SUBPARSER_CLASS_UNRESOLVED")
                return None
            return ParserRef(parser.identity, parser.path, (*hops, self.hop(function, node, "python.subparsers")), True)
        elif name == "add_parser" and parser.subparsers:
            if len(node.args) != 1 or any(item.arg is None or item.arg in {"aliases", "parents", "prefix_chars"} for item in node.keywords):
                self.diagnostics.add("PYTHON_SUBPARSER_CONFIGURATION_UNRESOLVED")
                return None
            child = self.expression(node.args[0], environment, function, via, stack)
            if not isinstance(child, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+-]{0,127}", child):
                self.diagnostics.add("PYTHON_SUBCOMMAND_NAME_UNRESOLVED")
                return None
            path = (*parser.path, child)
            if len(path) > 16:
                self.diagnostics.add("PYTHON_ARGPARSE_DEPTH_LIMIT")
                return None
            declaration = self.hop(function, node, "python.subcommand")
            child_parser = ParserRef(parser.identity, path, (*hops, declaration))
            self.commands.append((parser.identity, ResolvedCommand(path, function.path, node, child_parser.hops, function.ref, function.node)))
            return child_parser
        elif name in {"add_argument_group", "add_mutually_exclusive_group"} and not parser.subparsers:
            group_id = parser.exclusive_group
            required = parser.group_required
            if name == "add_mutually_exclusive_group":
                group_id = f"{function.ref.module}:{node.lineno}:{node.col_offset}"
                value = next((item.value for item in node.keywords if item.arg == "required"), ast.Constant(value=False))
                required = value.value if isinstance(value, ast.Constant) and type(value.value) is bool else None
            return ParserRef(parser.identity, parser.path, (*hops, self.hop(function, node, "python.argument_group")), group=True, exclusive_group=group_id, group_required=required)
        elif name == "add_argument" and not parser.subparsers:
            if any(item.arg is None for item in node.keywords):
                return None
            flags = [self.expression(argument, environment, function, via, stack) for argument in node.args]
            if len(flags) == 1 and isinstance(flags[0], str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+-]{0,127}", flags[0]):
                self.options.append((parser.identity, ResolvedOption(flags[0], function.path, node, hops, "argparse", function.ref, function.node, parser.path, True, parser.exclusive_group, parser.group_required)))
                return None
            if not flags or any(not isinstance(flag, str) or not re.fullmatch(r"--?[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", flag) for flag in flags):
                return None
            for flag in flags:
                if isinstance(flag, str):
                    self.options.append((parser.identity, ResolvedOption(flag, function.path, node, hops, "argparse", function.ref, function.node, parser.path, False, parser.exclusive_group, parser.group_required)))
        return None

    def statements(self, statements: list[ast.stmt], environment: dict[str, Value], function: ResolvedFunction, via: tuple[Hop, ...], stack: tuple[SymbolRef, ...]) -> Value:
        for statement in statements:
            if isinstance(statement, ast.FunctionDef):
                ref = SymbolRef(function.ref.module, f"{function.ref.name}.<locals>.{statement.name}")
                nested = ResolvedFunction(ref, function.path, function.module_tree, statement, ())
                environment[statement.name] = FunctionBinding(nested, environment)
            elif isinstance(statement, (ast.Assign, ast.AnnAssign)):
                value = self.expression(statement.value, environment, function, via, stack)
                targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
                for target in targets:
                    if isinstance(target, ast.Name):
                        environment[target.id] = value
                    else:
                        for name in stored_names(target):
                            environment[name] = None
            elif isinstance(statement, ast.Expr):
                self.expression(statement.value, environment, function, via, stack)
            elif isinstance(statement, ast.Return):
                return self.expression(statement.value, environment, function, via, stack)
            elif isinstance(statement, ast.Raise):
                return None
            elif isinstance(statement, (ast.Import, ast.ImportFrom)):
                fragment = ast.Module(body=[statement], type_ignores=[])
                values = framework_bindings(fragment, self.graph.blocked_frameworks)
                for name in stored_names(statement):
                    environment[name] = Qualified(values[name]) if name in values else None
            else:
                for name in stored_names(statement):
                    environment[name] = None
        return None

    def function(self, function: ResolvedFunction, arguments: dict[str, Value], captured: dict[str, Value], via: tuple[Hop, ...], stack: tuple[SymbolRef, ...]) -> Value:
        if any(isinstance(node, (ast.Global, ast.Nonlocal)) for node in ast.walk(function.node)):
            self.diagnostics.add("PYTHON_NONLOCAL_BINDING_UNRESOLVED")
            return None
        self.visits += 1
        if self.visits > self.graph.max_symbols or len(stack) >= self.graph.max_depth:
            self.diagnostics.add("PYTHON_ARGPARSE_TRAVERSAL_LIMIT")
            return None
        if function.ref in stack:
            self.diagnostics.add("PYTHON_ARGPARSE_CALL_CYCLE")
            return None
        environment = {**self.globals(function), **captured}
        for statement in function.node.body:
            environment.update(dict.fromkeys(stored_names(statement)))
        environment.update(arguments)
        return self.statements(function.node.body, environment, function, via, (*stack, function.ref))

    def analyze(self, function: ResolvedFunction, via: tuple[Hop, ...]) -> tuple[list[ResolvedOption], list[ResolvedCommand], bool]:
        environment = self.globals(function)
        module_statements: list[ast.stmt] = [node for node in function.module_tree.body if isinstance(node, (ast.Assign, ast.AnnAssign)) or (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute))]
        self.statements(module_statements, environment, function, via, ())
        self.parsed.clear()
        arguments: dict[str, Value] = {item.arg: None for item in [*function.node.args.posonlyargs, *function.node.args.args, *function.node.args.kwonlyargs]}
        self.function(function, arguments, environment, via, ())
        if len(self.parsed) > 1:
            self.diagnostics.add("PYTHON_ARGPARSE_ROOT_AMBIGUOUS")
        if len(self.parsed) != 1 or any(code.endswith("LIMIT") for code in self.diagnostics):
            return [], [], bool(self.parsed)
        identity = next(iter(self.parsed))
        proof = self.parsed[identity]
        options = [replace(item, hops=(*item.hops, proof)) for owner, item in self.options if owner == identity]
        commands = [replace(item, hops=(*item.hops, proof)) for owner, item in self.commands if owner == identity]
        if len({item.command_path for item in commands}) != len(commands):
            self.diagnostics.add("PYTHON_SUBCOMMAND_REGISTRATION_AMBIGUOUS")
            return [], [], True
        return options, commands, True
