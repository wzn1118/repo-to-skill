from __future__ import annotations

import math
from dataclasses import asdict
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from r2s.bundle_contracts import RelativePath
from r2s.command_graph import command_path, command_specs
from r2s.domain import Claim, DiscoveryIR, ParameterBinding, Procedure, ProcedureStep
from r2s.fact_contracts import CommandName, DeclaredText
from r2s.serialization import stable_id

InputValue = Annotated[str, StringConstraints(max_length=4096)]


class InvocationRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    command: CommandName
    path: list[CommandName] = Field(default_factory=list, max_length=16)
    parameters: dict[str, list[InputValue]] = Field(default_factory=dict, max_length=128)
    expected_observation: DeclaredText
    stdout_file: RelativePath | None = None
    stdin: Annotated[str, StringConstraints(max_length=16384)] | None = None


class WorkflowRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    format: Literal["r2s-workflow-v1"] = "r2s-workflow-v1"
    title: DeclaredText
    origin: Literal["user_input", "model_candidate"] = "user_input"
    steps: list[InvocationRequest] = Field(min_length=1, max_length=16)


def _validate_values(claim: Claim, values: tuple[str, ...]) -> None:
    shape = claim.object.get("shape")
    if not isinstance(shape, dict) or shape.get("unknown_reasons"):
        raise ValueError(f"PARAMETER_SEMANTICS_UNKNOWN: {claim.id}")
    arity = shape.get("arity")
    count = len(values)
    valid = type(arity) is int and arity >= 0 and count == arity
    valid = valid or arity in {"*", -1} or (arity == "+" and count >= 1) or (arity == "?" and count <= 1)
    if not valid:
        raise ValueError(f"PARAMETER_ARITY_MISMATCH: {claim.id}")
    semantics = claim.object.get("semantics", {})
    if not isinstance(semantics, dict):
        raise TypeError("PARAMETER_SEMANTICS_INVALID")
    value_type = semantics.get("value_type", "str")
    for value in values:
        if not value or len(value) > 4096 or any(ord(character) < 32 or ord(character) == 127 for character in value):
            raise ValueError("PARAMETER_VALUE_INVALID")
        converted: str | int | float | bool = value
        try:
            if value_type == "int":
                converted = int(value)
            elif value_type == "float":
                converted = float(value)
                if not math.isfinite(converted):
                    raise ValueError("nonfinite")
            elif value_type == "bool":
                if shape.get("framework") == "argparse":
                    raise ValueError("argparse bool conversion is not a literal boolean parser")
                if value.casefold() not in {"true", "false", "1", "0", "yes", "no", "on", "off"}:
                    raise ValueError("boolean")
                converted = value.casefold() in {"true", "1", "yes", "on"}
        except ValueError as exc:
            raise ValueError(f"PARAMETER_TYPE_MISMATCH: {claim.id}") from exc
        if "choices" in semantics and converted not in semantics["choices"]:
            raise ValueError(f"PARAMETER_CHOICE_MISMATCH: {claim.id}")


