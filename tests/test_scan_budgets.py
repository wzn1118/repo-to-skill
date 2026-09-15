import json
import os
from dataclasses import replace
from pathlib import Path

import pytest

from r2s.analyzers import discover
from r2s.discovery_contract import parse_discovery
from r2s.generator import generate, install_codex_plugin, validate_path
from r2s.scan_policy import ScanPolicy, scan_coverage
from r2s.scanner import scan
from r2s.storage import load_discovery, write_discovery


def write(root: Path, relative: str, content: str = "pass\n") -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_tests_do_not_starve_product_and_partial_scan_cannot_be_ready(tmp_path: Path) -> None:
    source = tmp_path / "source"
    write(source, "LICENSE", "MIT\n")
    write(source, "package.json", json.dumps({"name": "tool", "bin": {"tool": "zz/cli.js"}}))
    write(source, "zz/cli.js", "console.log('tool')\n")
    for index in range(12):
        write(source, f"aaa/tests/sample-{index:02}.js")
    discovery = discover(source, scan_policy=ScanPolicy(max_files=6, max_nonproduct_files=2))
    assert len(discovery.inventory) == 15
    assert next(item for item in discovery.inventory if item.path == "zz/cli.js").classification == "source"
    assert len(discovery.capabilities) == 1
    assert any(item.reason == "ROLE_FILE_BUDGET" for item in discovery.inventory)
    assert generate(discovery, "use commands", tmp_path / "out", "portable").readiness.value == "REVIEW_REQUIRED"
    codex = generate(discovery, "use commands", tmp_path / "codex", "codex")
    assert codex.root is not None
    assert any(item.code == "SCAN_INCOMPLETE" for item in validate_path(Path(codex.root)))
    _, findings, _ = install_codex_plugin(Path(codex.root), tmp_path / "installed")
    assert any(item.code == "SCAN_INCOMPLETE" for item in findings)
    parse_discovery(discovery.to_dict())
    payload = discovery.to_dict()
    payload["findings"] = [item for item in payload["findings"] if item["code"] != "SCAN_INCOMPLETE"]
    with pytest.raises(ValueError, match="INCOMPLETE_SCAN_NOT_DECLARED"):
        parse_discovery(payload)


def test_workspace_round_robin_reserves_room_for_later_packages(tmp_path: Path) -> None:
    for package in ["alpha", "zeta"]:
        write(tmp_path, f"packages/{package}/package.json", "{}")
        for index in range(10):
            write(tmp_path, f"packages/{package}/source-{index:02}.js")
    result = scan(tmp_path, policy=ScanPolicy(max_files=4))
    paths = {path.relative_to(tmp_path).as_posix() for path in result.analyzable_files}
    assert paths == {f"packages/{package}/{name}" for package in ["alpha", "zeta"] for name in ["package.json", "source-00.js"]}
    assert len(result.inventory) == 22


def test_byte_budgets_skip_large_files_without_losing_small_files(tmp_path: Path) -> None:
    write(tmp_path, "a.py", "a" * 50)
    write(tmp_path, "b.py", "b" * 50)
    write(tmp_path, "c.py", "pass")
    result = scan(tmp_path, policy=ScanPolicy(max_bytes=60))
    assert {path.name for path in result.analyzable_files} == {"a.py", "c.py"}
    assert next(item for item in result.inventory if item.path == "b.py").reason == "SCAN_BYTE_BUDGET"
    assert scan_coverage(result.inventory, result.snapshot.scan_policy_id)["content_bytes_read"] == 54


def test_workspace_and_role_budgets_are_global_to_their_scope(tmp_path: Path) -> None:
    for index in range(5):
        write(tmp_path, f"packages/tool/file-{index}.go")
        write(tmp_path, f"tests/pkg-{index}/package.json", "{}")
    write(tmp_path, "packages/tool/go.mod", "module example/tool\n")
    result = scan(tmp_path, policy=ScanPolicy(max_workspace_files=3, max_nonproduct_files=2))
    reasons = {item.reason for item in result.inventory}
    assert {"WORKSPACE_FILE_BUDGET", "ROLE_FILE_BUDGET"} <= reasons


@pytest.mark.parametrize("limit", ["max_inventory_entries", "max_directories", "max_depth"])
def test_metadata_traversal_has_independent_hard_limits(tmp_path: Path, limit: str) -> None:
    write(tmp_path, "one/two/three/file.py")
    with pytest.raises(ValueError, match="SCAN_.*LIMIT_EXCEEDED"):
        scan(tmp_path, policy=replace(ScanPolicy(), **{limit: 2}))


def test_policy_identity_and_partial_scope_survive_storage(tmp_path: Path) -> None:
    source = tmp_path / "source"
    write(source, "LICENSE", "MIT\n")
    write(source, "a.py")
    write(source, "b.py")
    limited = discover(source, scan_policy=ScanPolicy(max_files=2))
    full = discover(source)
    assert limited.tree_sha256 != full.tree_sha256
    assert limited.snapshot.scan_policy_id != full.snapshot.scan_policy_id
    run = write_discovery(limited, tmp_path / "runs")
    assert load_discovery(run).to_dict() == limited.to_dict()
    coverage = json.loads((run / "scan.json").read_text())
    assert coverage["budget_skipped_files"] == 1
    (run / "scan.json").write_text("{}")
    with pytest.raises(ValueError, match="MISMATCH"):
        load_discovery(run)


def test_oversized_python_manifest_is_never_parsed(tmp_path: Path) -> None:
    write(tmp_path, "pyproject.toml", "this is invalid TOML" * 5)
    discovery = discover(tmp_path, scan_policy=ScanPolicy(max_file_bytes=10))
    assert not discovery.capabilities
    assert any(item.code == "SCAN_INCOMPLETE" for item in discovery.findings)


def test_analyzers_cannot_read_excluded_or_changed_sources(tmp_path: Path) -> None:
    first = write(tmp_path, "a.py", "first")
    second = write(tmp_path, "b.py", "second")
    result = scan(tmp_path, policy=ScanPolicy(max_files=1))
    with pytest.raises(ValueError, match="SOURCE_NOT_SCANNED"):
        result.read_text(second)
    first.write_text("other")
    with pytest.raises(ValueError, match="ANALYSIS_SOURCE_CHANGED"):
        result.read_text(first)


def test_tracked_source_in_normally_ignored_directory_is_included(tmp_path: Path) -> None:
    write(tmp_path, "build/main.py")
    assert not scan(tmp_path).analyzable_files
    result = scan(tmp_path, committed_blob_oids={"build/main.py": "a" * 40})
    assert [path.name for path in result.analyzable_files] == ["main.py"]


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="FIFO unsupported")
def test_special_file_after_content_budget_exhaustion_is_still_rejected(tmp_path: Path) -> None:
    write(tmp_path, "a.py")
    os.mkfifo(tmp_path / "z.py")
    with pytest.raises(ValueError, match="UNTRUSTED_SPECIAL_FILE"):
        scan(tmp_path, policy=ScanPolicy(max_files=1))


def test_large_sensitive_file_is_not_hashed_or_disclosed(tmp_path: Path) -> None:
    write(tmp_path, ".env", "secret" * 100)
    result = scan(tmp_path, policy=ScanPolicy(max_file_bytes=20))
    assert result.inventory[0].classification == "sensitive"
    assert result.inventory[0].content_sha256 is None
    assert result.inventory[0].reason == "FILE_TOO_LARGE"
    assert scan_coverage(result.inventory, result.snapshot.scan_policy_id)["content_bytes_read"] == 0
