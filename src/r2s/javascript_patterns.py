from __future__ import annotations

from functools import lru_cache
from typing import Any

from r2s.syntax import field, literal, parse, text


def children(node: Any) -> list[Any]:
    selected = []
    previous = None
    for child in node.children:
        if child.type == "comment":
            continue
        if not child.is_named and child.type == ",":
            if node.type in {"array", "array_pattern"} and previous in {"[", ","}:
                selected.append(child)
        elif child.is_named or child.type != ";" and text(child):
            selected.append(child)
        previous = child.type
    return selected


def match(pattern: Any, actual: Any, captures: dict[str, Any]) -> bool:
    if pattern is None or actual is None:
        return pattern is actual
    if pattern.type == "pair" and actual.type == "shorthand_property_identifier" and text(field(pattern, "key")) == text(actual):
        return match(field(pattern, "value"), actual, captures)
    name = text(pattern)
    if pattern.type in {"identifier", "property_identifier", "shorthand_property_identifier", "shorthand_property_identifier_pattern"} and name.startswith("__"):
        if name.startswith("__literal_"):
            try:
                literal(actual)
            except ValueError:
                return False
        elif name.startswith("__expression_"):
            pass
        elif actual.type not in {"identifier", "property_identifier", "private_property_identifier", "shorthand_property_identifier", "shorthand_property_identifier_pattern"}:
            return False
        if name in captures:
            return text(captures[name]) == text(actual)
        captures[name] = actual
        return True
    if pattern.type != actual.type:
        return False
    expected, selected = children(pattern), children(actual)
    if len(expected) != len(selected):
        return False
    if not expected:
        return text(pattern) == text(actual)
    return all(match(left, right, captures) for left, right in zip(expected, selected, strict=True))


@lru_cache(maxsize=64)
def template(source: str) -> Any:
    tree = parse(source, "javascript")
    if tree is None:
        raise ValueError("JS_ANALYZER_TEMPLATE_INVALID")
    return next(node for node in tree.named_children if node.type != "comment")


def function_match(source: str, actual: Any) -> dict[str, Any] | None:
    expected = template(source)
    captures: dict[str, Any] = {}
    if actual is None or actual.type not in {"function_declaration", "function_expression", "generator_function_declaration", "method_definition"}:
        return None
    if any(item.type == "*" for item in expected.children) != any(item.type == "*" for item in actual.children):
        return None
    if any(item.type == "async" for item in expected.children) != any(item.type == "async" for item in actual.children):
        return None
    if not match(field(expected, "parameters"), field(actual, "parameters"), captures) or not match(field(expected, "body"), field(actual, "body"), captures):
        return None
    return captures
