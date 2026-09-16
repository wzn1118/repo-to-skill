import re
from typing import Annotated, Any, Literal, NotRequired, TypedDict

from pydantic import (
    AfterValidator,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
    TypeAdapter,
    with_config,
)

from r2s.contract_types import SourcePath, Text

CommandName = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,127}$")]
OptionName = Annotated[str, StringConstraints(pattern=r"^--?[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")]
CommandPath = Annotated[tuple[CommandName, ...], Field(max_length=16), BeforeValidator(lambda value: tuple(value) if isinstance(value, list) else value)]
ChildCommandPath = Annotated[tuple[CommandName, ...], Field(min_length=1, max_length=16), BeforeValidator(lambda value: tuple(value) if isinstance(value, list) else value)]


def safe_declared_text(value: str) -> str:
    if value.startswith(("/", "~", "\\")) or re.search(r"[\x00-\x1f\x7f`<>]|^[A-Za-z]:|gh[pousr]_|github_pat_|sk-[A-Za-z0-9]|PRIVATE KEY", value):
        raise ValueError("UNSAFE_DECLARED_VALUE")
    return value


DeclaredText = Annotated[str, StringConstraints(max_length=256), AfterValidator(safe_declared_text)]
DeclaredScalar = DeclaredText | bool | Annotated[int, Field(ge=-(2**53), le=2**53)] | Annotated[float, Field(allow_inf_nan=False)] | None
DeclaredValues = Annotated[tuple[DeclaredScalar, ...], Field(max_length=32), BeforeValidator(lambda value: tuple(value) if isinstance(value, list) else value)]


@with_config(ConfigDict(strict=True, extra="forbid", allow_inf_nan=False))
class OptionSemantics(TypedDict):
    framework: Literal["argparse", "click"]
    scope: Literal["explicit_source_keywords"]
    required: NotRequired[bool]
    nargs: NotRequired[Annotated[int, Field(ge=0, le=32)] | Literal["?", "*", "+"]]
    action: NotRequired[Literal["store", "store_const", "store_true", "store_false", "append", "append_const", "count", "extend", "help", "version"]]
    is_flag: NotRequired[bool]
    multiple: NotRequired[bool]
    count: NotRequired[bool]
    value_type: NotRequired[Literal["str", "int", "float", "bool"]]
    default: NotRequired[DeclaredScalar | DeclaredValues]
    choices: NotRequired[DeclaredValues]


@with_config(ConfigDict(strict=True, extra="forbid"))
class EntrypointValue(TypedDict):
    command: CommandName
    target: Text
    workspace: NotRequired[Text]
    role: NotRequired[Literal["product", "test", "developer", "unknown"]]


@with_config(ConfigDict(strict=True, extra="forbid"))
class OptionValue(TypedDict):
    command: CommandName
    option: OptionName
    command_path: NotRequired[CommandPath]
    semantics: NotRequired[OptionSemantics]


@with_config(ConfigDict(strict=True, extra="forbid"))
class SubcommandValue(TypedDict):
    command: CommandName
    command_path: ChildCommandPath


@with_config(ConfigDict(strict=True, extra="forbid"))
class LicenseValue(TypedDict):
    path: SourcePath


type FactValue = EntrypointValue | OptionValue | SubcommandValue | LicenseValue
FACT_ADAPTER: TypeAdapter[FactValue] = TypeAdapter(FactValue)


def parse_fact(value: dict[str, Any]) -> FactValue:
    return FACT_ADAPTER.validate_python(value, strict=True)
