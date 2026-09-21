from __future__ import annotations

import ast
import re
from typing import Any, cast

from pydantic import TypeAdapter, ValidationError

from r2s.fact_contracts import OptionSemantics, ParameterShape
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
                    elif isinstance(node, ast.Call) and qualified(node.func, bindings) in {"click.Path", "click.File"}:
                        additions["value_type"] = "path"
                    elif isinstance(node, ast.Call) and qualified(node.func, bindings) == "click.Choice" and len(node.args) == 1 and not node.keywords and not sensitive:
                        additions["choices"] = literal(node.args[0])
            if additions:
                validated = SEMANTICS_ADAPTER.validate_python({**result, **additions}, strict=True)
                result = dict(validated)
        except (ValueError, ValidationError):
            continue
    return SEMANTICS_ADAPTER.validate_python(result, strict=True) if len(result) > 2 else None


def parameter_shape(option: ResolvedOption, module: ast.Module) -> ParameterShape:
    keywords = {item.arg: item.value for item in option.call.keywords}
    semantics: dict[str, Any] = dict(explicit_semantics(option, module) or {})
    unknown: list[str] = []
    arity: Any = 1
    required: bool | None = option.positional
    repeatable: bool | None = False
    if option.framework == "argparse":
        action = semantics.get("action", "store")
        if "action" in keywords and "action" not in semantics:
            arity = "unknown"
            unknown.append("custom_or_dynamic_action")
        elif action in {"store_true", "store_false", "store_const", "append_const", "count", "help", "version"}:
            arity = 0
        repeatable = action in {"append", "append_const", "count", "extend"}
        if action in {"help", "version"}:
            unknown.append("terminates_parser")
    else:
        if semantics.get("is_flag") is True or semantics.get("count") is True:
            arity = 0
        elif "flag_value" in keywords or any("/" in argument.value for argument in option.call.args if isinstance(argument, ast.Constant) and isinstance(argument.value, str)):
            arity = "unknown"
            unknown.append("implicit_click_flag_behavior")
        repeatable = bool(semantics.get("multiple") or semantics.get("count"))
        if "callback" in keywords or "cls" in keywords:
            unknown.append("custom_click_behavior")
        for key in ("is_flag", "multiple", "count"):
            if key in keywords and key not in semantics:
                arity = "unknown"
                unknown.append(f"dynamic_{key}")
    if "nargs" in keywords:
        try:
            value = literal(keywords["nargs"])
            if type(value) is int and -1 <= value <= 32 or value in ("?", "*", "+"):
                arity = value
            else:
                arity = "unknown"
        except ValueError:
            arity = "unknown"
        if arity == "unknown":
            unknown.append("dynamic_or_unsupported_nargs")
    if option.positional:
        required = arity not in ("?", "*", -1, 0)
        if option.framework == "click" and "default" in keywords:
            required = False
    if "required" in keywords:
        value = semantics.get("required")
        required = value if isinstance(value, bool) else None
        if required is None:
            unknown.append("dynamic_required")
    if "type" in keywords and "value_type" not in semantics and "choices" not in semantics:
        unknown.append("custom_or_dynamic_type")
    if "choices" in keywords and "choices" not in semantics:
        unknown.append("dynamic_choices")
    if option.exclusive_group is not None and option.group_required is None:
        unknown.append("dynamic_group_required")
    aliases: list[str] = []
    if not option.positional:
        for argument in option.call.args:
            if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                aliases.extend(value for value in argument.value.split("/") if re.fullmatch(r"--?[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", value))
    return TypeAdapter(ParameterShape).validate_python({
        "framework": option.framework, "rule": "python-parameters-v1", "arity": arity,
        "required": required, "repeatable": repeatable, "aliases": tuple(aliases),
        "exclusive_group": option.exclusive_group, "group_required": option.group_required,
        "unknown_reasons": tuple(unknown),
    }, strict=True)
