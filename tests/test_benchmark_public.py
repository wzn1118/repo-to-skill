from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "benchmark_public", ROOT / "scripts" / "benchmark_public.py"
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _record(repository: str, stars: int, status: str) -> dict[str, object]:
    return {
        "repository": repository,
        "id": repository.replace("/", "-"),
        "tier": "A" if stars >= 30000 else "B",
        "set": "core",
        "benchmark_area": "test-cli",
        "ground_truth": False,
        "stars_at_benchmark": stars,
        "forks_at_benchmark": 1,
        "benchmark_date": "2026-09-14",
        "commit_sha": "a" * 40,
        "default_branch": "main",
        "archived": False,
        "language": "Python",
        "license": "MIT",
        "metadata_status": "OK",
        "analysis": {"status": status},
    }


def test_star_weighted_coverage_uses_tested_core_repositories() -> None:
    snapshot = {
        "schema_version": 1,
        "benchmark": "test",
        "benchmark_date": "2026-09-14",
        "star_policy": {"core_minimum": 0, "tier_a_minimum": 0, "tier_b_minimum": 0},
        "repositories": [
            _record("owner/ready", 30000, "STATIC_READY"),
            _record("owner/review", 10000, "REVIEW_REQUIRED"),
        ],
    }

    report = MODULE.build_report(snapshot)

    assert report["headline"]["high_star_public_repositories_tested"] == 2
    assert report["metrics"]["star_weighted_repository_coverage"] == 0.75
    assert report["metrics"]["hallucinated_executable_facts"] is None


def test_not_tested_repositories_are_excluded_from_coverage() -> None:
    snapshot = {
        "schema_version": 1,
        "benchmark": "test",
        "benchmark_date": "2026-09-14",
        "star_policy": {"core_minimum": 0, "tier_a_minimum": 0, "tier_b_minimum": 0},
        "repositories": [_record("owner/pending", 30000, "NOT_TESTED")],
    }

    report = MODULE.build_report(snapshot)

    assert report["headline"]["high_star_public_repositories_tested"] == 0
    assert report["metrics"]["star_weighted_repository_coverage"] is None


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
