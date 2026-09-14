from __future__ import annotations

import re

COMMAND_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,127}$")
PYTHON_MODULE_RE = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*$"
)
PYTHON_SYMBOL_RE = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*$"
)


def is_safe_command(value: str) -> bool:
    return bool(COMMAND_RE.fullmatch(value))


def is_safe_python_target(module: str, symbol: str) -> bool:
    return bool(PYTHON_MODULE_RE.fullmatch(module) and PYTHON_SYMBOL_RE.fullmatch(symbol))
