import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from task_oracle_worker import contained, oracle_failures


def test_oracle_rejects_wrong_contents_even_after_successful_exit(tmp_path: Path) -> None:
    (tmp_path / "result.py").write_text("wrong\n")
    oracle = {"files_exact": {"result.py": "value = 1\n"}}
    assert oracle_failures(tmp_path, oracle, "", "") == ["files_exact:result.py:mismatch"]
    (tmp_path / "result.py").write_text("value = 1\n")
    assert oracle_failures(tmp_path, oracle, "", "") == []
    (tmp_path / "unexpected").write_text("x")
    assert oracle_failures(tmp_path, {"absent": ["unexpected"]}, "", "")
    assert oracle_failures(tmp_path, {"stdout_exact": "expected"}, "wrong", "")


@pytest.mark.parametrize("path", ["../escape", "/tmp/escape", "C:/escape", "a\\b", "a/../b"])
def test_task_paths_are_contained(tmp_path: Path, path: str) -> None:
    with pytest.raises(ValueError):
        contained(tmp_path, path)


def test_taskset_pins_and_oracles_are_explicit() -> None:
    root = Path(__file__).resolve().parents[1]
    tasks = json.loads((root / "benchmark/tasks/cli-value-v1.json").read_text())["tasks"]
    metadata = json.loads((root / "benchmark/repository-metadata.json").read_text())
    pins = {item["id"]: item["commit_sha"] for item in metadata["repositories"]}
    assert len(tasks) == len({task["id"] for task in tasks}) == 30
    for identifier in ("black", "pre-commit", "cookiecutter"):
        assert sum(task["repository_id"] == identifier for task in tasks) == 10
    for task in tasks:
        assert task["commit_sha"] == pins[task["repository_id"]]
        assert task["oracle"] and task["steps"]
        assert not any("--help" in step["argv"] or "--version" in step["argv"] for step in task["steps"])
