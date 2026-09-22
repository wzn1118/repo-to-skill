from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import PurePosixPath
from typing import Literal

from r2s.domain import InventoryEntry
from r2s.serialization import canonical_sha256

TEST_PARTS = frozenset({
    ".fixture", ".fixtures", "test", "tests", "testdata", "fixture", "fixtures",
    "__tests__", "__fixtures__", "__utils__", "e2e", "dev",
})
EXAMPLE_PARTS = frozenset({"example", "examples", "demo", "demos", "benchmark", "benchmarks"})
MANIFEST_NAMES = frozenset({"package.json", "pyproject.toml", "setup.cfg", "go.mod", "Cargo.toml"})
PRIORITY_NAMES = MANIFEST_NAMES | {"go.work", "LICENSE", "LICENSE.txt", "LICENSE.md", "COPYING"}
SOURCE_SUFFIXES = frozenset({".py", ".go", ".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx", ".rs"})
INCOMPLETE_REASONS = frozenset({
    "SCAN_FILE_BUDGET", "SCAN_BYTE_BUDGET", "WORKSPACE_FILE_BUDGET", "WORKSPACE_BYTE_BUDGET",
    "ROLE_FILE_BUDGET", "ROLE_BYTE_BUDGET", "FILE_TOO_LARGE",
})


@dataclass(frozen=True)
class ScanPolicy:
    max_inventory_entries: int = 100_000
    max_directories: int = 25_000
    max_depth: int = 64
    max_files: int = 10_000
    max_workspace_files: int = 6_000
    max_nonproduct_files: int = 1_000
    max_file_bytes: int = 2 * 1024 * 1024
    max_bytes: int = 128 * 1024 * 1024
    max_workspace_bytes: int = 64 * 1024 * 1024
    max_nonproduct_bytes: int = 16 * 1024 * 1024

    def __post_init__(self) -> None:
        if any(type(value) is not int or value <= 0 for value in asdict(self).values()):
            raise ValueError("SCAN_POLICY_INVALID")

    @property
    def id(self) -> str:
        return "workspace-bounded-v1:" + canonical_sha256({
            "limits": asdict(self), "test_parts": sorted(TEST_PARTS),
            "example_parts": sorted(EXAMPLE_PARTS), "manifests": sorted(MANIFEST_NAMES),
            "priority_names": sorted(PRIORITY_NAMES), "source_suffixes": sorted(SOURCE_SUFFIXES),
        })


def scan_policy_for(profile: str) -> ScanPolicy:
    if profile == "default":
        return ScanPolicy()
    if profile == "expanded":
        return ScanPolicy(max_files=40_000, max_workspace_files=30_000,
                          max_nonproduct_files=20_000, max_file_bytes=16 * 1024 * 1024,
                          max_bytes=512 * 1024 * 1024, max_workspace_bytes=384 * 1024 * 1024,
                          max_nonproduct_bytes=256 * 1024 * 1024)
    raise ValueError("SCAN_PROFILE_INVALID")


def scan_profile_for_id(policy_id: str) -> str:
    for profile in ("default", "expanded"):
        identifier = scan_policy_for(profile).id
        if policy_id == identifier or policy_id.startswith(identifier + ":"):
            return profile
    raise ValueError("EXECUTION_SCAN_POLICY_UNSUPPORTED")


def path_role(path: str) -> Literal["product", "test", "example"]:
    parts = {part.casefold() for part in PurePosixPath(path).parts[:-1]}
    if parts & TEST_PARTS:
        return "test"
    if parts & EXAMPLE_PARTS:
        return "example"
    return "product"


def workspace_roots(paths: list[str]) -> set[str]:
    return {".", *(str(PurePosixPath(path).parent) for path in paths if PurePosixPath(path).name in MANIFEST_NAMES)}


def workspace_for(path: str, roots: set[str]) -> str:
    return next((str(parent) for parent in PurePosixPath(path).parents if str(parent) in roots), ".")


def scan_coverage(inventory: list[InventoryEntry] | tuple[InventoryEntry, ...], policy_id: str) -> dict[str, object]:
    roots = workspace_roots([item.path for item in inventory])
    workspaces: dict[str, Counter[str]] = {}
    reasons: Counter[str] = Counter()
    for item in inventory:
        counters = workspaces.setdefault(workspace_for(item.path, roots), Counter())
        counters["inventory_entries"] += 1
        counters["hashed_files"] += int(item.content_sha256 is not None)
        counters["analyzed_files"] += int(item.classification == "source")
        counters["hashed_bytes"] += item.size if item.content_sha256 is not None else 0
        if item.reason in INCOMPLETE_REASONS:
            counters["budget_skipped_files"] += 1
            reasons[item.reason] += 1
    return {
        "format": "r2s-scan-coverage-v1", "policy_id": policy_id,
        "complete_within_policy": not reasons if policy_id.startswith("workspace-bounded-v1:") else None,
        "inventory_entries": len(inventory),
        "content_files_read": sum(item.content_sha256 is not None or item.reason == "SENSITIVE_PATH_SKIPPED" for item in inventory),
        "analyzed_files": sum(item.classification == "source" for item in inventory),
        "content_bytes_read": sum(item.size for item in inventory if item.content_sha256 is not None or item.reason == "SENSITIVE_PATH_SKIPPED"),
        "budget_skipped_files": sum(reasons.values()), "budget_reasons": dict(sorted(reasons.items())),
        "workspaces": [{"root": root, **dict(sorted(counters.items()))} for root, counters in sorted(workspaces.items())],
        "scope": "Selected regular source content under the recorded policy; excluded content is unknown, not repository coverage",
    }


def bundle_scan_scope(inventory: list[InventoryEntry], policy_id: str) -> dict[str, object]:
    excluded = sum(item.reason in INCOMPLETE_REASONS for item in inventory)
    return {
        "policy_id": policy_id, "inventory_sha256": canonical_sha256([asdict(item) for item in inventory]),
        "complete_within_policy": excluded == 0 if policy_id.startswith("workspace-bounded-v1:") else None,
        "budget_skipped_files": excluded,
    }