def bind_invocation(claims: list[Claim], request: InvocationRequest, origin: Literal["user_input", "model_candidate"]) -> ProcedureStep:
    specs = command_specs(claims)
    spec = next((item for item in specs if item.command == request.command and item.path == tuple(request.path)), None)
    if spec is None:
        raise ValueError("WORKFLOW_COMMAND_UNKNOWN")
    if any(item.command == spec.command and item.path[:-1] == spec.path and item.path for item in specs):
        raise ValueError("WORKFLOW_SELECT_LEAF_COMMAND")
    by_id = {claim.id: claim for claim in claims}
    owned = [by_id[identifier] for identifier in (*spec.option_claim_ids, *spec.argument_claim_ids)]
    for ancestor in specs:
        if ancestor.command == spec.command and len(ancestor.path) < len(spec.path) and spec.path[:len(ancestor.path)] == ancestor.path:
            for identifier in (*ancestor.option_claim_ids, *ancestor.argument_claim_ids):
                shape = by_id[identifier].object.get("shape")
                if not isinstance(shape, dict) or shape.get("required") is not False or shape.get("group_required"):
                    raise ValueError("WORKFLOW_PARENT_PARAMETER_BINDING_REQUIRED")
    parameters = {str(claim.object.get("option", claim.object.get("argument"))): claim for claim in owned}
    if request.parameters.keys() - parameters.keys():
        raise ValueError("WORKFLOW_PARAMETER_UNKNOWN_OR_WRONG_OWNER")
    bindings: list[ParameterBinding] = []
    used_aliases: set[str] = set()
    selected_groups: dict[str, int] = {}
    argv = list(spec.path)
    identifiers = list(dict.fromkeys([spec.entrypoint_claim_id, spec.declaration_claim_id]))
    for name, values in request.parameters.items():
        claim = parameters[name]
        _validate_values(claim, tuple(values))
        shape = claim.object.get("shape", {})
        if not isinstance(shape, dict):
            raise TypeError("PARAMETER_SEMANTICS_UNKNOWN")
        aliases = set(shape.get("aliases", ()))
        if used_aliases & aliases:
            raise ValueError("PARAMETER_ALIAS_DUPLICATE")
        used_aliases.update(aliases)
        group = shape.get("exclusive_group")
        if isinstance(group, str):
            selected_groups[group] = selected_groups.get(group, 0) + 1
            if selected_groups[group] > 1:
                raise ValueError("PARAMETERS_MUTUALLY_EXCLUSIVE")
        bindings.append(ParameterBinding(claim.id, tuple(values), origin))
    bound = {binding.claim_id: binding for binding in bindings}
    for claim in owned:
        shape = claim.object.get("shape")
        if not isinstance(shape, dict):
            raise TypeError("COMMAND_PARAMETER_COVERAGE_UNKNOWN")
        group = shape.get("exclusive_group")
        aliases = set(shape.get("aliases", ()))
        present = claim.id in bound or bool(aliases & used_aliases)
        if shape.get("required") is None:
            raise ValueError("PARAMETER_REQUIRED_UNKNOWN")
        if shape.get("required") and not present:
            raise ValueError(f"PARAMETER_REQUIRED: {claim.object.get('option', claim.object.get('argument'))}")
        if group is not None and shape.get("group_required") and not selected_groups.get(str(group)):
            raise ValueError("PARAMETER_GROUP_REQUIRED")
    for binding in bindings:
        claim = by_id[binding.claim_id]
        if claim.predicate == "supports_option":
            option = str(claim.object.get("option"))
            if any(value.startswith("-") for value in binding.values):
                if len(binding.values) != 1 or not option.startswith("--"):
                    raise ValueError("PARAMETER_OPTION_LIKE_VALUE_AMBIGUOUS")
                argv.append(f"{option}={binding.values[0]}")
            else:
                argv.extend([option, *binding.values])
            identifiers.append(claim.id)
    positional_seen_optional_gap = False
    for identifier in spec.argument_claim_ids:
        positional_binding = bound.get(identifier)
        if positional_binding is None or not positional_binding.values:
            positional_seen_optional_gap = True
            continue
        if positional_seen_optional_gap or any(value.startswith("-") for value in positional_binding.values):
            raise ValueError("POSITIONAL_BINDING_AMBIGUOUS")
        argv.extend(positional_binding.values)
        identifiers.append(identifier)
    return ProcedureStep(request.command, tuple(argv), tuple(identifiers), request.expected_observation,
                         "external_side_effect", tuple(request.path), tuple(bindings), "invocation", request.stdout_file, request.stdin)


def workflow_procedure(discovery: DiscoveryIR, goal: str, request: WorkflowRequest) -> Procedure:
    commands = {step.command for step in request.steps}
    if len(commands) != 1:
        raise ValueError("WORKFLOW_CROSS_COMMAND_NOT_SUPPORTED")
    steps = tuple(bind_invocation(discovery.claims, item, request.origin) for item in request.steps)
    capability = next((item for item in discovery.capabilities if steps[0].claim_ids[0] in item.claim_ids), None)
    if capability is None:
        raise ValueError("WORKFLOW_CAPABILITY_MISSING")
    claim_ids = tuple(dict.fromkeys(identifier for step in steps for identifier in step.claim_ids))
    return Procedure(stable_id("proc", [goal, request.model_dump(), [asdict(step) for step in steps]]), request.title, goal,
                     (capability.id,), claim_ids, steps, "external_side_effect")


def validate_procedure(claims: list[Claim], procedure: Procedure, command: str, entrypoint: str) -> None:
    if not procedure.steps or len(procedure.steps) > 16:
        raise ValueError("PROCEDURE_STEPS_INVALID")
    for step in procedure.steps:
        if step.action != command:
            raise ValueError("PROCEDURE_COMMAND_MISMATCH")
        if step.mode == "inventory":
            if len(procedure.steps) != 1 or step.arguments or step.bindings or step.command_path or step.stdout_file is not None or step.stdin is not None or step.claim_ids != (entrypoint,):
                raise ValueError("PROCEDURE_INVENTORY_INVALID")
        else:
            by_id = {claim.id: claim for claim in claims}
            parameters = {}
            origins = {binding.origin for binding in step.bindings}
            if len(origins) > 1 or len({binding.claim_id for binding in step.bindings}) != len(step.bindings):
                raise ValueError("PROCEDURE_BINDING_INVALID")
            for binding in step.bindings:
                claim = by_id.get(binding.claim_id)
                if claim is None or command_path(claim) != step.command_path:
                    raise ValueError("PROCEDURE_BINDING_OWNER_INVALID")
                name = str(claim.object.get("option", claim.object.get("argument")))
                parameters[name] = list(binding.values)
            request = InvocationRequest(command=command, path=list(step.command_path), parameters=parameters, expected_observation=step.expected_observation, stdout_file=step.stdout_file, stdin=step.stdin)
            if bind_invocation(claims, request, next(iter(origins), "user_input")) != step:
                raise ValueError("PROCEDURE_INVOCATION_MISMATCH")
    if procedure.precondition_claim_ids != tuple(dict.fromkeys(identifier for step in procedure.steps for identifier in step.claim_ids)):
        raise ValueError("PROCEDURE_PRECONDITIONS_MISMATCH")
