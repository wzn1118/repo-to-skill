import copy
import json
from pathlib import Path

import pytest

from r2s.analyzers import discover
from r2s.bundle_validation import write_lock
from r2s.discovery_contract import parse_discovery
from r2s.generator import generate, validate_path
from r2s.migration import migrate_discovery
from r2s.storage import load_discovery


def fixture(root: Path, source: str, helpers: str = "") -> Path:
    root.mkdir()
    (root / "LICENSE").write_text("MIT\n")
    (root / "pyproject.toml").write_text('[project.scripts]\ndemo="main:main"\n')
    (root / "main.py").write_text(source)
    if helpers:
        (root / "helpers.py").write_text(helpers)
    return root


SOURCE = """import argparse
from helpers import add_options

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--global')
    subparsers = parser.add_subparsers()
    def command(name):
        child = subparsers.add_parser(name)
        add_options(child)
        return child
    run = command('run')
    install = command(name='install')
    run.add_argument('--all-files')
    install.add_argument('--force')
    children = run.add_subparsers()
    nested = children.add_parser('inspect')
    nested.add_argument('--json')
    parser.parse_args()
"""
HELPER = """def add_options(parser):
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--config')
"""


def test_helpers_preserve_subcommand_owner_and_source_chain(tmp_path: Path) -> None:
    root = fixture(tmp_path / "source", SOURCE, HELPER)
    discovery = parse_discovery(discover(root).to_dict())
    assert {item.path for item in discovery.commands} == {(), ("run",), ("install",), ("run", "inspect")}
    claims = {item.id: item for item in discovery.claims}
    evidence = {item.id: item for item in discovery.evidence}
    by_path = {item.path: [claims[identifier].object["option"] for identifier in item.option_claim_ids] for item in discovery.commands}
    assert set(by_path[()]) == {"--global"}
    assert set(by_path[("run",)]) == {"--config", "--all-files"}
    assert set(by_path[("install",)]) == {"--config", "--force"}
    assert set(by_path[("run", "inspect")]) == {"--json"}
    for command in discovery.commands:
        if not command.path:
            continue
        declaration = claims[command.declaration_claim_id]
        for identifier in command.option_claim_ids:
            assert set(declaration.evidence_ids).issubset(claims[identifier].evidence_ids)
    for claim in discovery.claims:
        if claim.object.get("option") == "--config":
            assert "helpers.py" in {evidence[identifier].source.path for identifier in claim.evidence_ids}
            assert "python.call" in {evidence[identifier].kind for identifier in claim.evidence_ids}
            assert "python.parse" in {evidence[identifier].kind for identifier in claim.evidence_ids}
    result = generate(discovery, "use demo", tmp_path / "output", "portable")
    bundle = Path(result.bundles[0])
    assert not validate_path(bundle)
    reference = (bundle / "references/cli.md").read_text()
    assert "--all-files" not in reference.split("## `demo`", 1)[1].split("## ", 1)[0]
    assert "## `demo run inspect`" in reference


@pytest.mark.parametrize("mutation", ["path", "parent", "evidence", "command", "extra", "string", "unsafe", "duplicate"])
def test_external_graph_cannot_reassign_or_hide_child_facts(tmp_path: Path, mutation: str) -> None:
    payload = discover(fixture(tmp_path / "source", SOURCE, HELPER)).to_dict()
    child = next(item for item in payload["commands"] if item["path"] == ("run",))
    option = next(item for item in payload["claims"] if item["object"].get("option") == "--all-files")
    if mutation == "path":
        option["object"]["command_path"] = ()
    elif mutation == "parent":
        child["parent_claim_id"] = None
    elif mutation == "evidence":
        option["evidence_ids"] = option["evidence_ids"][-1:]
    elif mutation == "command":
        payload["commands"].remove(child)
    elif mutation == "extra":
        child["trusted"] = True
    elif mutation == "string":
        option["object"]["command_path"] = "run"
    elif mutation == "unsafe":
        option["object"]["command_path"] = ["run;touch"]
    else:
        payload["commands"].append(copy.deepcopy(child))
    with pytest.raises(ValueError):
        parse_discovery(payload)


