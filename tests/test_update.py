import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from r2s.core import compare_discoveries, discover
from r2s.domain import RepositorySnapshot
from r2s.source import update_source
from r2s.storage import DB_NAME, compilation_root, load_discovery, write_discovery


def _write_two_command_repo(root: Path) -> None:
    (root / "pyproject.toml").write_text(
        '[project]\nname = "drift-demo"\nversion = "1"\n'
        '[project.scripts]\nalpha = "alpha:main"\nbeta = "beta:main"\n'
    )
    (root / "alpha.py").write_text(
        "import argparse\n\n"
        "def main():\n"
        "    parser = argparse.ArgumentParser()\n"
        "    parser.add_argument('--alpha')\n"
        "    parser.parse_args()\n"
    )
    (root / "beta.py").write_text(
        "import argparse\n\n"
        "def main():\n"
        "    parser = argparse.ArgumentParser()\n"
        "    parser.add_argument('--beta')\n"
        "    parser.parse_args()\n"
    )
    (root / "LICENSE").write_text("MIT License\n")
    (root / "README.md").write_text("Initial documentation.\n")


def _change_alpha(root: Path) -> None:
    (root / "alpha.py").write_text(
        "import argparse\n\n"
        "def main():\n"
        "    parser = argparse.ArgumentParser()\n"
        "    parser.add_argument('--alpha')\n"
        "    parser.add_argument('--new-alpha')\n"
        "    parser.parse_args()\n"
    )


class UpdateTests(unittest.TestCase):
    def test_capability_drift_is_scoped_by_evidence_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as source:
            root = Path(source)
            _write_two_command_repo(root)
            old = discover(root)
            _change_alpha(root)
            new = discover(root)
            report = compare_discoveries(old, new, "old", "new")
            self.assertEqual(report.schema_version, "1.0.0")
            self.assertEqual(
                [item.key for item in report.changed_capabilities],
                ["cli:alpha"],
            )
            self.assertEqual(
                [item.key for item in report.unchanged_capabilities],
                ["cli:beta"],
            )
            self.assertEqual(report.changed_files, ("alpha.py",))
            self.assertEqual(len(report.affected_new_capability_ids), 1)

    def test_update_cli_builds_only_affected_capability(self) -> None:
        with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as output:
            root = Path(source)
            output_root = Path(output)
            _write_two_command_repo(root)
            old_root = write_discovery(discover(root), output_root)
            _change_alpha(root)
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "r2s",
                    "update",
                    old_root.name,
                    "--repo",
                    str(root),
                    "--goal",
                    "use repository commands",
                    "--target",
                    "portable",
                    "--output",
                    str(output_root),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertNotEqual(payload["old_run_id"], payload["new_run_id"])
            self.assertEqual(
                [item["key"] for item in payload["report"]["changed_capabilities"]],
                ["cli:alpha"],
            )
            self.assertEqual(
                [Path(item).name for item in payload["build"]["bundles"]],
                ["alpha"],
            )
            self.assertEqual(payload["build_scope"], "capability_delta")
            scope_path = Path(payload["build"]["root"]).parent / "generation-scope.json"
            self.assertEqual(json.loads(scope_path.read_text())["scope"], "capability_delta")
            self.assertTrue(Path(payload["report_path"]).is_file())
            load_discovery(Path(payload["new_run_root"]))
            with sqlite3.connect(output_root / DB_NAME) as connection:
                links = connection.execute(
                    "SELECT link_type FROM run_links WHERE source_run_id = ?",
                    (old_root.name,),
                ).fetchall()
            self.assertEqual(links, [("updates_to",)])

    def test_codex_delta_uses_non_replacement_plugin_name(self) -> None:
        with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as output:
            root = Path(source)
            output_root = Path(output)
            _write_two_command_repo(root)
            old_root = write_discovery(discover(root), output_root)
            _change_alpha(root)
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "r2s",
                    "update",
                    old_root.name,
                    "--repo",
                    str(root),
                    "--goal",
                    "use repository commands",
                    "--target",
                    "codex",
                    "--output",
                    str(output_root),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            manifest_path = Path(payload["build"]["root"]) / ".codex-plugin/plugin.json"
            manifest = json.loads(manifest_path.read_text())
            self.assertTrue(manifest["name"].endswith("-delta"))

    def test_documentation_only_drift_does_not_trigger_build(self) -> None:
        with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as output:
            root = Path(source)
            output_root = Path(output)
            _write_two_command_repo(root)
            old_root = write_discovery(discover(root), output_root)
            (root / "README.md").write_text("Changed untrusted documentation.\n")
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "r2s",
                    "update",
                    old_root.name,
                    "--repo",
                    str(root),
                    "--goal",
                    "use repository commands",
                    "--output",
                    str(output_root),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertIsNone(payload["build"])
            self.assertEqual(payload["report"]["changed_files"], ["README.md"])
            self.assertEqual(len(payload["report"]["unchanged_capabilities"]), 2)

    def test_goal_naming_unchanged_command_skips_incremental_build(self) -> None:
        with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as output:
            root = Path(source)
            output_root = Path(output)
            _write_two_command_repo(root)
            old_root = write_discovery(discover(root), output_root)
            _change_alpha(root)
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "r2s",
                    "update",
                    old_root.name,
                    "--repo",
                    str(root),
                    "--goal",
                    "use beta",
                    "--output",
                    str(output_root),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertIsNone(payload["build"])
            self.assertEqual(payload["selected_affected_capability_ids"], [])

    def test_license_policy_drift_invalidates_all_capabilities(self) -> None:
        with tempfile.TemporaryDirectory() as source:
            root = Path(source)
            _write_two_command_repo(root)
            old = discover(root)
            (root / "LICENSE").unlink()
            new = discover(root)
            report = compare_discoveries(old, new, "old", "new")
            self.assertTrue(report.policy_changed)
            self.assertEqual(
                [item.key for item in report.changed_capabilities],
                ["cli:alpha", "cli:beta"],
            )
            self.assertEqual(len(report.affected_new_capability_ids), 2)

    def test_local_update_requires_explicit_repository(self) -> None:
        with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as output:
            root = Path(source)
            output_root = Path(output)
            _write_two_command_repo(root)
            old_root = write_discovery(discover(root), output_root)
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "r2s",
                    "update",
                    old_root.name,
                    "--output",
                    str(output_root),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("UPDATE_SOURCE_REQUIRED_FOR_LOCAL", result.stderr)

    def test_compilation_ids_are_scoped_to_discovery_run(self) -> None:
        with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as output:
            root = Path(source)
            output_root = Path(output)
            _write_two_command_repo(root)
            old_root = write_discovery(discover(root), output_root)
            _change_alpha(root)
            new_root = write_discovery(discover(root), output_root)
            old_compile = compilation_root(old_root, "same goal", "portable")
            new_compile = compilation_root(new_root, "same goal", "portable")
            self.assertNotEqual(old_compile.name, new_compile.name)

    def test_public_github_locator_can_be_reused_for_update(self) -> None:
        snapshot = RepositorySnapshot(
            kind="github",
            source_name="demo",
            locator="github://example/demo",
            requested_ref="main",
            resolved_commit_sha="a" * 40,
            tree_sha256="b" * 64,
            git_dirty=False,
        )
        self.assertEqual(
            update_source(snapshot),
            "https://github.com/example/demo",
        )


if __name__ == "__main__":
    unittest.main()
