from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "benchmark_public", ROOT / "scripts" / "benchmark_public.py"
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_metadata_cannot_overwrite_historical_snapshot(tmp_path: Path) -> None:
    path = tmp_path / "metadata.json"
    path.write_text("historical snapshot")
    with pytest.raises(FileExistsError, match="immutable"):
        MODULE.write_metadata(ROOT / "benchmark/corpus.yaml", path)
    assert path.read_text() == "historical snapshot"


def test_metadata_does_not_contain_measurement_results() -> None:
    metadata = json.loads((ROOT / "benchmark/repository-metadata.json").read_text())
    assert MODULE.validate_snapshot(metadata) == []
    for record in metadata["repositories"]:
        assert not {"analysis", "snapshot_status", "fetch_error"} & record.keys()


def test_metadata_snapshot_has_required_pinned_fields() -> None:
    metadata = json.loads(
        (ROOT / "benchmark" / "repository-metadata.json").read_text(encoding="utf-8")
    )
    core = [record for record in metadata["repositories"] if record["set"] == "core"]

    assert len(core) >= 30
    assert len([record for record in core if record["tier"] == "A"]) >= 10
    assert len([record for record in core if record["tier"] == "B"]) >= 20
    for record in metadata["repositories"]:
        assert len(record["commit_sha"]) == 40
        assert record["benchmark_date"] == metadata["benchmark_date"]
