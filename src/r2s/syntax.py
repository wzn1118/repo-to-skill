from __future__ import annotations

import importlib
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any


def parse(source: str, language: str) -> Any:
    try:
        runtime = importlib.import_module("tree_sitter")
        grammar = importlib.import_module("tree_sitter_" + language)
    except ImportError:
        return None
    grammar_language = grammar.language_typescript() if language == "typescript" else grammar.language()
    parser = runtime.Parser(runtime.Language(grammar_language))
    root = parser.parse(source.encode()).root_node
    return None if root.has_error else root


def walk(node: Any) -> Iterator[Any]:
    yield node
    for child in node.named_children:
        yield from walk(child)


def field(node: Any, name: str) -> Any:
    return node.child_by_field_name(name) if node is not None else None


def unconditional(node: Any, function: Any) -> bool:
    parent = node.parent
    while parent is not None and parent != function:
        if parent.type in {"if_statement", "for_statement", "expression_switch_statement", "type_switch_statement", "select_statement", "func_literal", "arrow_function", "function_expression"}:
            return False
        parent = parent.parent
    return bool(parent == function)


def text(node: Any) -> str:
    return node.text.decode("utf-8") if node is not None else ""


def literal(node: Any) -> Any:
    if node is None:
        raise ValueError("SYNTAX_LITERAL_REQUIRED")
    value = text(node)
    if node.type in {"string", "interpreted_string_literal", "raw_string_literal"}:
        if value.startswith('"'):
            return json.loads(value)
        if value.startswith("'") and "\\" not in value:
            return value[1:-1]
        if value.startswith("`"):
            return value[1:-1]
    if node.type in {"true", "false", "number", "int_literal", "float_literal", "null"}:
        return json.loads(value)
    raise ValueError("SYNTAX_DYNAMIC_VALUE")


def relative_import(base: Path, value: str, admitted: set[Path]) -> Path | None:
    if not value.startswith("."):
        return None
    target = (base.parent / value).resolve()
    candidates = [target, target.with_suffix(".js"), target.with_suffix(".ts"), target / "index.js"]
    return next((path for path in candidates if path in admitted), None)
