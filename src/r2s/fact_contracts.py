from typing import Annotated, Any, Literal, NotRequired, TypedDict

from pydantic import ConfigDict, StringConstraints, TypeAdapter, with_config

from r2s.contract_types import SourcePath, Text

CommandName = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,127}$")]
OptionName = Annotated[str, StringConstraints(pattern=r"^--?[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")]


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


@with_config(ConfigDict(strict=True, extra="forbid"))
class LicenseValue(TypedDict):
    path: SourcePath


type FactValue = EntrypointValue | OptionValue | LicenseValue
FACT_ADAPTER: TypeAdapter[FactValue] = TypeAdapter(FactValue)


def parse_fact(value: dict[str, Any]) -> FactValue:
    return FACT_ADAPTER.validate_python(value, strict=True)
