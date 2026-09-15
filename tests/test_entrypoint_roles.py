import json
from pathlib import Path

import pytest

from r2s.analyzers import discover


@pytest.mark.parametrize("directory", [
    "pnpr/.fixtures/packages/tool", "pnpm/__utils__/server", "pnpm/dev",
    "testdata/fake", "tests/nested", "packages/test-runner",
])
def test_javascript_workspace_roles_use_exact_path_components(tmp_path: Path, directory: str) -> None:
    workspace = tmp_path / directory
    workspace.mkdir(parents=True)
    (workspace / "package.json").write_text(json.dumps({"name": "tool", "bin": {"tool": "cli.js"}}))
    (workspace / "cli.js").write_text("console.log('tool')")
    discovery = discover(tmp_path)
    commands = [claim.object["command"] for claim in discovery.claims if claim.predicate == "provides_cli"]
    assert commands == (["tool"] if directory == "packages/test-runner" else [])
    assert any(item.kind == "javascript.bin" for item in discovery.evidence)


@pytest.mark.parametrize("directory", ["internal/pipe/testdata/fake", "tests/source/Go", "packages/test-runner", "tools/cmd/helper", "scripts/helper"])
def test_nested_go_module_keeps_repository_role(tmp_path: Path, directory: str) -> None:
    (tmp_path / "go.mod").write_text("module example.org/root\n")
    workspace = tmp_path / directory
    workspace.mkdir(parents=True)
    (workspace / "go.mod").write_text("module example.org/tool\n")
    (workspace / "main.go").write_text("package main\nfunc main() {}\n")
    discovery = discover(tmp_path)
    commands = [claim.object["command"] for claim in discovery.claims if claim.predicate == "provides_cli"]
    assert commands == (["tool"] if directory == "packages/test-runner" else [])
    assert any(item.kind == "go.main" for item in discovery.evidence)
