from __future__ import annotations

from r2s.domain import Claim, CommandSpec


def command_path(claim: Claim) -> tuple[str, ...]:
    value = claim.object.get("command_path", ())
    if not isinstance(value, (list, tuple)) or any(not isinstance(part, str) for part in value):
        raise ValueError("COMMAND_PATH_INVALID")
    return tuple(value)


def command_specs(claims: list[Claim]) -> list[CommandSpec]:
    supported = [claim for claim in claims if claim.status == "supported"]
    roots = {str(claim.object.get("command")): claim for claim in supported if claim.predicate == "provides_cli"}
    declarations = {
        (str(claim.object.get("command")), command_path(claim)): claim
        for claim in supported if claim.predicate in {"provides_cli", "supports_subcommand"}
    }
    count = sum(claim.predicate in {"provides_cli", "supports_subcommand"} for claim in supported)
    if len(declarations) != count:
        raise ValueError("COMMAND_DECLARATION_AMBIGUOUS")
    result = []
    for (command, path), declaration in sorted(declarations.items()):
        root = roots.get(command)
        parent = declarations.get((command, path[:-1])) if path else None
        if root is None or (path and parent is None):
            raise ValueError("COMMAND_PARENT_MISSING")
        if path and parent is not None and not set(parent.evidence_ids).issubset(declaration.evidence_ids):
            raise ValueError("COMMAND_PARENT_EVIDENCE_MISSING")
        options = [claim for claim in supported if claim.predicate == "supports_option" and claim.object.get("command") == command and command_path(claim) == path]
        if len({str(claim.object.get("option")) for claim in options}) != len(options):
            raise ValueError("COMMAND_OPTION_AMBIGUOUS")
        for option in options:
            if path and not set(declaration.evidence_ids).issubset(option.evidence_ids):
                raise ValueError("COMMAND_OPTION_OWNER_EVIDENCE_MISSING")
        result.append(CommandSpec(command, path, root.id, declaration.id, parent.id if parent else None, tuple(sorted(claim.id for claim in options))))
    for claim in supported:
        if claim.predicate == "supports_option" and (str(claim.object.get("command")), command_path(claim)) not in declarations:
            raise ValueError("COMMAND_OPTION_OWNER_MISSING")
    return result
