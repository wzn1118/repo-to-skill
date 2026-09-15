from __future__ import annotations

import shutil
from pathlib import Path
from typing import Literal

from r2s.bundle_validation import validate_skill
from r2s.domain import Finding
from r2s.serialization import canonical_json

ClientTarget = Literal["claude", "cursor"]


def adapt_portable_skills(
    portable_root: Path,
    output_root: Path,
    target: ClientTarget,
    source_profile: str,
) -> tuple[tuple[Path, ...], list[Finding]]:
    if target not in {"claude", "cursor"}:
        return (), [Finding("CLIENT_PROFILE_UNKNOWN", "error", f"Unsupported adapter: {target}")]
    source_bundles = tuple(sorted(path for path in portable_root.iterdir() if path.is_dir()))
    if not source_bundles:
        return (), [Finding("NO_SKILLS_TO_ADAPT", "error", "Portable output has no Skills")]
    client_root = output_root / target
    skills_root = client_root / "skills"
    if client_root.exists():
        shutil.rmtree(client_root)
    skills_root.mkdir(parents=True)
    bundles: list[Path] = []
    findings: list[Finding] = []
    for source in source_bundles:
        destination = skills_root / source.name
        shutil.copytree(source, destination)
        bundles.append(destination)
        findings.extend(validate_skill(destination))
    (client_root / "adapter.json").write_text(
        canonical_json({
            "format": "r2s-client-adapter-v1",
            "target": target,
            "source_profile": source_profile,
            "skills": [f"skills/{path.name}" for path in bundles],
            "analysis_engine": "shared-portable-skill",
        }),
        encoding="utf-8",
    )
    return tuple(bundles), findings
