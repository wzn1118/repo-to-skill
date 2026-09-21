import json
from pathlib import Path

import pytest

from r2s.analyzers import discover
from r2s.bundle_validation import write_lock
from r2s.discovery_contract import parse_discovery
from r2s.generator import generate, validate_path
from r2s.planner import plan
from r2s.storage import compilation_root, write_discovery
from r2s.workflows import WorkflowRequest

SOURCE = '''import argparse
def main():
    parser = argparse.ArgumentParser()
    children = parser.add_subparsers(required=True)
    run = children.add_parser("run")
    run.add_argument("source")
    run.add_argument("--output", required=True)
    run.add_argument("--format", choices=["json", "csv"], default="json")
    run.add_argument("--limit", type=int, default=10)
    group = run.add_mutually_exclusive_group()
    group.add_argument("--quiet", action="store_true")
    group.add_argument("--verbose", action="store_true")
    parser.parse_args()
'''


def discovery_at(root: Path):
    root.mkdir()
    (root / "LICENSE").write_text("MIT\n")
    (root / "pyproject.toml").write_text('[project.scripts]\ndemo="main:main"\n')
    (root / "main.py").write_text(SOURCE)
    return parse_discovery(discover(root).to_dict())


def request():
    return WorkflowRequest.model_validate({"title": "Export supplied data", "steps": [{
        "command": "demo", "path": ["run"],
        "parameters": {"source": ["input.txt"], "--output": ["output.json"], "--format": ["json"], "--limit": ["5"]},
        "expected_observation": "output.json contains the requested JSON records",
    }]})


def test_task_invocation_roundtrip_and_independent_validation(tmp_path):
    discovery = discovery_at(tmp_path / "repo")
    workflow = request()
    workflow.steps.append(workflow.steps[0].model_copy(deep=True))
    workflow.steps[1].parameters["--format"] = ["csv"]
    procedures = plan(discovery, "导出 JSON 文件", workflow=workflow)
    assert len(procedures[0].steps) == 2
    assert procedures[0].steps[0].arguments == ("run", "--output", "output.json", "--format", "json", "--limit", "5", "input.txt")
    result = generate(discovery, "导出 JSON 文件", tmp_path / "out", "portable", workflow=workflow)
    assert result.root
    bundle = Path(result.bundles[0])
    assert not validate_path(bundle)
    value = json.loads((bundle / "PROVENANCE.json").read_text())
    value["procedure"]["steps"][0]["arguments"].append("--invented")
    (bundle / "PROVENANCE.json").write_text(json.dumps(value))
    write_lock(bundle)
    assert validate_path(bundle)


@pytest.mark.parametrize(("change", "error"), [
    ({"--format": ["xml"]}, "CHOICE"),
    ({"--limit": ["five"]}, "TYPE"),
    ({"--output": []}, "ARITY"),
    ({"--invented": []}, "UNKNOWN"),
    ({"--quiet": [], "--verbose": []}, "EXCLUSIVE"),
    ({"source": ["--not-a-file"]}, "AMBIGUOUS"),
    ({"source": ["bad\nvalue"]}, "INVALID"),
])
def test_invalid_task_bindings_fail_before_generation(tmp_path, change, error):
    discovery = discovery_at(tmp_path / "repo")
    workflow = request()
    workflow.steps[0].parameters.update(change)
    with pytest.raises((ValueError, TypeError), match=error):
        plan(discovery, "export", workflow=workflow)


def test_required_input_and_subcommand_ownership(tmp_path):
    discovery = discovery_at(tmp_path / "repo")
    workflow = request()
    del workflow.steps[0].parameters["--output"]
    with pytest.raises(ValueError, match="REQUIRED"):
        plan(discovery, "export", workflow=workflow)
    workflow = request()
    workflow.steps[0].path = []
    with pytest.raises(ValueError, match="WRONG_OWNER|SELECT_LEAF"):
        plan(discovery, "export", workflow=workflow)


def test_workflow_inputs_participate_in_compilation_identity(tmp_path):
    discovery = discovery_at(tmp_path / "repo")
    run = write_discovery(discovery, tmp_path / "runs")
    workflow = request()
    first = compilation_root(run, "export", "portable", workflow=workflow)
    workflow.steps[0].parameters["--limit"] = ["6"]
    second = compilation_root(run, "export", "portable", workflow=workflow)
    assert first != second


def test_click_positionals_are_ordered_and_scoped(tmp_path):
    root = tmp_path / "repo"
    discovery_at(root)
    (root / "main.py").write_text('''import click
@click.command()
@click.argument("first")
@click.argument("rest", nargs=-1)
@click.option("--check", is_flag=True)
def main(first, rest, check):
    pass
''')
    discovery = parse_discovery(discover(root).to_dict())
    claims = [claim for claim in discovery.claims if claim.predicate == "supports_argument"]
    assert [claim.object["argument"] for claim in claims] == ["first", "rest"]
    workflow = WorkflowRequest.model_validate({"title": "Check files", "steps": [{"command": "demo", "parameters": {"first": ["a.py"], "rest": ["b.py", "c.py"], "--check": []}, "expected_observation": "Files are checked"}]})
    assert plan(discovery, "check", workflow=workflow)[0].steps[0].arguments == ("--check", "a.py", "b.py", "c.py")
