import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import pytest

from r2s.analyzers import discover
from r2s.client_profiles import CLIENT_PROFILES
from r2s.compiler_identity import compiler_identity
from r2s.generator import generate
from r2s.storage import compilation_root, write_discovery

SOURCE = Path(__file__).parent / "fixtures/multi_cli"


def test_cache_key_changes_for_runtime_dependency_and_client_profile(tmp_path: Path) -> None:
    run = write_discovery(discover(SOURCE), tmp_path)
    original = compilation_root(run, "inspect options", "portable")
    assert compilation_root(run, "inspect   options", "portable") == original
    with patch("r2s.compiler_identity.version", return_value="99.0.0"):
        changed_dependency = compilation_root(run, "inspect options", "portable")
    assert changed_dependency != original
    with patch.dict(CLIENT_PROFILES, {"portable": replace(CLIENT_PROFILES["portable"], id="next-profile")}):
        changed_profile = compilation_root(run, "inspect options", "portable")
    assert changed_profile not in {original, changed_dependency}
    lock = json.loads((original / "compiler.lock.json").read_text())
    assert lock["compiler"]["sha256"] == compiler_identity("portable")["sha256"]
    assert {"planner.py", "documents.py", "generator.py", "bundle_validation.py"} <= set(lock["compiler"]["files"])


def test_full_and_capability_delta_builds_never_share_output(tmp_path: Path) -> None:
    discovery = discover(SOURCE)
    run = write_discovery(discovery, tmp_path)
    full = compilation_root(run, "inspect options", "codex")
    first_capability = {discovery.capabilities[0].id}
    partial = compilation_root(run, "inspect options", "codex", first_capability)
    assert full != partial
    full_result = generate(discovery, "inspect options", full, "codex")
    partial_result = generate(discovery, "inspect options", partial, "codex", first_capability)
    assert len(full_result.bundles) == 2
    assert len(partial_result.bundles) == 1
    assert all(Path(bundle).exists() for bundle in full_result.bundles)


def test_tampered_cache_identity_is_not_replaced(tmp_path: Path) -> None:
    discovery = discover(SOURCE)
    run = write_discovery(discovery, tmp_path)
    compiled = compilation_root(run, "inspect options", "portable")
    lock = compiled / "compiler.lock.json"
    lock.write_text("{}")
    with pytest.raises(ValueError, match="ARTIFACT_MISMATCH"):
        compilation_root(run, "inspect options", "portable")
    assert lock.read_text() == "{}"


def test_existing_discovery_is_verified_and_not_rewritten(tmp_path: Path) -> None:
    discovery = discover(SOURCE)
    run = write_discovery(discovery, tmp_path)
    before = {path.name: (path.read_bytes(), path.stat().st_mtime_ns) for path in run.iterdir()}
    assert write_discovery(discovery, tmp_path) == run
    assert before == {path.name: (path.read_bytes(), path.stat().st_mtime_ns) for path in run.iterdir()}
    claims = run / "claims.json"
    claims.write_text("[]")
    with pytest.raises(ValueError, match="ARTIFACT_MISMATCH"):
        write_discovery(discovery, tmp_path)
    assert claims.read_text() == "[]"


def test_short_id_collision_checks_full_request(tmp_path: Path) -> None:
    run = write_discovery(discover(SOURCE), tmp_path)
    from r2s.serialization import stable_id

    def collide(prefix: str, value: object) -> str:
        return "compile_" + "0" * 20 if prefix == "compile" else stable_id(prefix, value)

    with patch("r2s.storage.stable_id", side_effect=collide):
        first = compilation_root(run, "inspect options", "portable")
        original = (first / "compiler.lock.json").read_bytes()
        with pytest.raises(ValueError, match="ARTIFACT_MISMATCH"):
            compilation_root(run, "different goal", "portable")
        assert (first / "compiler.lock.json").read_bytes() == original


def test_generation_rejects_wrong_compilation_inputs(tmp_path: Path) -> None:
    discovery = discover(SOURCE)
    run = write_discovery(discovery, tmp_path)
    compiled = compilation_root(run, "inspect options", "portable")
    with pytest.raises(ValueError, match="COMPILATION_INPUT_MISMATCH"):
        generate(discovery, "use commands", compiled, "portable")
    assert not (compiled / "portable").exists()
    with pytest.raises(ValueError, match="COMPILATION_INPUT_MISMATCH"):
        generate(discovery, "inspect options", compiled, "codex")


def test_repeated_generation_verifies_bytes_and_never_overwrites_tampering(tmp_path: Path) -> None:
    discovery = discover(SOURCE)
    compiled = tmp_path / "compile"
    original = generate(discovery, "inspect options", compiled, "portable")
    paths = [path for path in compiled.rglob("*") if path.is_file()]
    before = {str(path): (path.read_bytes(), path.stat().st_mtime_ns) for path in paths}
    assert generate(discovery, "inspect  options", compiled, "portable") == original
    assert before == {str(path): (path.read_bytes(), path.stat().st_mtime_ns) for path in paths}
    skill = Path(original.bundles[0]) / "SKILL.md"
    skill.write_text("modified")
    with pytest.raises(ValueError, match="COMPILATION_OUTPUT_MISMATCH"):
        generate(discovery, "inspect options", compiled, "portable")
    assert skill.read_text() == "modified"


def test_changed_compiler_during_generation_cannot_publish(tmp_path: Path) -> None:
    original = compiler_identity("portable")
    changed = deepcopy(original)
    changed["files"]["generator.py"] = "0" * 64
    compiled = tmp_path / "compile"
    with (
        patch("r2s.generator.compiler_identity", side_effect=[original, changed]),
        pytest.raises(ValueError, match="COMPILER_CHANGED_DURING_GENERATION"),
    ):
        generate(discover(SOURCE), "inspect options", compiled, "portable")
    assert not list(compiled.iterdir())


def test_generation_refuses_unmanaged_outputs(tmp_path: Path) -> None:
    existing = tmp_path / "portable/old"
    existing.mkdir(parents=True)
    (existing / "SKILL.md").write_text("user content")
    with pytest.raises(ValueError, match="COMPILATION_OUTPUT_UNMANAGED"):
        generate(discover(SOURCE), "inspect options", tmp_path, "portable")
    assert (existing / "SKILL.md").read_text() == "user content"
