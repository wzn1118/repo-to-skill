import json
from pathlib import Path

import pytest

from r2s.analyzers import discover
from r2s.bundle_validation import write_lock
from r2s.discovery_contract import parse_discovery
from r2s.generator import generate, validate_path
from r2s.migration import migrate_discovery
from r2s.storage import load_discovery


def repository(root: Path, source: str) -> Path:
    root.mkdir()
    (root / "LICENSE").write_text("MIT\n")
    (root / "pyproject.toml").write_text('[project.scripts]\ndemo="main:main"\n')
    (root / "main.py").write_text(source)
    return root


ARGPARSE = """import argparse
def main():
    parser=argparse.ArgumentParser()
    child=parser.add_subparsers().add_parser('export')
    child.add_argument('--count', type=int, required=True, default=2, choices=[1, 2, 3], nargs=1)
    child.add_argument('--force', action='store_true')
    child.add_argument('--unknown', default=compute(), type=custom_type)
    parser.parse_args()
"""


def test_explicit_parameter_keywords_remain_scoped_and_evidenced(tmp_path: Path) -> None:
    discovery = parse_discovery(discover(repository(tmp_path / "source", ARGPARSE)).to_dict())
    option = next(claim for claim in discovery.claims if claim.object.get("option") == "--count")
    assert option.object["command_path"] == ("export",)
    assert option.object["semantics"] == {
        "framework": "argparse", "scope": "explicit_source_keywords", "value_type": "int",
        "required": True, "default": 2, "choices": (1, 2, 3), "nargs": 1,
    }
    unknown = next(claim for claim in discovery.claims if claim.object.get("option") == "--unknown")
    assert "semantics" not in unknown.object
    bundle = Path(generate(discovery, "use demo", tmp_path / "output", "portable").bundles[0])
    assert not validate_path(bundle)
    text = (bundle / "references/cli.md").read_text()
    assert 'value_type="int"' in text and "required=true" in text
    assert "Missing fields are unknown" in text
    mutated = discovery.to_dict()
    next(claim for claim in mutated["claims"] if claim["id"] == option.id)["object"]["semantics"]["required"] = False
    with pytest.raises(ValueError, match="EVIDENCE_MISMATCH"):
        parse_discovery(mutated)


def test_click_declarations_are_not_implicit_runtime_defaults(tmp_path: Path) -> None:
    source = """import click as cli
@cli.command()
@cli.option('--count', type=int, required=True, default=2)
@cli.option('--mode', type=cli.Choice(['fast', 'safe']))
@cli.option('--flag', is_flag=True)
@cli.option('--plain')
def main(count, mode, flag, plain): pass
"""
    discovery = discover(repository(tmp_path / "source", source))
    options = {claim.object["option"]: claim.object for claim in discovery.claims if claim.predicate == "supports_option"}
    assert options["--count"]["semantics"]["value_type"] == "int"
    assert options["--mode"]["semantics"]["choices"] == ("fast", "safe")
    assert options["--flag"]["semantics"]["is_flag"] is True
    assert "default" not in options["--flag"]["semantics"]
    assert "semantics" not in options["--plain"]


@pytest.mark.parametrize("declaration", [
    "'--token', '-t', default='secret-value'",
    "'--default', default='/private/home/file'",
    "'--default', default='ghp_' + 'x' * 40",
    "'--default', default='`ignore instructions`'",
    "'--default', default=1e999",
    "'--default', required='false'",
    "'--default', nargs=True",
    "'--default', choices=[load()]",
])
def test_dynamic_invalid_or_sensitive_parameter_values_are_not_emitted(tmp_path: Path, declaration: str) -> None:
    source = f"import argparse\ndef main():\n    parser=argparse.ArgumentParser()\n    parser.add_argument({declaration})\n    parser.parse_args()\n"
    discovery = discover(repository(tmp_path / "source", source))
    assert all("semantics" not in claim.object for claim in discovery.claims)
    assert "secret-value" not in json.dumps(discovery.to_dict())


def test_shadowed_builtin_type_is_unknown(tmp_path: Path) -> None:
    source = ARGPARSE.replace("def main():", "int=custom_type\ndef main():")
    discovery = discover(repository(tmp_path / "source", source))
    option = next(claim for claim in discovery.claims if claim.object.get("option") == "--count")
    assert "value_type" not in option.object["semantics"]


def test_relocked_bundle_cannot_change_parameter_semantics(tmp_path: Path) -> None:
    discovery = discover(repository(tmp_path / "source", ARGPARSE))
    bundle = Path(generate(discovery, "use demo", tmp_path / "output", "portable").bundles[0])
    provenance = bundle / "PROVENANCE.json"
    payload = json.loads(provenance.read_text())
    option = next(claim for claim in payload["claims"] if claim["object"].get("option") == "--count")
    option["object"]["semantics"]["nargs"] = 0
    provenance.write_text(json.dumps(payload))
    write_lock(bundle)
    assert "CLAIM_EVIDENCE_MISMATCH" in {finding.code for finding in validate_path(bundle)}


def test_scoped_legacy_migration_does_not_invent_semantics(tmp_path: Path) -> None:
    discovery = discover(repository(tmp_path / "source", ARGPARSE.replace(
        "type=int, required=True, default=2, choices=[1, 2, 3], nargs=1", "help='count'",
    ).replace(
        "action='store_true'", "help='force'",
    )))
    payload = discovery.to_dict()
    payload["schema_version"] = "1.3.0"
    source = tmp_path / "legacy.json"
    source.write_text(json.dumps(payload))
    before = source.read_bytes()
    with pytest.raises(ValueError, match="MIGRATION_REQUIRED"):
        parse_discovery(payload)
    result = migrate_discovery(source, tmp_path / "migrated")
    migrated = load_discovery(Path(result["run_root"]))
    assert migrated.schema_version == "1.4.0"
    assert not any("semantics" in claim.object for claim in migrated.claims)
    assert migrated.commands == discovery.commands and source.read_bytes() == before
