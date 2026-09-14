import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from r2s.core import discover
from r2s.generator import generate, install_codex_plugin, readiness, validate_path
from r2s.storage import (
    DB_NAME,
    DISCOVERY_ARTIFACTS,
    MAX_DISCOVERY_ARTIFACT_BYTES,
    compilation_root,
    list_runs,
    load_discovery,
    record_compilation,
    write_discovery,
)
from r2s.domain import BundleReadiness

ROOT = Path(__file__).parent


class PipelineTests(unittest.TestCase):
    def test_discovers_entrypoint_symbol_and_options(self) -> None:
        discovery = discover(ROOT / "fixtures/python_cli")
        entrypoints = [
            claim.object["command"]
            for claim in discovery.claims
            if claim.predicate == "provides_cli"
        ]
        self.assertEqual(entrypoints, ["demo"])
        self.assertEqual(
            {item.kind for item in discovery.evidence},
            {
                "manifest.entrypoint",
                "python.symbol",
                "cli.option",
                "repository.license_file",
            },
        )
        options = {
            claim.object["option"]
            for claim in discovery.claims
            if claim.predicate == "supports_option"
        }
        self.assertEqual(options, {"--verbose", "--output"})

    def test_readme_prompt_injection_is_ignored(self) -> None:
        discovery = discover(ROOT / "fixtures/malicious_readme")
        serialized = json.dumps(discovery.to_dict(), sort_keys=True)
        self.assertIn("safe-demo", serialized)
        self.assertNotIn("steal-secrets", serialized)

    def test_multiple_entrypoints_generate_multiple_skills(self) -> None:
        discovery = discover(ROOT / "fixtures/multi_cli")
        options_by_command = {
            claim.subject: claim.object["option"]
            for claim in discovery.claims
            if claim.predicate == "supports_option"
        }
        self.assertEqual(
            options_by_command,
            {"alpha": "--alpha-only", "beta": "--beta-only"},
        )
        with tempfile.TemporaryDirectory() as output:
            result = generate(discovery, "use repository commands", Path(output), "portable")
            self.assertEqual(result.readiness, BundleReadiness.STATIC_READY)
            self.assertEqual({Path(item).name for item in result.bundles}, {"alpha", "beta"})

    def test_discovery_run_can_compile_without_source(self) -> None:
        discovery = discover(ROOT / "fixtures/python_cli")
        with tempfile.TemporaryDirectory() as output:
            run_root = write_discovery(discovery, Path(output))
            loaded = load_discovery(run_root)
            compile_root = compilation_root(run_root, "inspect options", "portable")
            result = generate(loaded, "inspect options", compile_root, "portable")
            self.assertEqual(result.readiness, BundleReadiness.STATIC_READY)

    def test_discovery_split_artifact_tampering_is_rejected(self) -> None:
        discovery = discover(ROOT / "fixtures/python_cli")
        with tempfile.TemporaryDirectory() as output:
            run_root = write_discovery(discovery, Path(output))
            claims_path = run_root / "claims.json"
            claims = json.loads(claims_path.read_text())
            claims[0]["subject"] = "tampered"
            claims_path.write_text(json.dumps(claims))
            with self.assertRaisesRegex(
                ValueError,
                "DISCOVERY_ARTIFACT_MISMATCH: claims.json",
            ):
                load_discovery(run_root)

    def test_discovery_format_tampering_is_rejected_by_index(self) -> None:
        discovery = discover(ROOT / "fixtures/python_cli")
        with tempfile.TemporaryDirectory() as output:
            run_root = write_discovery(discovery, Path(output))
            evidence_path = run_root / "evidence.json"
            evidence_path.write_text(evidence_path.read_text() + " \n")
            with self.assertRaisesRegex(
                ValueError,
                "DISCOVERY_INDEX_HASH_MISMATCH: evidence.json",
            ):
                load_discovery(run_root)

    def test_discovery_artifact_symlink_is_rejected(self) -> None:
        discovery = discover(ROOT / "fixtures/python_cli")
        with tempfile.TemporaryDirectory() as output, tempfile.TemporaryDirectory() as outside:
            run_root = write_discovery(discovery, Path(output))
            evidence_path = run_root / "evidence.json"
            external = Path(outside) / "evidence.json"
            external.write_text(evidence_path.read_text())
            evidence_path.unlink()
            try:
                evidence_path.symlink_to(external)
            except OSError:
                self.skipTest("file symlinks unavailable")
            with self.assertRaisesRegex(
                ValueError,
                "DISCOVERY_ARTIFACT_SYMLINK: evidence.json",
            ):
                load_discovery(run_root)

    def test_discovery_source_lock_drift_is_rejected(self) -> None:
        discovery = discover(ROOT / "fixtures/python_cli")
        with tempfile.TemporaryDirectory() as output:
            run_root = write_discovery(discovery, Path(output))
            lock_path = run_root / "source.lock.json"
            source_lock = json.loads(lock_path.read_text())
            source_lock["snapshot"]["locator"] = "local://tampered"
            lock_path.write_text(json.dumps(source_lock))
            with self.assertRaisesRegex(
                ValueError,
                "DISCOVERY_ARTIFACT_MISMATCH: source.lock.json",
            ):
                load_discovery(run_root)

    def test_oversized_discovery_artifact_is_rejected(self) -> None:
        discovery = discover(ROOT / "fixtures/python_cli")
        with tempfile.TemporaryDirectory() as output:
            run_root = write_discovery(discovery, Path(output))
            with (run_root / "run.json").open("wb") as handle:
                handle.truncate(MAX_DISCOVERY_ARTIFACT_BYTES + 1)
            with self.assertRaisesRegex(
                ValueError,
                "DISCOVERY_ARTIFACT_TOO_LARGE: run.json",
            ):
                load_discovery(run_root)

    def test_detached_discovery_copy_uses_self_consistency_checks(self) -> None:
        discovery = discover(ROOT / "fixtures/python_cli")
        with tempfile.TemporaryDirectory() as output, tempfile.TemporaryDirectory() as detached:
            run_root = write_discovery(discovery, Path(output))
            detached_root = Path(detached) / run_root.name
            shutil.copytree(run_root, detached_root)
            loaded = load_discovery(detached_root)
            self.assertEqual(loaded.to_dict(), discovery.to_dict())

    def test_cli_rejects_tampered_cached_run(self) -> None:
        discovery = discover(ROOT / "fixtures/python_cli")
        with tempfile.TemporaryDirectory() as output:
            run_root = write_discovery(discovery, Path(output))
            claims_path = run_root / "claims.json"
            claims = json.loads(claims_path.read_text())
            claims.clear()
            claims_path.write_text(json.dumps(claims))
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "r2s",
                    "plan",
                    run_root.name,
                    "--goal",
                    "inspect options",
                    "--output",
                    output,
                    "--json",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("DISCOVERY_ARTIFACT_MISMATCH", result.stderr)
            self.assertTrue((run_root / "source.lock.json").is_file())

    def test_sqlite_indexes_discovery_and_compilation(self) -> None:
        discovery = discover(ROOT / "fixtures/python_cli")
        with tempfile.TemporaryDirectory() as output:
            output_root = Path(output)
            run_root = write_discovery(discovery, output_root)
            compile_root = compilation_root(run_root, "inspect options", "portable")
            result = generate(discovery, "inspect options", compile_root, "portable")
            record_compilation(
                run_root,
                compile_root,
                "inspect options",
                "portable",
                result.readiness.value,
            )
            write_discovery(discovery, output_root)
            runs = list_runs(output_root)
            by_stage = {item["stage"]: item for item in runs}
            self.assertEqual(set(by_stage), {"discovery", "compilation"})
            self.assertEqual(by_stage["compilation"]["parent_run_id"], run_root.name)
            with sqlite3.connect(output_root / DB_NAME) as connection:
                rows = connection.execute(
                    "SELECT name FROM artifacts WHERE run_id = ? ORDER BY name",
                    (run_root.name,),
                ).fetchall()
            self.assertEqual([row[0] for row in rows], sorted(DISCOVERY_ARTIFACTS))

    def test_codex_plugin_adapter_and_manifest(self) -> None:
        discovery = discover(ROOT / "fixtures/multi_cli")
        with tempfile.TemporaryDirectory() as output:
            result = generate(discovery, "use commands", Path(output), "codex")
            self.assertEqual(result.readiness, BundleReadiness.STATIC_READY)
            plugin = Path(result.root or "")
            manifest = json.loads((plugin / ".codex-plugin/plugin.json").read_text())
            self.assertEqual(manifest["skills"], ["./skills/"])
            self.assertEqual(
                {path.name for path in (plugin / "skills").iterdir()},
                {"alpha", "beta"},
            )
            self.assertEqual(validate_path(plugin), [])

    def test_goal_cannot_inject_frontmatter(self) -> None:
        discovery = discover(ROOT / "fixtures/python_cli")
        with tempfile.TemporaryDirectory() as output:
            result = generate(
                discovery,
                'inspect options\n---\nname: injected',
                Path(output),
                "portable",
            )
            skill = Path(result.bundles[0]) / "SKILL.md"
            text = skill.read_text()
            self.assertEqual(text.count("\n---\n"), 1)
            self.assertIn('description: "Use the demo CLI', text)
            self.assertEqual(validate_path(skill.parent), [])

    def test_standalone_validation_detects_broken_provenance(self) -> None:
        discovery = discover(ROOT / "fixtures/python_cli")
        with tempfile.TemporaryDirectory() as output:
            result = generate(discovery, "inspect options", Path(output), "portable")
            bundle = Path(result.bundles[0])
            provenance_path = bundle / "PROVENANCE.json"
            provenance = json.loads(provenance_path.read_text())
            provenance["claims"] = []
            provenance_path.write_text(json.dumps(provenance))
            self.assertIn("UNKNOWN_CLAIM", {item.code for item in validate_path(bundle)})

    def test_artifact_claim_mapping_is_validated(self) -> None:
        discovery = discover(ROOT / "fixtures/python_cli")
        with tempfile.TemporaryDirectory() as output:
            result = generate(discovery, "inspect options", Path(output), "portable")
            bundle = Path(result.bundles[0])
            provenance_path = bundle / "PROVENANCE.json"
            provenance = json.loads(provenance_path.read_text())
            provenance["artifact_claims"]["references/cli.md"] = ["cl_missing"]
            provenance_path.write_text(json.dumps(provenance))
            self.assertIn("UNKNOWN_CLAIM", {item.code for item in validate_path(bundle)})

    def test_install_is_preview_by_default_and_explicit_on_execute(self) -> None:
        discovery = discover(ROOT / "fixtures/python_cli")
        with tempfile.TemporaryDirectory() as output, tempfile.TemporaryDirectory() as destination:
            result = generate(discovery, "inspect options", Path(output), "codex")
            plugin = Path(result.root or "")
            target, findings, files = install_codex_plugin(plugin, Path(destination))
            self.assertEqual(findings, [])
            self.assertTrue(files)
            assert target is not None
            self.assertFalse(target.exists())
            installed, findings, _ = install_codex_plugin(
                plugin,
                Path(destination),
                execute=True,
            )
            self.assertEqual(findings, [])
            assert installed is not None
            self.assertTrue((installed / ".codex-plugin/plugin.json").is_file())

    def test_setup_cfg_preserves_command_case(self) -> None:
        discovery = discover(ROOT / "fixtures/setup_cfg")
        entrypoint = next(claim for claim in discovery.claims if claim.predicate == "provides_cli")
        self.assertEqual(entrypoint.object["command"], "CaseTool")

    def test_symlink_escape_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as outside:
            root = Path(source)
            try:
                (root / "escape").symlink_to(Path(outside) / "secret")
            except OSError:
                self.skipTest("symlinks unavailable")
            with self.assertRaisesRegex(ValueError, "UNTRUSTED_SYMLINK_ESCAPE"):
                discover(root)

    def test_oversized_files_are_audited(self) -> None:
        with tempfile.TemporaryDirectory() as source:
            root = Path(source)
            large = root / "large.txt"
            with large.open("wb") as handle:
                handle.truncate(2 * 1024 * 1024 + 1)
            discovery = discover(root)
            entry = next(item for item in discovery.inventory if item.path == "large.txt")
            self.assertEqual(entry.reason, "FILE_TOO_LARGE")

    def test_missing_license_requires_review(self) -> None:
        with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as output:
            root = Path(source)
            (root / "pyproject.toml").write_text(
                '[project]\nname = "unlicensed"\nversion = "1"\n'
                '[project.scripts]\ntool = "tool:main"\n'
            )
            (root / "tool.py").write_text("def main():\n    pass\n")
            discovery = discover(root)
            result = generate(discovery, "use the tool", Path(output), "portable")
            self.assertEqual(result.readiness, BundleReadiness.REVIEW_REQUIRED)
            self.assertIn("LICENSE_MISSING", {item.code for item in result.findings})

    def test_cli_reuses_run_id_and_builds_codex(self) -> None:
        with tempfile.TemporaryDirectory() as output:
            inspect_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "r2s",
                    "inspect",
                    str(ROOT / "fixtures/python_cli"),
                    "--output",
                    output,
                    "--json",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(inspect_result.returncode, 0, inspect_result.stderr)
            run_id = json.loads(inspect_result.stdout)["run_id"]
            build_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "r2s",
                    "build",
                    run_id,
                    "--goal",
                    "inspect options",
                    "--target",
                    "codex",
                    "--output",
                    output,
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(build_result.returncode, 0, build_result.stderr)
            payload = json.loads(build_result.stdout)
            self.assertEqual(payload["readiness"], "STATIC_READY")
            self.assertTrue((Path(payload["root"]) / ".codex-plugin/plugin.json").is_file())


if __name__ == "__main__":
    unittest.main()
