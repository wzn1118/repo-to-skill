import hashlib
from pathlib import Path

import pytest

from r2s.analyzers import discover
from r2s.discovery_contract import parse_discovery
from r2s.generator import generate, validate_path
from r2s.python_graph import PythonGraph
from r2s.scan_policy import ScanPolicy
from r2s.scanner import scan

CLICK_MAIN = "import click\n@click.command()\n@click.option('--check')\n@click.option('--fast/--safe')\ndef main(check, fast): pass\n"


def repository(root: Path, files: dict[str, str], target: str = "app:entry") -> Path:
    files = {"LICENSE": "MIT\n", "pyproject.toml": f'[project]\nname = "demo"\n[project.scripts]\ndemo = "{target}"\n', **files}
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return root


def flags(root: Path) -> set[str]:
    return {str(claim.object["option"]) for claim in discover(root).claims if claim.predicate == "supports_option"}


def test_wrapper_reexports_aliases_carry_complete_evidence(tmp_path: Path) -> None:
    root = repository(tmp_path / "source", {
        "src/app.py": "from package import entry as run\nalias = run\nsecond = alias\ndef entry():\n return second()\n",
        "src/package/__init__.py": "from .cli import main as entry\n",
        "src/package/cli.py": CLICK_MAIN,
    })
    discovery = parse_discovery(discover(root).to_dict())
    assert flags(root) == {"--check", "--fast", "--safe"}
    evidence = {item.id: item for item in discovery.evidence}
    for claim in discovery.claims:
        if claim.predicate != "supports_option":
            continue
        chain = [evidence[identifier] for identifier in claim.evidence_ids]
        assert {item.kind for item in chain} == {"manifest.entrypoint", "python.symbol", "python.call", "python.import", "python.symbol_alias", "cli.option"}
        assert {item.source.start_line for item in chain if item.kind == "python.symbol_alias"} == {2, 3}
        assert {item.source.path for item in chain} == {"pyproject.toml", "src/app.py", "src/package/__init__.py", "src/package/cli.py"}
        for item in chain:
            assert item.source.content_sha256 == hashlib.sha256((root / item.source.path).read_bytes()).hexdigest()
            assert item.source.start_line is not None
    result = generate(discovery, "use demo", tmp_path / "out", "portable")
    assert result.root is not None
    assert result.bundles
    for bundle in result.bundles:
        assert not any(item.severity == "error" for item in validate_path(Path(bundle)))


@pytest.mark.parametrize("import_source", [
    "import package.cli as tool\ndef entry():\n return tool.main()\n",
    "import package.cli\ndef entry():\n return package.cli.main()\n",
    "from package.cli import main as entry\n",
])
def test_static_module_import_forms(tmp_path: Path, import_source: str) -> None:
    root = repository(tmp_path, {"app.py": import_source, "package/__init__.py": "", "package/cli.py": CLICK_MAIN})
    assert flags(root) == {"--check", "--fast", "--safe"}


@pytest.mark.parametrize("body", [
    "pass", "return lambda: main()", "return (main() for item in [])",
    "return main() if condition else None", "if condition:\n  main()",
    "return None\n main()", "raise RuntimeError()\n main()",
    "main = external\n main()", "main = main\n main()",
    "def main(): pass\n main()", "return external(main())",
    "return main('--check')", "return main(**options)",
])
def test_unreachable_dynamic_or_shadowed_calls_do_not_supply_options(tmp_path: Path, body: str) -> None:
    root = repository(tmp_path, {"app.py": CLICK_MAIN + f"\ndef entry():\n {body}\n"})
    assert not flags(root)


@pytest.mark.parametrize("source", [
    CLICK_MAIN + "\ndef entry(main):\n main()\n",
    CLICK_MAIN + "\ndef main(): pass\ndef entry():\n main()\n",
    CLICK_MAIN + "\nfrom unknown import *\ndef entry():\n main()\n",
    "import click\n@click.option('--fake')\ndef entry(): pass\n",
    "import typer\ndef entry(value=typer.Option('--fake')): pass\n",
    "import click\n@external\n@click.command()\n@click.option('--fake')\ndef entry(): pass\n",
    "import click\nclick.option = external\n@click.command()\n@click.option('--fake')\ndef entry(): pass\n",
    "import argparse\ndef entry():\n parser=argparse.ArgumentParser()\n parser.add_argument('--unused')\n",
    "import argparse\ndef entry():\n parser=argparse.ArgumentParser()\n consume(lambda: parser.add_argument('--fake'))\n parser.parse_args()\n",
    "import argparse\ndef entry():\n parser=argparse.ArgumentParser(prefix_chars='+')\n parser.add_argument('--fake')\n parser.parse_args()\n",
    "import argparse\ndef entry():\n parser=argparse.ArgumentParser(**settings)\n parser.add_argument('--fake')\n parser.parse_args()\n",
])
def test_unproven_framework_or_parser_is_not_a_fact(tmp_path: Path, source: str) -> None:
    assert not flags(repository(tmp_path, {"app.py": source}))


def test_two_distinct_cli_delegates_are_ambiguous(tmp_path: Path) -> None:
    root = repository(tmp_path, {"app.py": CLICK_MAIN + "\n@click.command()\ndef other(): pass\ndef entry():\n other()\n main()\n"})
    discovery = discover(root)
    assert not flags(root)
    assert "PYTHON_CLI_DELEGATION_AMBIGUOUS" in {item.code for item in discovery.findings}


