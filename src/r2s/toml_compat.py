from __future__ import annotations

import json
import re
from typing import Any

try:
    import tomllib as _tomllib
except ModuleNotFoundError:  # Python 3.10 bootstrap environment
    _tomllib = None  # type: ignore[assignment]


class TOMLDecodeError(ValueError):
    pass


_SECTION = re.compile(r"^\[([A-Za-z0-9_.-]+)]$")
_PAIR = re.compile(
    r'^(?P<key>"(?:[^"\\]|\\.)*"|[A-Za-z0-9_.-]+)\s*=\s*'
    r'(?P<value>"(?:[^"\\]|\\.)*")\s*$'
)


def loads(text: str) -> dict[str, Any]:
    if _tomllib is not None:
        return _tomllib.loads(text)
    result: dict[str, Any] = {}
    section: dict[str, Any] = result
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        section_match = _SECTION.fullmatch(line)
        if section_match:
            section = result
            for part in section_match.group(1).split("."):
                value = section.setdefault(part, {})
                if not isinstance(value, dict):
                    raise TOMLDecodeError(f"Conflicting section at line {line_number}")
                section = value
            continue
        pair_match = _PAIR.fullmatch(line)
        if pair_match:
            key_raw = pair_match.group("key")
            value_raw = pair_match.group("value")
            key = json.loads(key_raw) if key_raw.startswith('"') else key_raw
            section[key] = json.loads(value_raw)
            continue
        raise TOMLDecodeError(f"Unsupported TOML syntax at line {line_number}")
    return result
