from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path, PurePosixPath

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Citation(Record):
    path: str
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    content_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    range_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def check_range(self):
        if self.end_line < self.start_line:
            raise ValueError("GOLD_RANGE_INVALID")
        safe_relative(self.path)
        return self


class Assertion(Record):
    id: str
    kind: str
    command: str
    command_path: list[str]
    name: str
    expectation: str = "present"
    fields: dict = Field(default_factory=dict)
    citations: list[Citation] = Field(min_length=1)
    rationale: str = Field(min_length=12)

    @model_validator(mode="after")
    def check_assertion(self):
        if self.kind not in {"option", "argument", "subcommand", "command"}:
            raise ValueError("GOLD_KIND_INVALID")
        if self.expectation not in {"present", "absent"} or self.expectation == "absent" and self.fields:
            raise ValueError("GOLD_EXPECTATION_INVALID")
        allowed = {"shape.arity", "shape.required", "shape.repeatable", "shape.aliases", "semantics.value_type", "semantics.default", "semantics.choices", "semantics.validation", "position", "target"}
        if set(self.fields) - allowed:
            raise ValueError("GOLD_FIELD_INVALID")
        if self.kind in {"option", "argument"} and self.expectation == "present" and not self.fields:
            raise ValueError("GOLD_OPERATIONAL_FIELDS_REQUIRED")
        if any(not part or any(char.isspace() for char in part) for part in self.command_path):
            raise ValueError("GOLD_COMMAND_PATH_INVALID")
        if not self.id or not self.name or not self.command:
            raise ValueError("GOLD_SUBJECT_EMPTY")
        if self.kind == "subcommand" and (not self.command_path or self.name != self.command_path[-1]):
            raise ValueError("GOLD_SUBCOMMAND_INVALID")
        if self.kind == "command" and (self.command_path or self.name != self.command):
            raise ValueError("GOLD_COMMAND_INVALID")
        for field, value in self.fields.items():
            validate_json_value(value)
            if field in {"shape.required", "shape.repeatable"} and type(value) is not bool:
                raise ValueError("GOLD_FIELD_TYPE_INVALID")
            if field == "shape.arity" and not (type(value) is int and -1 <= value <= 32 or type(value) is str and value in {"?", "*", "+"}):
                raise ValueError("GOLD_FIELD_TYPE_INVALID")
            if field == "position" and not (type(value) is int and value >= 0):
                raise ValueError("GOLD_FIELD_TYPE_INVALID")
            if field in {"shape.aliases", "semantics.choices"} and (not isinstance(value, list) or not value or any(type(item) not in {str, bool, int, float, type(None)} for item in value)):
                raise ValueError("GOLD_FIELD_TYPE_INVALID")
            if field == "semantics.value_type" and (type(value) is not str or value not in {"str", "int", "float", "bool", "path"}):
                raise ValueError("GOLD_FIELD_TYPE_INVALID")
            if field in {"target", "semantics.validation"} and (type(value) is not str or not value):
                raise ValueError("GOLD_FIELD_TYPE_INVALID")
            if field == "shape.aliases" and any(type(item) is not str or not item or item[0] not in "-+" for item in value):
                raise ValueError("GOLD_FIELD_TYPE_INVALID")
        return self


