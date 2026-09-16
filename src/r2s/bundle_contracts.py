from __future__ import annotations

import re
from pathlib import PurePosixPath, PureWindowsPath
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, StringConstraints

from r2s.contract_types import ByteCount, Text
from r2s.domain import Claim, CommandSpec, Evidence, Procedure, RepositorySnapshot


def relative_path(value: str) -> str:
    parts = value.split("/")
    if (
        not value
        or len(value) > 512
        or "\\" in value
        or PurePosixPath(value).is_absolute()
        or PureWindowsPath(value).drive
        or any(part in {"", ".", ".."} for part in parts)
        or any(part.endswith((".", " ")) for part in parts)
        or re.search(r'[\x00-\x1f\x7f<>:"|?*]', value)
        or any(
            re.fullmatch(r"(?i:con|prn|aux|nul|com[1-9]|lpt[1-9])", part.split(".")[0])
            for part in parts
        )
    ):
        raise ValueError("Expected a portable relative file path")
    return value


RelativePath = Annotated[str, AfterValidator(relative_path)]
Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


class BundleLock(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    format: Literal["r2s-bundle-v1"] = "r2s-bundle-v1"
    files: dict[RelativePath, Sha256]


class SkillDocument(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    renderer: Literal["r2s-cli-v3"] = "r2s-cli-v3"
    entrypoint_claim_id: str
    option_claim_ids: list[str]
    subcommand_claim_ids: list[str]


class ScanScope(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    policy_id: Text
    inventory_sha256: Sha256
    complete_within_policy: bool | None
    budget_skipped_files: ByteCount


class BundleProvenance(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    schema_version: Literal["1.4.0"]
    source_snapshot: RepositorySnapshot
    artifact_path: Literal["SKILL.md"]
    procedure: Procedure
    document: SkillDocument
    artifact_claims: dict[RelativePath, list[str]]
    claims: list[Claim]
    evidence: list[Evidence]
    commands: list[CommandSpec]
    scan_scope: ScanScope | None = None


class PluginAuthor(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    name: Literal["Repo-to-Skill"] = "Repo-to-Skill"


class PluginInterface(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    displayName: Annotated[str, StringConstraints(min_length=1, max_length=128)]
    shortDescription: Annotated[str, StringConstraints(min_length=1, max_length=256)]
    longDescription: Annotated[str, StringConstraints(min_length=1, max_length=1024)]
    developerName: Literal["Repo-to-Skill"] = "Repo-to-Skill"
    category: Literal["Developer Tools"] = "Developer Tools"
    capabilities: list[Literal["Interactive"]]
    defaultPrompt: Annotated[str, StringConstraints(min_length=1, max_length=1024)]


class PluginManifest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    name: Annotated[str, StringConstraints(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=64)]
    version: Annotated[str, StringConstraints(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")]
    description: Annotated[str, StringConstraints(min_length=1, max_length=1024)]
    skills: Literal["./skills/"]
    author: PluginAuthor
    interface: PluginInterface
