from __future__ import annotations

import ast
from dataclasses import dataclass


@dataclass(frozen=True)
class BoundOption:
    call: ast.Call
    framework: str


def _qualified(node: ast.AST, bindings: dict[str, str]) -> str:
    if isinstance(node, ast.Name):
        return bindings.get(node.id, "")
    if isinstance(node, ast.Attribute):
        owner = _qualified(node.value, bindings)
        return f"{owner}.{node.attr}" if owner else ""
    return ""


def _binding(value: ast.AST | None, bindings: dict[str, str]) -> str:
    if isinstance(value, ast.Call):
        function = _qualified(value.func, bindings)
        if function == "argparse.ArgumentParser":
            prefix = next((keyword.value for keyword in value.keywords if keyword.arg == "prefix_chars"), None)
            if prefix is not None and (not isinstance(prefix, ast.Constant) or not isinstance(prefix.value, str) or "-" not in prefix.value):
                return ""
            if any(keyword.arg is None for keyword in value.keywords):
                return ""
            return f"parser@{value.lineno}:{value.col_offset}"
        if function.endswith((".add_argument_group", ".add_mutually_exclusive_group")):
            owner = function.rsplit(".", 1)[0]
            return owner if owner.startswith("parser@") else ""
        if function in {"click.group", "click.Group"}:
            return "click.group_instance"
    return _qualified(value, bindings) if value is not None else ""


def _walk_expression(node: ast.AST) -> list[ast.Call]:
    if isinstance(node, (ast.Lambda, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.GeneratorExp, ast.ListComp, ast.SetComp, ast.DictComp, ast.IfExp, ast.BoolOp)):
        return []
    calls = [node] if isinstance(node, ast.Call) else []
    for child in ast.iter_child_nodes(node):
        calls.extend(_walk_expression(child))
    return calls


def _statements(
    statements: list[ast.stmt], bindings: dict[str, str],
    blocked_imports: frozenset[str] = frozenset(),
) -> tuple[list[tuple[str, ast.Call]], set[str]]:
    found: list[tuple[str, ast.Call]] = []
    used: set[str] = set()
    for statement in statements:
        if isinstance(statement, ast.Import):
            for alias in statement.names:
                imported = alias.name if alias.asname else alias.name.split(".")[0]
                bindings[alias.asname or alias.name.split(".")[0]] = imported if imported.split(".")[0] not in blocked_imports else ""
            continue
        if isinstance(statement, ast.ImportFrom):
            for alias in statement.names:
                if alias.name == "*":
                    bindings.clear()
                    continue
                imported = f"{statement.module}.{alias.name}" if not statement.level else ""
                bindings[alias.asname or alias.name] = imported if imported.split(".")[0] not in blocked_imports else ""
            continue
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bindings[statement.name] = ""
            continue
        if not isinstance(statement, (ast.Assign, ast.AnnAssign, ast.Expr, ast.Return)):
            for child in ast.walk(statement):
                if isinstance(child, ast.Name) and isinstance(child.ctx, (ast.Store, ast.Del)):
                    bindings.pop(child.id, None)
                elif isinstance(child, (ast.Import, ast.ImportFrom)):
                    for alias in child.names:
                        bindings.pop(alias.asname or alias.name.split(".")[0], None)
            continue
        for call in _walk_expression(statement):
            function = _qualified(call.func, bindings)
            owner = function.rsplit(".", 1)[0]
            if owner.startswith("parser@"):
                used.add(owner)
                if function.endswith(".add_argument"):
                    found.append((owner, call))
                if function.endswith((".parse_args", ".parse_known_args", ".parse_intermixed_args", ".parse_known_intermixed_args")):
                    used.add(f"{owner}:parsed")
        if isinstance(statement, (ast.Assign, ast.AnnAssign)):
            targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
            value = _binding(statement.value, bindings)
            for target in targets:
                if isinstance(target, ast.Name):
                    bindings[target.id] = value
                elif isinstance(target, ast.Attribute):
                    base = target.value
                    while isinstance(base, ast.Attribute):
                        base = base.value
                    if isinstance(base, ast.Name):
                        bindings.pop(base.id, None)
        if isinstance(statement, ast.Return):
            break
    return found, used


def bound_options(
    module: ast.AST, scope: ast.AST | None, blocked_imports: frozenset[str] = frozenset(),
    require_parse: bool = False,
) -> list[BoundOption]:
    if not isinstance(module, ast.Module) or not isinstance(
        scope, (ast.FunctionDef, ast.AsyncFunctionDef),
    ):
        return []
    module_bindings: dict[str, str] = {}
    global_options, _ = _statements(module.body, module_bindings, blocked_imports)
    bindings = dict(module_bindings)
    arguments = scope.args
    for argument in [*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs]:
        bindings.pop(argument.arg, None)
    if arguments.vararg is not None:
        bindings.pop(arguments.vararg.arg, None)
    if arguments.kwarg is not None:
        bindings.pop(arguments.kwarg.arg, None)
    for statement in ast.walk(scope):
        if isinstance(statement, ast.Name) and isinstance(statement.ctx, ast.Store):
            bindings.pop(statement.id, None)
    options, used = _statements(scope.body, bindings, blocked_imports)
    result = [BoundOption(call, "argparse") for owner, call in global_options if owner in used and (not require_parse or f"{owner}:parsed" in used)]
    result.extend(BoundOption(call, "argparse") for owner, call in options if not require_parse or f"{owner}:parsed" in used)
    for decorator in scope.decorator_list:
        if isinstance(decorator, ast.Call) and _qualified(decorator.func, module_bindings) == "click.option":
            result.append(BoundOption(decorator, "click"))
    defaults = [*arguments.defaults, *[value for value in arguments.kw_defaults if value is not None]]
    annotations = [
        argument.annotation for argument in [*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs]
        if argument.annotation is not None
    ]
    for expression in [*defaults, *annotations]:
        for call in _walk_expression(expression):
            if _qualified(call.func, module_bindings) == "typer.Option":
                result.append(BoundOption(call, "typer"))
    return sorted(result, key=lambda item: (item.call.lineno, item.call.col_offset))


def bound_option_calls(module: ast.AST, scope: ast.AST | None) -> list[ast.Call]:
    return [item.call for item in bound_options(module, scope)]


def is_click_command(module: ast.Module, scope: ast.FunctionDef, blocked_imports: frozenset[str]) -> bool:
    bindings: dict[str, str] = {}
    _statements(module.body, bindings, blocked_imports)
    decorators = [
        _qualified(decorator.func if isinstance(decorator, ast.Call) else decorator, bindings)
        for decorator in scope.decorator_list
    ]
    allowed = {"click.command", "click.group", "click.option", "click.argument", "click.pass_context", "click.pass_obj", "click.version_option", "click.help_option"}
    return bool({"click.command", "click.group"} & set(decorators)) and all(value in allowed for value in decorators)