class Repository(Record):
    id: str = Field(pattern=r"^[a-z0-9-]+$")
    repository: str = Field(pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
    commit_sha: str = Field(pattern=r"^[a-f0-9]{40}$")
    assertions: list[Assertion] = Field(min_length=1)


class Gold(Record):
    format: str
    metadata_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    review_method: str
    tuning_scope: str
    repositories: list[Repository] = Field(min_length=1)

    @model_validator(mode="after")
    def check_unique(self):
        if self.format != "r2s-semantic-gold-v1":
            raise ValueError("GOLD_FORMAT_INVALID")
        identities = [item.id for item in self.repositories]
        assertions = [item.id for repo in self.repositories for item in repo.assertions]
        subjects = [(repo.id, item.kind, item.command, tuple(item.command_path), item.name)
                    for repo in self.repositories for item in repo.assertions]
        if len(set(identities)) != len(identities) or len(set(assertions)) != len(assertions) or len(set(subjects)) != len(subjects):
            raise ValueError("GOLD_DUPLICATE_ID_OR_SUBJECT")
        return self


def safe_relative(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if not name or path.is_absolute() or path.as_posix() != name or any(part in {"", ".", ".."} for part in name.split("/")) or re.search(r"[\\:\x00-\x1f]", name):
        raise ValueError("GOLD_PATH_INVALID")
    return path


def source_bytes(root: Path, relative: str) -> bytes:
    parts = safe_relative(relative).parts
    path = root
    if root.is_symlink():
        raise ValueError("GOLD_SOURCE_SYMLINK")
    for part in parts:
        path = path / part
        if path.is_symlink():
            raise ValueError("GOLD_SOURCE_SYMLINK")
    if not path.is_file() or path.stat().st_size > 8 * 1024 * 1024:
        raise ValueError("GOLD_SOURCE_INVALID_OR_TOO_LARGE")
    return path.read_bytes()


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_json_value(value, depth=0) -> None:
    if depth > 64:
        raise ValueError("GOLD_JSON_TOO_DEEP")
    if type(value) is float and not math.isfinite(value):
        raise ValueError("GOLD_NONFINITE_JSON")
    if type(value) is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise ValueError("GOLD_JSON_KEY_INVALID")
            validate_json_value(item, depth + 1)
    elif type(value) is list:
        for item in value:
            validate_json_value(item, depth + 1)
    elif type(value) not in {str, bool, int, float, type(None)}:
        raise ValueError("GOLD_JSON_TYPE_INVALID")


def strict_loads(data: bytes) -> dict:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("GOLD_DUPLICATE_JSON_KEY")
            result[key] = value
        return result

    def constant(value):
        raise ValueError("GOLD_NONFINITE_JSON")

    result = json.loads(data, object_pairs_hook=pairs, parse_constant=constant)
    validate_json_value(result)
    if type(result) is not dict:
        raise ValueError("GOLD_JSON_OBJECT_REQUIRED")
    return result


def strict_load(path: Path) -> dict:
    if path.stat().st_size > 128 * 1024 * 1024:
        raise ValueError("GOLD_JSON_TOO_LARGE")
    return strict_loads(path.read_bytes())


def citation(root: Path, relative: str, anchor: str, lines: int) -> dict:
    if not anchor or type(lines) is not int or lines < 1:
        raise ValueError("GOLD_ANCHOR_INVALID")
    data = source_bytes(root, relative)
    text = data.decode("utf-8").splitlines()
    found = [index for index, line in enumerate(text) if anchor in line]
    if len(found) != 1:
        raise ValueError(f"GOLD_ANCHOR_NOT_UNIQUE: {relative}: {anchor}: {len(found)}")
    start = found[0]
    end = min(len(text), start + lines)
    return Citation(path=relative, start_line=start + 1, end_line=end, content_sha256=digest(data),
                    range_sha256=digest("\n".join(text[start:end]).encode())).model_dump()


def verify_sources(gold: Gold, snapshots: Path) -> None:
    if any(path.is_symlink() for path in (snapshots, *snapshots.parents)):
        raise ValueError("GOLD_SNAPSHOT_SYMLINK")
    for repo in gold.repositories:
        cached = snapshots / f"{repo.id}-{repo.commit_sha}"
        if cached.is_symlink():
            raise ValueError("GOLD_SNAPSHOT_SYMLINK")
        locked = strict_loads(source_bytes(cached, "source.lock.json"))
        if locked["repository"] != repo.repository or locked["commit_sha"] != repo.commit_sha:
            raise ValueError("GOLD_SNAPSHOT_PIN_MISMATCH")
        for item in repo.assertions:
            for ref in item.citations:
                data = source_bytes(cached / "source", ref.path)
                lines = data.decode("utf-8").splitlines()
                expected = locked["files"].get(ref.path, {})
                if digest(data) != ref.content_sha256 or ref.content_sha256 != expected.get("sha256") or ref.end_line > len(lines):
                    raise ValueError("GOLD_SOURCE_MISMATCH")
                if digest("\n".join(lines[ref.start_line - 1:ref.end_line]).encode()) != ref.range_sha256:
                    raise ValueError("GOLD_RANGE_MISMATCH")


def candidates(assertion: Assertion, facts: list[dict]) -> list[dict]:
    predicate = {"option": "supports_option", "argument": "supports_argument", "subcommand": "supports_subcommand", "command": "provides_cli"}[assertion.kind]
    selected = []
    for fact in facts:
        value = fact.get("value", {})
        if fact["emitted"] is not True or fact.get("predicate") != predicate or value.get("command") != assertion.command:
            continue
        if list(value.get("command_path", [])) != assertion.command_path:
            continue
        name = value.get({"option": "option", "argument": "argument", "command": "command"}.get(assertion.kind, ""))
        if assertion.kind == "subcommand" or name == assertion.name or assertion.kind == "option" and assertion.name in value.get("shape", {}).get("aliases", []):
            selected.append(fact)
    return selected


def canonical_fact(fact: dict, assertion: Assertion) -> str:
    value = dict(fact["value"])
    value.pop({"option": "option", "argument": "argument"}.get(assertion.kind, ""), None)
    return json.dumps([value, fact.get("status")], sort_keys=True)


def check_assertion(assertion: Assertion, facts: list[dict]) -> dict:
    selected = candidates(assertion, facts)
    checked = []
    if assertion.expectation == "absent":
        status = "NEGATIVE_VIOLATION" if selected else "NEGATIVE_CLEAR"
    elif not selected:
        status = "MISSING_FACT"
    elif len(selected) > 1 and len({canonical_fact(fact, assertion) for fact in selected}) != 1:
        status = "AMBIGUOUS_FACT"
    else:
        fact = selected[0]
        for path, expected in assertion.fields.items():
            actual = fact["value"]
            found = True
            for part in path.split("."):
                if not isinstance(actual, dict) or part not in actual:
                    found = False
                    break
                actual = actual[part]
            if not found or actual is None and expected is not None or path == "semantics.value_type" and actual == "unknown":
                verdict = "UNKNOWN"
            elif path in {"shape.aliases", "semantics.choices"}:
                verdict = "MATCH" if isinstance(actual, list) and all(any(type(value) is type(wanted) and value == wanted for value in actual) for wanted in expected) else "MISMATCH"
            else:
                verdict = "MATCH" if type(actual) is type(expected) and actual == expected else "MISMATCH"
            checked.append({"field": path, "expected": expected, "actual": actual if found else None, "present": found, "status": verdict})
        if any(row["status"] == "MISMATCH" for row in checked):
            status = "FIELD_MISMATCH"
        elif any(row["status"] == "UNKNOWN" for row in checked) or fact.get("status") != "supported" or fact["value"].get("shape", {}).get("unknown_reasons"):
            status = "PARTIAL_OR_UNKNOWN"
        else:
            status = "SELECTED_FIELDS_MATCH"
    if not checked:
        checked = [{"field": path, "expected": expected, "actual": None, "present": False, "status": "NOT_EVALUATED"} for path, expected in assertion.fields.items()]
    return {"id": assertion.id, "kind": assertion.kind, "command": assertion.command, "command_path": assertion.command_path,
            "name": assertion.name, "expectation": assertion.expectation, "status": status, "fields": checked,
            "claim_ids": sorted(item["id"] for item in selected), "citations": [item.model_dump() for item in assertion.citations],
            "rationale": assertion.rationale}


def validate_facts(facts) -> None:
    if type(facts) is not list:
        raise ValueError("GOLD_RESULT_FACTS_INVALID")
    identities = set()
    for fact in facts:
        if (type(fact) is not dict or type(fact.get("id")) is not str or not fact["id"]
                or type(fact.get("emitted")) is not bool or type(fact.get("predicate")) is not str
                or type(fact.get("status")) is not str or type(fact.get("value")) is not dict):
            raise ValueError("GOLD_RESULT_FACT_INVALID")
        if fact["id"] in identities:
            raise ValueError("GOLD_RESULT_DUPLICATE_CLAIM")
        identities.add(fact["id"])
        value = fact["value"]
        path = value.get("command_path", [])
        if type(path) is not list or any(type(part) is not str or not part for part in path):
            raise ValueError("GOLD_RESULT_PATH_INVALID")
        for field in ("shape", "semantics"):
            if field in value and type(value[field]) is not dict:
                raise ValueError("GOLD_RESULT_PARAMETER_INVALID")
        for field in ("aliases", "unknown_reasons"):
            items = value.get("shape", {}).get(field, [])
            if type(items) is not list or any(type(item) is not str for item in items):
                raise ValueError("GOLD_RESULT_PARAMETER_INVALID")


def evaluate(gold: Gold, results: dict) -> dict:
    validate_json_value(results)
    if (type(results.get("repositories")) is not list
            or any(type(item) is not dict or type(item.get("id")) is not str for item in results["repositories"])
            or type(results.get("compiler_sha256")) is not str
            or not re.fullmatch(r"[a-f0-9]{64}", results["compiler_sha256"])):
        raise ValueError("GOLD_RESULT_INVALID")
    indexed = {item["id"]: item for item in results["repositories"]}
    if len(indexed) != len(results["repositories"]):
        raise ValueError("GOLD_RESULT_DUPLICATE_REPOSITORY")
    if results.get("metadata_sha256") != gold.metadata_sha256:
        raise ValueError("GOLD_METADATA_MISMATCH")
    repositories = []
    for repo in gold.repositories:
        measured = indexed.get(repo.id)
        if not measured or measured["repository"] != repo.repository or measured["commit_sha"] != repo.commit_sha:
            raise ValueError("GOLD_RESULT_PIN_MISMATCH")
        if type(measured.get("completed")) is not bool:
            raise ValueError("GOLD_RESULT_COMPLETION_INVALID")
        if measured["completed"] and measured.get("compiler_sha256") != results["compiler_sha256"]:
            raise ValueError("GOLD_RESULT_COMPILER_MISMATCH")
        if measured["completed"]:
            facts = measured.get("facts")
            validate_facts(facts)
            assertions = [check_assertion(item, facts) for item in repo.assertions]
        else:
            assertions = [check_assertion(item, []) for item in repo.assertions]
            for assertion in assertions:
                assertion["status"] = "MEASUREMENT_INCOMPLETE"
        repositories.append({"id": repo.id, "repository": repo.repository, "commit_sha": repo.commit_sha,
                             "assertions": assertions, "counts": dict(Counter(item["status"] for item in assertions))})
    rows = [item for repo in repositories for item in repo["assertions"]]
    return {"format": "r2s-semantic-gold-evaluation-v1", "input_compiler_sha256": results["compiler_sha256"],
            "positive_subjects": sum(item["expectation"] == "present" for item in rows),
            "negative_subjects": sum(item["expectation"] == "absent" for item in rows),
            "counts": dict(Counter(item["status"] for item in rows)), "repositories": repositories,
            "field_counts": dict(Counter(field["status"] for item in rows for field in item["fields"])),
            "selected_field_denominator": sum(len(item["fields"]) for item in rows),
            "human_verified_repositories": 0, "full_semantic_precision": None,
            "scope": "Retrospective agent-curated selected-field agreement, not complete generated-fact precision, human sign-off, held-out accuracy or Agent uplift. Missing and unknown fields stay in the positive denominator; negatives are separate. Alias/choice checks require the selected values, not an exhaustive set."}


def write_new(path: Path, value: dict) -> None:
    for parent in (path, *path.parents):
        if parent.is_symlink():
            raise ValueError("SEMANTIC_GOLD_OUTPUT_SYMLINK")
        if parent.is_dir() and (parent / "manifest.json").exists():
            raise ValueError("SEMANTIC_GOLD_RUN_FINALIZED")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--snapshots", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("SEMANTIC_GOLD_OUTPUT_EXISTS")
    inputs = {path: path.read_bytes() for path in (args.gold, args.results, Path(__file__))}
    payload = Gold.model_validate(strict_loads(inputs[args.gold]), strict=True)
    verify_sources(payload, args.snapshots)
    result = evaluate(payload, strict_loads(inputs[args.results]))
    verify_sources(payload, args.snapshots)
    if any(path.read_bytes() != data for path, data in inputs.items()):
        raise ValueError("SEMANTIC_GOLD_INPUT_CHANGED")
    result["gold_input_sha256"] = digest(inputs[args.gold])
    result["results_input_sha256"] = digest(inputs[args.results])
    result["evaluator_sha256"] = digest(inputs[Path(__file__)])
    write_new(args.output, result)
    print(json.dumps({key: result[key] for key in ("positive_subjects", "negative_subjects", "counts", "field_counts")}, sort_keys=True))


if __name__ == "__main__":
    main()
