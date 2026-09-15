import copy
import json
from pathlib import Path

import pytest

from r2s.analyzers import discover
from r2s.cli import main
from r2s.generator import generate
from r2s.migration import migrate_discovery
from r2s.storage import load_discovery, write_discovery

FIXTURE = Path(__file__).parent / "fixtures/python_cli"


def test_migration_deduplicates_only_identical_evidence_and_preserves_source(tmp_path: Path) -> None:
    payload = discover(FIXTURE).to_dict()
    payload["evidence"].append(copy.deepcopy(payload["evidence"][0]))
    source = tmp_path / "legacy.json"
    source.write_text(json.dumps(payload), encoding="utf-8")
    original = source.read_bytes()
    migrated = migrate_discovery(source, tmp_path / "output")
    run = Path(migrated["run_root"])
    discovery = load_discovery(run)
    assert len(discovery.evidence) == len(payload["evidence"]) - 1
    assert migrated["report"]["removed_identical_evidence_ids"] == [payload["evidence"][0]["id"]]
    assert discovery.snapshot.resolved_commit_sha == payload["snapshot"]["resolved_commit_sha"]
    assert source.read_bytes() == original
    assert migrated["report"]["readiness"] == "REVIEW_REQUIRED"
    assert generate(discovery, "inspect options", tmp_path / "compiled", "portable").readiness.value == "REVIEW_REQUIRED"
    before = {path.name: path.stat().st_mtime_ns for path in run.iterdir()}
    assert migrate_discovery(source, tmp_path / "output") == migrated
    assert before == {path.name: path.stat().st_mtime_ns for path in run.iterdir()}


def test_migration_rejects_conflicting_duplicate_without_writing(tmp_path: Path) -> None:
    payload = discover(FIXTURE).to_dict()
    duplicate = copy.deepcopy(payload["evidence"][0])
    duplicate["confidence"] = 0.25
    payload["evidence"].append(duplicate)
    source = tmp_path / "legacy.json"
    source.write_text(json.dumps(payload), encoding="utf-8")
    output = tmp_path / "new"
    with pytest.raises(ValueError, match="MIGRATION_EVIDENCE_COLLISION"):
        migrate_discovery(source, output)
    assert not output.exists()


def test_migration_checks_run_envelope_and_rejects_nested_output(tmp_path: Path) -> None:
    source = write_discovery(discover(FIXTURE), tmp_path / "old")
    with pytest.raises(ValueError, match="MIGRATION_OUTPUT_INSIDE_SOURCE"):
        migrate_discovery(source, source / "new")
    original = {path.name: path.read_bytes() for path in source.iterdir()}
    migrated = migrate_discovery(source, tmp_path / "new")
    assert migrated["report"]["source_integrity"] == "envelope checked"
    assert original == {path.name: path.read_bytes() for path in source.iterdir()}
    (source / "claims.json").write_text("[]")
    with pytest.raises(ValueError, match="ARTIFACT_MISMATCH"):
        migrate_discovery(source, tmp_path / "other")


@pytest.mark.parametrize("mutation", ["future", "missing", "duplicate_key", "dangling"])
def test_migration_does_not_repair_ambiguous_or_invalid_inputs(tmp_path: Path, mutation: str) -> None:
    payload = discover(FIXTURE).to_dict()
    if mutation == "future":
        payload["schema_version"] = "2.0.0"
    elif mutation == "missing":
        del payload["claims"][0]["status"]
    elif mutation == "dangling":
        payload["capabilities"][0]["claim_ids"] = ["cl_" + "f" * 20]
    content = json.dumps(payload)
    if mutation == "duplicate_key":
        content = '{"schema_version":"1.2.0",' + content[1:]
    source = tmp_path / "legacy.json"
    source.write_text(content)
    with pytest.raises(ValueError):
        migrate_discovery(source, tmp_path / "new")
    assert not (tmp_path / "new").exists()


def test_cli_migration_produces_a_new_reviewable_run(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = tmp_path / "input.json"
    source.write_text(json.dumps(discover(FIXTURE).to_dict()))
    assert main(["migrate", str(source), "--output", str(tmp_path / "new")]) == 0
    response = json.loads(capsys.readouterr().out)
    assert (Path(response["run_root"]) / "migration.json").is_file()
    assert response["report"]["source_authenticity"] == "not_independently_authenticated"
