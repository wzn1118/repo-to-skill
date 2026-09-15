from __future__ import annotations

import json
import re

from r2s.bundle_contracts import BundleProvenance
from r2s.policy import is_safe_command


def slugify(value: str) -> str:
    parts = re.findall(r"[a-z0-9]+", value.lower().replace("_", "-"))
    return "-".join(parts)[:64].rstrip("-") or "repository-skill"


def render_document(provenance: BundleProvenance) -> dict[str, bytes]:
    claims = {claim.id: claim for claim in provenance.claims}
    entrypoint = claims[provenance.document.entrypoint_claim_id]
    command = entrypoint.object.get("command")
    if (
        entrypoint.predicate != "provides_cli"
        or entrypoint.status != "supported"
        or not entrypoint.executable_fact
        or not isinstance(command, str)
        or not is_safe_command(command)
        or entrypoint.subject != "repository"
        or entrypoint.object.get("role", "product") != "product"
    ):
        raise ValueError("Document command must reference a supported CLI claim")
    procedure = provenance.procedure
    if (
        len(procedure.steps) != 1
        or procedure.steps[0].action != command
        or procedure.steps[0].arguments
        or procedure.steps[0].claim_ids != (entrypoint.id,)
        or procedure.precondition_claim_ids != (entrypoint.id,)
    ):
        raise ValueError("Procedure does not match the supported document format")
    option_lines = []
    for claim_id in provenance.document.option_claim_ids:
        claim = claims[claim_id]
        option = claim.object.get("option")
        if (
            claim.predicate != "supports_option"
            or claim.status != "supported"
            or not claim.executable_fact
            or claim.subject != command
            or claim.object.get("command") != command
            or not isinstance(option, str)
            or not re.fullmatch(r"--?[A-Za-z0-9][A-Za-z0-9_-]*", option)
        ):
            raise ValueError("Document option must reference a supported option owned by the CLI")
        option_lines.append(f"- `{option}`")
    description = (
        f"Use the {command} CLI with its statically discovered options. "
        "Check source evidence and preview invocations before execution."
    )
    skill = (
        f"---\nname: {slugify(command)}\ndescription: {json.dumps(description)}\n---\n\n"
        f"# Use {command}\n\n"
        "## Workflow\n\n"
        f"1. Treat `{command}` as the evidence-backed executable name; confirm it is available "
        "in the user's environment without assuming an installation method.\n"
        "2. Select only options listed in `references/cli.md` or arguments explicitly supplied "
        "by the user. Do not invent flags.\n"
        "3. Preview the complete invocation and identify its side effects before asking for "
        "execution approval.\n"
        "4. After execution, verify the user-requested result rather than relying only on the "
        "process exit code.\n\n"
        "See `references/cli.md` for statically discovered options and `references/provenance.md` "
        "for source evidence.\n"
    )
    cli = (
        f"# {command} CLI\n\n## Statically discovered options\n\n"
        + ("\n".join(option_lines) if option_lines else (
            "No options were statically discovered. Do not infer flags; obtain additional "
            "evidence or explicit user input before constructing an invocation."
        ))
        + "\n"
    )
    references = "# Provenance\n\n" + "\n".join(
        f"- Claim `{claim_id}`" for claim_id in sorted(claims)
    ) + "\n"
    return {
        "SKILL.md": skill.encode("utf-8"),
        "references/cli.md": cli.encode("utf-8"),
        "references/provenance.md": references.encode("utf-8"),
    }
