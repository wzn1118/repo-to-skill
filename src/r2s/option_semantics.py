from __future__ import annotations

import ast
import re
from typing import Any, cast

from pydantic import TypeAdapter, ValidationError

from r2s.fact_contracts import OptionSemantics
from r2s.python_bindings import framework_bindings
from r2s.python_graph import ResolvedOption, stored_names

SEMANTICS_ADAPTER = TypeAdapter(OptionSemantics)
SENSITIVE_OPTION = re.compile(r"(?:password|passwd|secret|token|credential|private.?key|api.?key|auth)", re.IGNORECASE)


def literal(node: ast.AST) -> Any:
    if isinstance(node, ast.Constant) and (node.value is None or type(node.value) in {str, bool, int, float}):
        return node.value
    if isinstance(node, (ast.List, ast.Tuple)) and len(node.elts) <= 32 and all(isinstance(item, ast.Constant) for item in node.elts):
        return tuple(literal(item) for item in node.elts)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)) and isinstance(node.operand, ast.Constant) and type(node.operand.value) in {int, float}:
        number = cast(int | float, node.operand.value)
        return -number if isinstance(node.op, ast.USub) else number
    raise ValueError("DYNAMIC_PARAMETER_VALUE")


def qualified(node: ast.AST, bindings: dict[str, str]) -> str:
    if isinstance(node, ast.Name):
        return bindings.get(node.id, "")
    if isinstance(node, ast.Attribute):
        owner = qualified(node.value, bindings)
        return f"{owner}.{node.attr}" if owner else ""
    return ""


def explicit_semantics(option: ResolvedOption, module: ast.Module) -> OptionSemantics | None:
    if option.framework not in {"argparse", "click"} or any(item.arg is None for item in option.call.keywords):
        return None
    result: dict[str, Any] = {"framework": option.framework, "scope": "explicit_source_keywords"}
    bindings = framework_bindings(module, frozenset())
    names = stored_names(module) | stored_names(option.scope)
    parameters = option.scope.args
    names.update(item.arg for item in [*parameters.posonlyargs, *parameters.args, *parameters.kwonlyargs])
    names.update(item.arg for item in [parameters.vararg, parameters.kwarg] if item is not None)
    common = {"required", "nargs", "default"}
    allowed = common | ({"action", "choices"} if option.framework == "argparse" else {"is_flag", "multiple", "count"})
    labels = [argument.value for argument in option.call.args if isinstance(argument, ast.Constant) and isinstance(argument.value, str)]
    labels.extend(keyword.value.value for keyword in option.call.keywords if keyword.arg == "dest" and isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str))
    sensitive = any(SENSITIVE_OPTION.search(label) for label in labels)
    for keyword in option.call.keywords:
        key = keyword.arg
        if key is None:
            continue
        try:
            additions: dict[str, Any] = {}
            if key in allowed:
                if sensitive and key in {"default", "choices"}:
                    continue
                additions[key] = literal(keyword.value)
            elif key == "type":
                node = keyword.value
                if isinstance(node, ast.Name) and node.id in {"str", "int", "float", "bool"} and node.id not in names:
                    additions["value_type"] = node.id
                elif option.framework == "click":
                    type_name = qualified(node, bindings)
                    known = {"click.STRING": "str", "click.INT": "int", "click.FLOAT": "float", "click.BOOL": "bool"}
                    if type_name in known:
                        additions["value_type"] = known[type_name]
                    elif isinstance(node, ast.Call) and qualified(node.func, bindings) == "click.Choice" and len(node.args) == 1 and not node.keywords and not sensitive:
                        additions["choices"] = literal(node.args[0])
            if additions:
                validated = SEMANTICS_ADAPTER.validate_python({**result, **additions}, strict=True)
                result = dict(validated)
        except (ValueError, ValidationError):
            continue
    return SEMANTICS_ADAPTER.validate_python(result, strict=True) if len(result) > 2 else None
