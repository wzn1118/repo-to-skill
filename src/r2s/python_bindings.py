from __future__ import annotations

import ast


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
            return f"parser@{value.lineno}"
        if function.endswith((".add_argument_group", ".add_mutually_exclusive_group")):
            owner = function.rsplit(".", 1)[0]
            return owner if owner.startswith("parser@") else ""
        if function in {"click.group", "click.Group"}:
            return "click.group_instance"
    return _qualified(value, bindings) if value is not None else ""


def _walk_expression(node: ast.AST) -> list[ast.Call]:
    if isinstance(node, (ast.Lambda, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return []
    calls = [node] if isinstance(node, ast.Call) else []
    for child in ast.iter_child_nodes(node):
        calls.extend(_walk_expression(child))
    return calls


def _statements(
    statements: list[ast.stmt], bindings: dict[str, str],
) -> tuple[list[tuple[str, ast.Call]], set[str]]:
    found: list[tuple[str, ast.Call]] = []
    used: set[str] = set()
    for statement in statements:
        if isinstance(statement, ast.Import):
            for alias in statement.names:
                bindings[alias.asname or alias.name.split(".")[0]] = (
                    alias.name if alias.asname else alias.name.split(".")[0]
                )
            continue
        if isinstance(statement, ast.ImportFrom):
            for alias in statement.names:
                bindings[alias.asname or alias.name] = (
                    f"{statement.module}.{alias.name}" if not statement.level else ""
                )
            continue
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bindings[statement.name] = ""
            continue
        if not isinstance(statement, (ast.Assign, ast.AnnAssign, ast.Expr, ast.Return)):
            for child in ast.walk(statement):
                if isinstance(child, ast.Name) and isinstance(child.ctx, (ast.Store, ast.Del)):
                    bindings.pop(child.id, None)
            continue
        for call in _walk_expression(statement):
            function = _qualified(call.func, bindings)
            owner = function.rsplit(".", 1)[0]
            if owner.startswith("parser@"):
                used.add(owner)
                if function.endswith(".add_argument"):
                    found.append((owner, call))
        if isinstance(statement, (ast.Assign, ast.AnnAssign)):
            targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
            value = _binding(statement.value, bindings)
            for target in targets:
                if isinstance(target, ast.Name):
                    bindings[target.id] = value
    return found, used


def bound_option_calls(module: ast.AST, scope: ast.AST | None) -> list[ast.Call]:
    if not isinstance(module, ast.Module) or not isinstance(
        scope, (ast.FunctionDef, ast.AsyncFunctionDef),
    ):
        return []
    module_bindings: dict[str, str] = {}
    global_options, _ = _statements(module.body, module_bindings)
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
    options, used = _statements(scope.body, bindings)
    result = [call for owner, call in global_options if owner in used]
    result.extend(call for _, call in options)
    for decorator in scope.decorator_list:
        if isinstance(decorator, ast.Call) and _qualified(decorator.func, module_bindings) == "click.option":
            result.append(decorator)
    defaults = [*arguments.defaults, *[value for value in arguments.kw_defaults if value is not None]]
    annotations = [
        argument.annotation for argument in [*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs]
        if argument.annotation is not None
    ]
    for expression in [*defaults, *annotations]:
        for call in _walk_expression(expression):
            if _qualified(call.func, module_bindings) == "typer.Option":
                result.append(call)
    return sorted(result, key=lambda node: (node.lineno, node.col_offset))
