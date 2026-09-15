from __future__ import annotations

import io
import json
import sys
import tarfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from public_evaluate import covered
from public_measure import summary
from public_runtime import docker_arguments
from public_sources import digest, extract_archive, verify_cache, write_json


def archive(path: Path, entries: list[tuple[str, str]]) -> None:
    with tarfile.open(path, "w:gz") as handle:
        for name, value in entries:
            info = tarfile.TarInfo(name)
            if value.startswith("link:"):
                info.type = tarfile.SYMTYPE
                info.linkname = value[5:]
                handle.addfile(info)
            else:
                data = value.encode()
                info.size = len(data)
                handle.addfile(info, io.BytesIO(data))


@pytest.mark.parametrize("name", ["/etc/r2s-test", "root/../../escape", "root/C:/escape", "root/a\\b"])
def test_archive_rejects_escaping_paths(tmp_path: Path, name: str) -> None:
    path = tmp_path / "archive.tar.gz"
    archive(path, [(name, "bad")])
    with pytest.raises(ValueError):
        extract_archive(path, tmp_path / "source")


def test_links_are_recorded_without_following(tmp_path: Path) -> None:
    path = tmp_path / "archive.tar.gz"
    archive(path, [("root/source.py", "print('safe')"), ("root/escape", "link:/etc/passwd")])
    result = extract_archive(path, tmp_path / "source")
    assert not (tmp_path / "source/escape").exists()
    assert result["skipped"][0]["path"] == "escape"
    assert len(result["files"]) == 1


def test_duplicate_and_multi_root_archives_fail(tmp_path: Path) -> None:
    for index, names in enumerate([("a/file", "a/file"), ("a/file", "b/file")]):
        path = tmp_path / f"{index}.tar.gz"
        archive(path, [(name, "x") for name in names])
        with pytest.raises(ValueError):
            extract_archive(path, tmp_path / str(index))


def test_cache_rejects_partial_or_modified_source(tmp_path: Path) -> None:
    record = {"repository": "test/repo", "commit_sha": "a" * 40}
    with pytest.raises(FileNotFoundError):
        verify_cache(tmp_path, record)
    source = tmp_path / "source"
    source.mkdir()
    path = source / "main.py"
    path.write_text("pass")
    write_json(tmp_path / "source.lock.json", dict(record, files={
        "main.py": {"sha256": digest(path), "bytes": 4},
    }))
    verify_cache(tmp_path, record)
    path.write_text("fail")
    with pytest.raises(ValueError, match="CONTENT_MISMATCH"):
        verify_cache(tmp_path, record)


def test_coverage_keeps_fetch_failures_and_excludes_secondary() -> None:
    result = summary([
        {"set": "core", "status": "STATIC_READY", "stars_at_benchmark": 30000,
         "attempted": True, "completed": True},
        {"set": "core", "status": "FETCH_ERROR", "stars_at_benchmark": 10000},
        {"set": "edge", "status": "STATIC_READY", "stars_at_benchmark": 5000,
         "attempted": True, "completed": True},
    ])
    assert result["star_weighted_repository_coverage"] == 0.75
    assert result["high_star_public_repositories_tested"] == 1
    assert result["high_star_selected"] == 2


def test_option_on_another_command_is_not_coverage() -> None:
    fact = {"kind": "option", "value": "--check"}
    generated = [{"predicate": "supports_option", "value": {"option": "--check"},
                  "subject": "unrelated", "emitted": True}]
    assert not covered(fact, generated, "black")


def test_subcommand_coverage_uses_command_path() -> None:
    fact = {"kind": "subcommand", "value": "issue create"}
    generated = [{
        "predicate": "provides_subcommand",
        "subject": "gh",
        "value": {"command_path": "issue list"},
        "emitted": True,
    }]
    assert not covered(fact, generated, "gh")
    generated[0]["value"]["command_path"] = "issue create"
    assert covered(fact, generated, "gh")
    generated[0]["subject"] = "other"
    assert not covered(fact, generated, "gh")
    del generated[0]["subject"]
    assert not covered(fact, generated, "gh")


def test_option_on_different_subcommand_is_not_coverage() -> None:
    fact = {"kind": "option", "value": "--json", "command_path": "pr list"}
    generated = [{"predicate": "supports_option", "subject": "gh", "emitted": True,
                  "value": {"command": "gh", "command_path": "issue list", "option": "--json"}}]
    assert not covered(fact, generated, "gh")
    generated[0]["value"]["command_path"] = "pr list"
    assert covered(fact, generated, "gh")


def test_task_can_require_a_second_executable() -> None:
    fact = {"kind": "command", "value": "webpack-cli"}
    generated = [{"predicate": "provides_cli", "emitted": True, "value": {"command": "webpack-cli"}}]
    assert covered(fact, generated, "webpack")


def test_sandbox_has_no_network_or_host_secrets(tmp_path: Path) -> None:
    command = docker_arguments("sha256:test", "test", tmp_path, tmp_path)
    assert "--network=none" in command
    assert "--read-only" in command
    assert "--cap-drop=ALL" in command
    assert "--user=65534:65534" in command
    assert "--pids-limit=64" in command
    assert "--security-opt=no-new-privileges" in command
    assert "docker.sock" not in json.dumps(command)
