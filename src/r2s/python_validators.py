from __future__ import annotations

import ast

from r2s.python_graph import (
    Hop,
    PythonGraph,
    ResolvedFunction,
    ResolvedOption,
    SymbolRef,
    dotted,
    stored_names,
)


def _body(function: ast.FunctionDef) -> list[ast.stmt]:
    return [node for node in function.body if not (isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str))]


def _parameters(function: ast.FunctionDef, count: int) -> list[str] | None:
    args = function.args
    if function.decorator_list or args.posonlyargs or args.kwonlyargs or args.kwarg or args.vararg or args.defaults or len(args.args) != count:
        return None
    return [parameter.arg for parameter in args.args]


def _external(resolver: PythonGraph, function: ResolvedFunction, node: ast.AST, target: str) -> bool:
    name = dotted(node)
    if not name:
        return False
    alias, _, member = name.partition(".")
    package, _, symbol = target.partition(".")
    if member != symbol or alias in stored_names(function.node) or any(parameter.arg == alias for parameter in function.node.args.args):
        return False
    paths = resolver.inventory_paths
    if any(path in paths for path in (package + ".py", "src/" + package + ".py")) or any(path.startswith((package + "/", "src/" + package + "/")) for path in paths):
        return False
    bindings = resolver.bindings(function.ref.module, function.path, function.module_tree)
    if any(isinstance(item, ast.Attribute) and isinstance(item.ctx, (ast.Store, ast.Del)) and dotted(item.value) == alias for item in ast.walk(function.module_tree)):
        return False
    bound = bindings.get(alias)
    return bool(bound and bound[0] == SymbolRef(package, "") and isinstance(bound[1], ast.Import))


def _compile_helper(resolver: PythonGraph, function: ResolvedFunction) -> bool:
    parameters = _parameters(function.node, 1)
    if parameters is None:
        return False
    argument = parameters[0]
    body = _body(function.node)
    if body and isinstance(body[0], ast.If):
        expected = ast.parse(f'if "\\n" in {argument}:\n {argument} = "(?x)" + {argument}').body[0]
        if ast.dump(body.pop(0), include_attributes=False) != ast.dump(expected, include_attributes=False):
            return False
    expression: ast.AST | None = None
    if len(body) == 1 and isinstance(body[0], ast.Return):
        expression = body[0].value
    elif len(body) == 2 and isinstance(body[0], (ast.Assign, ast.AnnAssign)) and isinstance(body[1], ast.Return):
        assignment = body[0]
        targets = assignment.targets if isinstance(assignment, ast.Assign) else [assignment.target]
        if len(targets) == 1 and isinstance(targets[0], ast.Name) and isinstance(body[1].value, ast.Name) and body[1].value.id == targets[0].id:
            if targets[0].id == argument:
                return False
            expression = assignment.value
    return bool(isinstance(expression, ast.Call) and not expression.keywords and len(expression.args) == 1
                and isinstance(expression.args[0], ast.Name) and expression.args[0].id == argument
                and _external(resolver, function, expression.func, "re.compile"))


def regex_callback(option: ResolvedOption, resolver: PythonGraph) -> tuple[Hop, ...]:
    callbacks = [keyword.value for keyword in option.call.keywords if keyword.arg == "callback"]
    if option.framework != "click" or len(callbacks) != 1 or not isinstance(callbacks[0], ast.Name):
        return ()
    function = resolver.resolve(SymbolRef(option.owner.module, callbacks[0].id))
    if function is None:
        return ()
    parameters = _parameters(function.node, 3)
    body = _body(function.node)
    if parameters is None or len(body) != 1 or not isinstance(body[0], ast.Try):
        return ()
    attempt = body[0]
    if attempt.orelse or attempt.finalbody or len(attempt.body) != 1 or len(attempt.handlers) != 1 or not isinstance(attempt.body[0], ast.Return):
        return ()
    returned = attempt.body[0].value
    if not isinstance(returned, ast.IfExp) or not isinstance(returned.orelse, ast.Constant) or returned.orelse.value is not None:
        return ()
    expected = ast.parse(f"{parameters[2]} is not None", mode="eval").body
    if ast.dump(returned.test) != ast.dump(expected):
        return ()
    invocation = returned.body
    if not isinstance(invocation, ast.Call) or not isinstance(invocation.func, ast.Name) or invocation.keywords or len(invocation.args) != 1 or not isinstance(invocation.args[0], ast.Name) or invocation.args[0].id != parameters[2]:
        return ()
    handler = attempt.handlers[0]
    if handler.type is None or not _external(resolver, function, handler.type, "re.error") or len(handler.body) != 1 or not isinstance(handler.body[0], ast.Raise):
        return ()
    raised = handler.body[0].exc
    cause = handler.body[0].cause
    if cause is not None and not (isinstance(cause, ast.Constant) and cause.value is None):
        return ()
    if not isinstance(raised, ast.Call) or not _external(resolver, function, raised.func, "click.BadParameter") or raised.keywords or len(raised.args) != 1:
        return ()
    message = raised.args[0]
    if any(not isinstance(node, (ast.JoinedStr, ast.FormattedValue, ast.Constant, ast.Name, ast.Load)) for node in ast.walk(message)) or any(isinstance(node, ast.Name) and node.id != handler.name for node in ast.walk(message)):
        return ()
    helper = resolver.resolve(SymbolRef(function.ref.module, invocation.func.id))
    if helper is None or not _compile_helper(resolver, helper):
        return ()
    return (*function.hops, Hop("python.regex_validator", function.path, function.node, option.owner, function.ref),
            *helper.hops, Hop("python.regex_compiler", helper.path, helper.node, function.ref, helper.ref))
