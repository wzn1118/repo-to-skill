from typing import Annotated, Any, Literal, NotRequired, TypedDict

from pydantic import BeforeValidator, ConfigDict, Field, StringConstraints, TypeAdapter, with_config

from r2s.contract_types import SourcePath, Text

CommandName = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,127}$")]
OptionName = Annotated[str, StringConstraints(pattern=r"^--?[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")]
CommandPath = Annotated[tuple[CommandName, ...], Field(max_length=16), BeforeValidator(lambda value: tuple(value) if isinstance(value, list) else value)]
ChildCommandPath = Annotated[tuple[CommandName, ...], Field(min_length=1, max_length=16), BeforeValidator(lambda value: tuple(value) if isinstance(value, list) else value)]


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
