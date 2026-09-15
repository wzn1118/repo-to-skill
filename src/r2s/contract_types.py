from __future__ import annotations

import re
from dataclasses import fields
from functools import cache
from typing import Annotated, Any, ClassVar, cast, get_origin, get_type_hints

from pydantic import AfterValidator, ConfigDict, Field, StringConstraints, model_validator


def relative_source_path(value: str) -> str:
    if (
        value.startswith("/") or "\\" in value or len(value) > 2048
        or any(part in {"", ".", ".."} for part in value.split("/"))
        or re.search(r"[\x00-\x1f\x7f:]", value)
    ):
        raise ValueError("SOURCE_PATH_INVALID")
    return value


def complete_schema(schema: dict[str, Any]) -> None:
    schema["required"] = list(schema.get("properties", {}))
    for item in schema.get("properties", {}).values():
        item.pop("default", None)


@cache
def _tuple_fields(record: type[Any]) -> set[str]:
    return {name for name, hint in get_type_hints(record).items() if get_origin(hint) is tuple}


class StrictRecord:
    __pydantic_config__: ClassVar[ConfigDict] = ConfigDict(
        strict=True, extra="forbid", allow_inf_nan=False, json_schema_extra=complete_schema,
    )

    @model_validator(mode="before")
    @classmethod
    def require_serialized_fields(cls, value: Any) -> Any:
        if isinstance(value, dict):
            expected = {item.name for item in fields(cast(Any, cls))}
            if expected - value.keys():
                raise ValueError("CONTRACT_FIELDS_MISSING: " + ",".join(sorted(expected - value.keys())))
            return {
                name: tuple(item) if name in _tuple_fields(cast(Any, cls)) and isinstance(item, list) else item
                for name, item in value.items()
            }
        return value


SourcePath = Annotated[str, AfterValidator(relative_source_path), StringConstraints(
    min_length=1, max_length=2048,
    pattern=re.compile(r"^(?!/)(?!.*//)(?!.*(?:^|/)\.{1,2}(?:/|$))[^\\:\x00-\x1f\x7f]*[^/\\:\x00-\x1f\x7f]$"),
)]
Text = Annotated[str, StringConstraints(min_length=1, max_length=8192)]
Sha256 = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]
GitOid = Annotated[str, StringConstraints(pattern=r"^(?:[a-f0-9]{40}|[a-f0-9]{64})$")]
Confidence = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
PositiveLine = Annotated[int, Field(ge=1)]
ByteCount = Annotated[int, Field(ge=0)]
EvidenceId = Annotated[str, StringConstraints(pattern=r"^ev_(?:[a-f0-9]{20}|[a-f0-9]{64})$")]
ClaimId = Annotated[str, StringConstraints(pattern=r"^cl_(?:[a-f0-9]{20}|[a-f0-9]{64})$")]
CapabilityId = Annotated[str, StringConstraints(pattern=r"^cap_(?:[a-f0-9]{20}|[a-f0-9]{64})$")]
