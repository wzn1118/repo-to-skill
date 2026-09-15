import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from taskset import validate


def test_taskset_has_thirty_pinned_tasks() -> None:
    root = Path(__file__).parents[1]
    taskset = json.loads((root / "benchmark/taskset-v1.json").read_text())
    metadata = json.loads((root / "benchmark/repository-metadata.json").read_text())
    assert validate(taskset, metadata) == []
    assert len(taskset["tasks"]) == 30