@pytest.mark.parametrize("framework", ["argparse", "click", "typer"])
def test_repository_modules_cannot_impersonate_frameworks(tmp_path: Path, framework: str) -> None:
    source = CLICK_MAIN + "\ndef entry():\n main()\n" if framework == "click" else "def entry():\n import argparse\n parser=argparse.ArgumentParser()\n parser.add_argument('--fake')\n parser.parse_args()\n"
    if framework == "typer":
        source = "import typer\ndef entry(value=typer.Option(None, '--fake')): pass\n"
    root = repository(tmp_path, {"app.py": source, f"{framework}.py": "raise RuntimeError('must not import')\n"})
    assert not flags(root)


def test_skipped_framework_module_still_blocks_trust(tmp_path: Path) -> None:
    root = repository(tmp_path, {"app.py": CLICK_MAIN + "\ndef entry():\n main()\n", "click.py": " " * 2000})
    discovery = discover(root, scan_policy=ScanPolicy(max_file_bytes=1024))
    assert not any(item.predicate == "supports_option" for item in discovery.claims)


def test_argument_groups_stay_with_parsed_root(tmp_path: Path) -> None:
    root = repository(tmp_path, {"app.py": "import argparse\ndef entry():\n parser = argparse.ArgumentParser()\n group = parser.add_argument_group('root')\n group.add_argument('--root')\n child = parser.add_subparsers().add_parser('child')\n child.add_argument('--child')\n unused = argparse.ArgumentParser()\n unused.add_argument('--unused')\n parser.parse_args()\n"})
    assert {(tuple(claim.object.get("command_path", ())), claim.object.get("option")) for claim in discover(root).claims if claim.predicate == "supports_option"} == {((), "--root"), (("child",), "--child")}


def test_parser_instances_on_same_line_keep_distinct_owners(tmp_path: Path) -> None:
    root = repository(tmp_path, {"app.py": "import argparse\ndef entry():\n parser = argparse.ArgumentParser(); unused = argparse.ArgumentParser()\n parser.add_argument('--root')\n unused.add_argument('--unused')\n parser.parse_args()\n"})
    assert flags(root) == {"--root"}


@pytest.mark.parametrize("limits", [{"max_modules": 1}, {"max_depth": 1}])
def test_import_limits_do_not_emit_partial_option_chains(tmp_path: Path, limits: dict[str, int]) -> None:
    root = repository(tmp_path, {"app.py": "from package import entry\n", "package/__init__.py": "from .cli import main as entry\n", "package/cli.py": CLICK_MAIN})
    result = PythonGraph(scan(root), **limits).analyze("app", "entry")
    assert not result.options
    assert any(code.endswith("LIMIT") for code in result.diagnostics)


def test_cycles_and_budget_exhaustion_fail_closed(tmp_path: Path) -> None:
    root = repository(tmp_path, {"app.py": "from package import entry\n", "package/__init__.py": "from app import entry\n"})
    result = PythonGraph(scan(root)).analyze("app", "entry")
    assert not result.options and "PYTHON_IMPORT_CYCLE" in result.diagnostics
    (root / "app.py").write_text(CLICK_MAIN + "\ndef entry():\n main()\n entry()\n")
    result = PythonGraph(scan(root), max_symbols=1).analyze("app", "entry")
    assert not result.options and "PYTHON_GRAPH_TRAVERSAL_LIMIT" in result.diagnostics
    result = PythonGraph(scan(root)).analyze("app", "entry")
    assert "PYTHON_CALL_CYCLE" in result.diagnostics


def test_module_ambiguity_and_import_escape_are_not_guessed(tmp_path: Path) -> None:
    root = repository(tmp_path, {"app.py": "from ..external import entry\n", "src/app.py": CLICK_MAIN.replace("main", "entry")})
    result = PythonGraph(scan(root)).analyze("app", "entry")
    assert not result.options and "PYTHON_MODULE_AMBIGUOUS" in result.diagnostics
    (root / "src/app.py").unlink()
    assert not flags(root)


@pytest.mark.parametrize("initializer", ["", "cli = unrelated\n", "from external import cli\n"])
def test_from_import_attributes_are_not_assumed_to_be_submodules(tmp_path: Path, initializer: str) -> None:
    root = repository(tmp_path, {
        "app.py": "from package import cli\ndef entry():\n cli.main()\n",
        "package/__init__.py": initializer,
        "package/cli.py": CLICK_MAIN,
    })
    assert not flags(root)
    assert "PYTHON_ATTRIBUTE_BINDING_UNRESOLVED" in {item.code for item in discover(root).findings}


def test_importing_parent_does_not_prove_child_module_loaded(tmp_path: Path) -> None:
    root = repository(tmp_path, {
        "app.py": "import package\ndef entry():\n package.cli.main()\n",
        "package/__init__.py": "",
        "package/cli.py": CLICK_MAIN,
    })
    assert not flags(root)


def test_callee_source_drift_is_detected_and_never_executed(tmp_path: Path) -> None:
    marker = tmp_path / "executed"
    root = repository(tmp_path / "source", {"app.py": f"from pathlib import Path\nPath({str(marker)!r}).touch()\n" + CLICK_MAIN + "\ndef entry():\n main()\n"})
    scanned = scan(root)
    assert PythonGraph(scanned).analyze("app", "entry").options
    assert not marker.exists()
    (root / "app.py").write_text("def entry(): pass\n")
    with pytest.raises(ValueError, match="ANALYSIS_SOURCE_CHANGED|SCAN_SOURCE_CHANGED"):
        PythonGraph(scanned).analyze("app", "entry")
