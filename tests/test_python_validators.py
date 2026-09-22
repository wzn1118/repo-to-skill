import json
from pathlib import Path

import pytest

from r2s.analyzers import discover
from r2s.discovery_contract import parse_discovery
from r2s.fact_contracts import parse_fact
from r2s.generator import generate, validate_path
from r2s.migration import migrate_discovery
from r2s.storage import load_discovery
from r2s.workflows import InvocationRequest, WorkflowRequest, bind_invocation

SOURCE = '''import click as cli
import re as regex
def compile_pattern(value: str):
    if "\\n" in value:
        value = "(?x)" + value
    compiled = regex.compile(value)
    return compiled
def check(context, parameter, value):
    try:
        return compile_pattern(value) if value is not None else None
    except regex.error as error:
        raise cli.BadParameter(f"Invalid pattern: {error}") from None
@cli.command()
@cli.option("--exclude", type=str, callback=check)
def main(exclude): pass
'''


def repository(root: Path, source: str = SOURCE) -> None:
    (root / "LICENSE").write_text("MIT")
    (root / "pyproject.toml").write_text('[project.scripts]\ndemo="cli:main"\n')
    (root / "cli.py").write_text(source)


def test_regex_callback_is_bound_without_import_or_execution(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    repository(source)
    discovery = parse_discovery(discover(source).to_dict())
    claim = next(item for item in discovery.claims if item.object.get("option") == "--exclude")
    assert claim.object["semantics"]["validation"] == "python_regex"
    assert claim.object["shape"]["unknown_reasons"] == ()
    sources = [item for item in discovery.evidence if item.id in claim.evidence_ids]
    assert {"python.regex_validator", "python.regex_compiler"} <= {item.kind for item in sources}
    request = InvocationRequest(command="demo", parameters={"--exclude": [r".*\.tmp$"]}, expected_observation="Temporary files skipped")
    workflow = WorkflowRequest(title="Exclude temporary files", steps=[request])
    result = generate(discovery, workflow.title, tmp_path / "build", "portable", workflow=workflow)
    assert not validate_path(Path(result.bundles[0]))
    for value in ["[", "(?P<", "x{999999999999999999999}"]:
        with pytest.raises(ValueError, match="PARAMETER_REGEX_INVALID"):
            bind_invocation(discovery.claims, request.model_copy(update={"parameters": {"--exclude": [value]}}), "user_input")


@pytest.mark.parametrize(("before", "after"), [
    ('regex.compile(value)', 'custom_compile(value)'),
    ('return compiled', 'touch_disk(); return compiled'),
    ('from None', 'from side_effect()'),
    ('regex.error', 'Exception'),
    ('return compile_pattern(value) if value is not None else None', 'return compile_pattern("fixed") if value is not None else None'),
    ('import re as regex', 'import fake_re as regex'),
    ('import re as regex', 'import re as regex\nregex.compile = custom_compile'),
    ('def check(context, parameter, value):', 'def check(regex, parameter, value):'),
    ('callback=check', 'callback=check, cls=CustomOption'),
    ('@cli.command()', 'check = other_callback\n@cli.command()'),
])
def test_unproven_callback_remains_unknown(tmp_path, before, after):
    repository(tmp_path, SOURCE.replace(before, after))
    discovery = discover(tmp_path)
    claim = next(item for item in discovery.claims if item.object.get("option") == "--exclude")
    assert "custom_click_behavior" in claim.object["shape"]["unknown_reasons"]
    assert "validation" not in claim.object.get("semantics", {})


def test_repository_cannot_impersonate_standard_regex_module(tmp_path):
    repository(tmp_path)
    (tmp_path / "re.py").write_text("def compile(value): return 'fake'\n")
    claim = next(item for item in discover(tmp_path).claims if item.object.get("option") == "--exclude")
    assert "validation" not in claim.object.get("semantics", {})


def test_15_import_preserves_existing_fields_without_inventing_validators(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    repository(source, SOURCE.replace(", callback=check", ""))
    payload = discover(source).to_dict()
    payload["schema_version"] = "1.5.0"
    original = tmp_path / "legacy.json"
    original.write_text(json.dumps(payload))
    previous = original.read_bytes()
    with pytest.raises(ValueError, match="MIGRATION_REQUIRED"):
        parse_discovery(payload)
    result = migrate_discovery(original, tmp_path / "migrations")
    migrated = load_discovery(Path(result["run_root"]))
    assert migrated.schema_version == "1.6.0"
    assert not any("validation" in item.object.get("semantics", {}) for item in migrated.claims)
    assert original.read_bytes() == previous
    assert any(item.code == "MIGRATION_REVIEW_REQUIRED" for item in migrated.findings)


def test_15_import_rejects_backdated_validation_semantics(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    repository(source)
    payload = discover(source).to_dict()
    payload["schema_version"] = "1.5.0"
    original = tmp_path / "legacy.json"
    original.write_text(json.dumps(payload))
    with pytest.raises(ValueError):
        migrate_discovery(original, tmp_path / "migrations")


@pytest.mark.parametrize("changes", [
    {"value_type": "int"},
    {"framework": "commander"},
    {"validation": "ascii_case_insensitive_choices", "framework": "cobra"},
    {"validation": "ascii_case_insensitive_choices", "framework": "cobra", "choices": ["cſv"]},
])
def test_validator_contract_rejects_incompatible_declarations(changes):
    semantics = {"framework": "click", "scope": "explicit_source_keywords", "value_type": "str", "validation": "python_regex", **changes}
    with pytest.raises(ValueError):
        parse_fact({"command": "demo", "option": "--input", "semantics": semantics})
