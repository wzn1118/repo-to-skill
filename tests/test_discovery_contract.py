import copy
import json
from pathlib import Path
from typing import Any

import pytest

from r2s.analyzers import discover
from r2s.core import schema_catalog
from r2s.discovery_contract import parse_discovery, strict_json_loads
from r2s.domain import DiscoveryIR
from r2s.generator import generate
from r2s.storage import load_discovery, write_discovery

FIXTURE = Path(__file__).parent / "fixtures/python_cli"


@pytest.mark.parametrize(("section", "field", "value"), [
    ("claims", "executable_fact", "false"),
    ("claims", "status", "READY"),
    ("claims", "confidence", True),
    ("claims", "confidence", 1.5),
    ("claims", "confidence", float("nan")),
    ("evidence", "confidence", -0.1),
    ("evidence", "id", "unscoped"),
    ("inventory", "size", True),
    ("inventory", "size", "123"),
    ("inventory", "path", "../outside"),
    ("inventory", "classification", "trusted"),
    ("capabilities", "support_level", "READY"),
])
def test_external_ir_rejects_wrong_scalar_types(section: str, field: str, value: Any) -> None:
    payload = discover(FIXTURE).to_dict()
    payload[section][0][field] = value
    with pytest.raises((ValueError, TypeError)):
        DiscoveryIR.from_dict(payload)


@pytest.mark.parametrize("section", ["claims", "evidence", "capabilities", "inventory"])
def test_nested_unknown_and_missing_fields_are_rejected(section: str) -> None:
    payload = discover(FIXTURE).to_dict()
    payload[section][0]["trusted_override"] = True
    with pytest.raises(ValueError):
        parse_discovery(payload)
    del payload[section][0]["trusted_override"]
    del payload[section][0][next(iter(payload[section][0]))]
    with pytest.raises(ValueError):
        parse_discovery(payload)


def test_security_defaults_cannot_be_inferred_when_loading() -> None:
    payload = discover(FIXTURE).to_dict()
    del payload["claims"][0]["status"]
    with pytest.raises(ValueError, match="CONTRACT_FIELDS_MISSING"):
        parse_discovery(payload)
    payload = discover(FIXTURE).to_dict()
    del payload["snapshot"]
    with pytest.raises(ValueError, match="MIGRATION_REQUIRED"):
        parse_discovery(payload)


def test_future_version_is_not_silently_accepted() -> None:
    payload = discover(FIXTURE).to_dict()
    payload["schema_version"] = "99.0.0"
    with pytest.raises(ValueError, match="SCHEMA_UNSUPPORTED"):
        parse_discovery(payload)


def test_dangling_and_reused_ids_fail_before_generation(tmp_path: Path) -> None:
    payload = discover(FIXTURE).to_dict()
    payload["capabilities"][0]["claim_ids"] = ["cl_" + "0" * 20]
    with pytest.raises(ValueError, match="IR_CAPABILITY_CLAIM_MISSING"):
        parse_discovery(payload)
    discovery = discover(FIXTURE)
    discovery.evidence.append(discovery.evidence[0])
    with pytest.raises(ValueError, match="IR_DUPLICATE_EVIDENCE_ID"):
        generate(discovery, "inspect options", tmp_path, "portable")
    assert not list(tmp_path.iterdir())


def test_evidence_must_match_inventory_and_commit() -> None:
    payload = discover(FIXTURE).to_dict()
    payload["evidence"][0]["source"]["content_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="SOURCE_MISMATCH"):
        parse_discovery(payload)
    payload = discover(FIXTURE).to_dict()
    payload["evidence"][0]["source"]["commit_sha"] = "a" * 40
    with pytest.raises(ValueError, match="COMMIT_MISMATCH"):
        parse_discovery(payload)


def test_option_from_another_entrypoint_is_not_a_capability() -> None:
    payload = discover(Path(__file__).parent / "fixtures/multi_cli").to_dict()
    beta = next(claim for claim in payload["claims"] if claim["predicate"] == "supports_option" and claim["subject"] == "beta")
    payload["capabilities"][0]["claim_ids"] = (*payload["capabilities"][0]["claim_ids"], beta["id"])
    with pytest.raises(ValueError, match="CAPABILITY_OPTION_OWNER_MISMATCH"):
        parse_discovery(payload)


def test_duplicate_json_keys_fail_even_without_database(tmp_path: Path) -> None:
    run = write_discovery(discover(FIXTURE), tmp_path)
    (tmp_path / "runs.sqlite3").unlink()
    path = run / "discovery.json"
    original = path.read_text()
    path.write_text('{"schema_version":"99.0.0",' + original[1:])
    with pytest.raises(ValueError, match="JSON_DUPLICATE_KEY"):
        load_discovery(run)


def test_nested_json_limits_and_non_finite_values() -> None:
    for payload in ['{"value":NaN}', '{"nested":{"same":1,"same":2}}', "[" * 80 + "0" + "]" * 80]:
        with pytest.raises(ValueError):
            strict_json_loads(payload)


def test_schema_and_runtime_share_nested_contracts() -> None:
    schema = schema_catalog()
    for name in ("Evidence", "Claim", "SourceLocation", "Capability", "InventoryEntry", "RepositorySnapshot"):
        model = schema["$defs"][name]
        assert model["additionalProperties"] is False
        assert set(model["required"]) == set(model["properties"])
    assert schema["$defs"]["Claim"]["properties"]["confidence"]["maximum"] == 1
    payload = discover(FIXTURE).to_dict()
    assert parse_discovery(json.loads(json.dumps(payload))).to_dict() == copy.deepcopy(payload)
    checked_in = Path(__file__).resolve().parents[1] / "schemas/discovery.schema.json"
    assert json.loads(checked_in.read_text()) == schema


@pytest.mark.parametrize("value", [
    {"command": "tool", "target": "tool:main", "trusted_override": True},
    {"command": "tool", "target": False},
    {"command": "tool", "option": "--safe;touch"},
    {"command": "tool", "option": "--help"},
    {"command": "missing", "target": "tool:main"},
])
def test_claim_payload_shape_and_witness_must_match(value: dict[str, Any]) -> None:
    payload = discover(FIXTURE).to_dict()
    entrypoint = next(claim for claim in payload["claims"] if claim["predicate"] == "provides_cli")
    entrypoint["object"] = value
    with pytest.raises(ValueError):
        parse_discovery(payload)


def test_shared_entrypoint_keeps_one_evidence_record(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname="alias"\n[project.scripts]\nfirst="tool:main"\nsecond="tool:main"\n'
    )
    (tmp_path / "tool.py").write_text("def main(): pass\n")
    discovery = discover(tmp_path)
    assert len([item for item in discovery.evidence if item.kind == "python.symbol"]) == 1
    assert len(discovery.capabilities) == 2
    parse_discovery(discovery.to_dict())
