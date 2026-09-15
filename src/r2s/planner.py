from __future__ import annotations

import re
from dataclasses import asdict

from r2s.domain import DiscoveryIR, Procedure, ProcedureStep
from r2s.serialization import stable_id

MAX_GOAL_LENGTH = 500
GENERIC_GOALS = {
    "inspect options", "inspect commands", "inspect the cli", "use commands",
    "use the command", "use repository commands", "use the repository commands",
    "use the discovered commands", "use discovered commands", "explore repository commands",
    "使用仓库命令", "查看命令", "查看选项", "使用发现的命令", "检查选项",
}


def plan(
    discovery: DiscoveryIR,
    goal: str,
    capability_ids: set[str] | None = None,
) -> list[Procedure]:
    normalized_goal = " ".join(goal.split())
    if not normalized_goal:
        raise ValueError("GOAL_REQUIRED")
    if len(normalized_goal) > MAX_GOAL_LENGTH:
        raise ValueError("GOAL_TOO_LONG")
    claims = {claim.id: claim for claim in discovery.claims if claim.status == "supported"}
    command_by_capability: dict[str, str] = {}
    for capability in discovery.capabilities:
        entrypoint_claim = next(
            (
                claims[claim_id]
                for claim_id in capability.claim_ids
                if claim_id in claims
                and claims[claim_id].predicate == "provides_cli"
            ),
            None,
        )
        if entrypoint_claim is not None:
            command_by_capability[capability.id] = str(
                entrypoint_claim.object["command"]
            )
    mentioned_commands = {
        command.casefold()
        for command in command_by_capability.values()
        if re.search(
            rf"(?<![A-Za-z0-9_.+-]){re.escape(command)}(?![A-Za-z0-9_.+-])",
            normalized_goal, re.IGNORECASE,
        )
    }
    if not mentioned_commands and normalized_goal.casefold() not in GENERIC_GOALS:
        return []
    procedures: list[Procedure] = []
    for capability in discovery.capabilities:
        if capability_ids is not None and capability.id not in capability_ids:
            continue
        command_for_capability = command_by_capability.get(capability.id)
        if (
            mentioned_commands
            and command_for_capability is not None
            and command_for_capability.casefold() not in mentioned_commands
        ):
            continue
        capability_claims = [
            claims[claim_id]
            for claim_id in capability.claim_ids
            if claim_id in claims
        ]
        entrypoint = next(
            (
                claim
                for claim in capability_claims
                if claim.predicate == "provides_cli"
            ),
            None,
        )
        if entrypoint is None:
            continue
        command = str(entrypoint.object["command"])
        step = ProcedureStep(
            command,
            (),
            (entrypoint.id,),
            "A complete invocation is previewed using only evidence-backed or "
            "explicitly user-supplied arguments before execution",
            "external_side_effect",
        )
        procedure_id = stable_id("proc", [normalized_goal, capability.id, asdict(step)])
        procedures.append(
            Procedure(
                procedure_id,
                capability.title,
                normalized_goal,
                (capability.id,),
                (entrypoint.id,),
                (step,),
                "external_side_effect",
            )
        )
    return procedures