def test_standalone_validation_checks_scoped_graph_after_relocking(tmp_path: Path) -> None:
    discovery = discover(fixture(tmp_path / "source", SOURCE, HELPER))
    result = generate(discovery, "use demo", tmp_path / "out", "portable")
    bundle = Path(result.bundles[0])
    provenance = bundle / "PROVENANCE.json"
    payload = json.loads(provenance.read_text())
    next(item for item in payload["commands"] if item["path"] == ["run"])["parent_claim_id"] = None
    provenance.write_text(json.dumps(payload))
    write_lock(bundle)
    assert "COMMAND_GRAPH_INVALID" in {item.code for item in validate_path(bundle)}


@pytest.mark.parametrize("body", [
    "children = external\n    child = command('run')",
    "child = command(*names)",
    "child = command(**names)",
    "child = command(dynamic)",
    "child = children.add_parser('run', aliases=['r'])",
    "if condition:\n        child = command('run')",
    "child = command('run')\n    child = command('run')",
])
def test_unknown_or_rebound_registration_does_not_invent_commands(tmp_path: Path, body: str) -> None:
    source = "import argparse\ndef main():\n    parser = argparse.ArgumentParser()\n    children = parser.add_subparsers()\n    def command(name):\n        return children.add_parser(name)\n    " + body + "\n    parser.parse_args()\n"
    discovery = discover(fixture(tmp_path / "source", source))
    assert not any(item.predicate == "supports_subcommand" for item in discovery.claims)


def test_parser_return_value_keeps_its_options(tmp_path: Path) -> None:
    source = "import argparse\ndef make():\n    parser=argparse.ArgumentParser()\n    parser.add_argument('--known')\n    return parser\ndef main():\n    parser=make()\n    parser.parse_args()\n"
    discovery = discover(fixture(tmp_path / "source", source))
    assert [item.object.get("option") for item in discovery.claims if item.predicate == "supports_option"] == ["--known"]


def test_legacy_root_claims_require_explicit_reviewed_migration(tmp_path: Path) -> None:
    source = fixture(tmp_path / "source", "def main(): pass\n")
    payload = discover(source).to_dict()
    payload.pop("commands")
    payload["schema_version"] = "1.2.0"
    original = tmp_path / "legacy.json"
    original.write_text(json.dumps(payload))
    content = original.read_bytes()
    with pytest.raises(ValueError, match="MIGRATION_REQUIRED"):
        parse_discovery(payload)
    migrated = migrate_discovery(original, tmp_path / "migrated")
    loaded = load_discovery(Path(migrated["run_root"]))
    assert loaded.schema_version == "1.6.0" and loaded.commands[0].path == ()
    assert migrated["report"]["original_schema"] == "1.2.0"
    assert migrated["report"]["readiness"] == "REVIEW_REQUIRED"
    assert content == original.read_bytes()


def test_registrations_after_first_parse_are_not_executable_facts(tmp_path: Path) -> None:
    source = "import argparse\ndef main():\n    parser=argparse.ArgumentParser()\n    parser.add_argument('--before')\n    parser.parse_args()\n    parser.add_argument('--late')\n    child=parser.add_subparsers().add_parser('late')\n    parser.parse_args()\n"
    discovery = discover(fixture(tmp_path / "source", source))
    assert [item.object.get("option") for item in discovery.claims if item.predicate == "supports_option"] == ["--before"]
    assert not any(item.predicate == "supports_subcommand" for item in discovery.claims)


@pytest.mark.parametrize("body", [
    "group=parser.add_argument_group()\n    group.add_argument('--false')\n    group.parse_args()",
    "parser.add_argument('--false', dynamic)\n    parser.parse_args()",
    "parser.add_argument('--false', *dynamic)\n    parser.parse_args()",
])
def test_invalid_parser_calls_do_not_support_options(tmp_path: Path, body: str) -> None:
    source = "import argparse\ndef main():\n    parser=argparse.ArgumentParser()\n    " + body + "\n"
    discovery = discover(fixture(tmp_path / "source", source))
    assert not any(item.predicate == "supports_option" for item in discovery.claims)


def test_command_path_schema_has_array_cardinality() -> None:
    from r2s.discovery_contract import discovery_schema

    schema = discovery_schema()["$defs"]
    child = schema["SubcommandValue"]["properties"]["command_path"]
    option = schema["OptionValue"]["properties"]["command_path"]
    assert child["minItems"] == 1 and child["maxItems"] == 16
    assert option["maxItems"] == 16
    assert "minLength" not in child and "maxLength" not in child
