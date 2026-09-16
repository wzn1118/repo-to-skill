from pathlib import Path

import pytest

from r2s.analyzers import discover
from r2s.generator import generate
from r2s.planner import plan

FIXTURE = Path(__file__).parent / "fixtures/python_cli"


@pytest.mark.parametrize("goal", ["使用 demo 导出结果", "导出结果", "use demo to export results", "demo --unknown", "delete files with demo"])
def test_command_mention_does_not_claim_task_understanding(tmp_path: Path, goal: str) -> None:
    discovery = discover(FIXTURE)
    assert plan(discovery, goal) == []
    result = generate(discovery, goal, tmp_path / "out", "portable")
    assert not result.bundles and result.outcome.value == "NEEDS_INPUT"


@pytest.mark.parametrize("goal", ["Use the demo CLI", "使用 demo", "inspect demo options", "demo", "查看 demo 的选项"])
def test_explicit_command_exploration_is_still_available(goal: str) -> None:
    assert len(plan(discover(FIXTURE), goal)) == 1
