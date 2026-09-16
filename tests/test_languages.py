import tempfile
import unittest
from pathlib import Path

from r2s.analyzers import discover
from r2s.domain import BundleReadiness, RunOutcome
from r2s.generator import generate

ROOT = Path(__file__).parent / "fixtures"


class LanguageAnalyzerTests(unittest.TestCase):
    def test_javascript_package_bin_generates_skill(self) -> None:
        discovery = discover(ROOT / "js_cli")
        self.assertEqual(discovery.languages, ["javascript"])
        self.assertEqual(discovery.repository_types, ["cli"])
        entrypoint = next(
            claim
            for claim in discovery.claims
            if claim.predicate == "provides_cli"
        )
        self.assertEqual(entrypoint.object["command"], "js-tool")
        self.assertEqual(entrypoint.object["target"], "bin/cli.js")
        with tempfile.TemporaryDirectory() as output:
            result = generate(discovery, "run js-tool", Path(output), "portable")
            self.assertEqual(result.readiness, BundleReadiness.STATIC_READY)
            self.assertEqual(Path(result.bundles[0]).name, "js-tool")
            bundle = Path(result.bundles[0])
            self.assertNotIn("--help", (bundle / "SKILL.md").read_text())
            self.assertNotIn("--help", (bundle / "references/cli.md").read_text())

    def test_typescript_bin_is_classified_without_executing_build(self) -> None:
        discovery = discover(ROOT / "ts_cli")
        self.assertEqual(discovery.languages, ["typescript"])
        target = next(
            evidence
            for evidence in discovery.evidence
            if evidence.kind == "javascript.bin_target"
        )
        self.assertEqual(target.normalized_value["language"], "typescript")

    def test_go_cmd_and_flag_generate_provenanced_skill(self) -> None:
        discovery = discover(ROOT / "go_cli")
        self.assertEqual(discovery.languages, ["go"])
        entrypoint = next(
            claim
            for claim in discovery.claims
            if claim.predicate == "provides_cli"
        )
        option = next(
            claim
            for claim in discovery.claims
            if claim.predicate == "supports_option"
        )
        self.assertEqual(entrypoint.object["command"], "greet")
        self.assertEqual(option.object["option"], "-name")
        with tempfile.TemporaryDirectory() as output:
            result = generate(discovery, "use greet", Path(output), "codex")
            self.assertEqual(result.readiness, BundleReadiness.STATIC_READY)
            cli_reference = Path(result.bundles[0]) / "references/cli.md"
            self.assertIn("`-name`", cli_reference.read_text())

    def test_go_raw_string_cannot_create_false_cli(self) -> None:
        discovery = discover(ROOT / "go_false_positive")
        self.assertEqual(discovery.languages, ["go"])
        self.assertEqual(discovery.repository_types, ["library"])
        self.assertFalse(discovery.capabilities)

    def test_monorepo_command_conflict_requires_review(self) -> None:
        discovery = discover(ROOT / "js_conflict")
        conflicts = {
            claim.id
            for claim in discovery.claims
            if claim.predicate == "provides_cli" and claim.status == "conflicted"
        }
        self.assertEqual(len(conflicts), 2)
        self.assertIn("COMMAND_CONFLICT", {item.code for item in discovery.findings})
        with tempfile.TemporaryDirectory() as output:
            result = generate(discovery, "use the command", Path(output), "portable")
            self.assertEqual(result.readiness, BundleReadiness.REVIEW_REQUIRED)
            self.assertFalse(result.bundles)

    def test_goal_selects_only_mentioned_command(self) -> None:
        discovery = discover(ROOT / "multi_cli")
        with tempfile.TemporaryDirectory() as output:
            result = generate(discovery, "use beta", Path(output), "portable")
            self.assertEqual(result.readiness, BundleReadiness.STATIC_READY)
            self.assertEqual([Path(item).name for item in result.bundles], ["beta"])

    def test_go_module_major_version_is_not_a_command(self) -> None:
        discovery = discover(ROOT / "go_versioned_module")
        entrypoint = next(claim for claim in discovery.claims if claim.predicate == "provides_cli")
        self.assertEqual(entrypoint.object["command"], "versioned")

    def test_goal_length_is_bounded(self) -> None:
        discovery = discover(ROOT / "python_cli")
        with self.assertRaisesRegex(ValueError, "GOAL_TOO_LONG"):
            generate(discovery, "x" * 501, Path(tempfile.mkdtemp()), "portable")

    def test_unrelated_goal_requests_input_instead_of_all_commands(self) -> None:
        discovery = discover(ROOT / "multi_cli")
        with tempfile.TemporaryDirectory() as output:
            result = generate(discovery, "deploy a Kubernetes cluster", Path(output), "portable")
            self.assertEqual(result.outcome, RunOutcome.NEEDS_INPUT)
            self.assertEqual(result.readiness, BundleReadiness.REVIEW_REQUIRED)
            self.assertFalse(result.bundles)

    def test_unsafe_python_manifest_cannot_escape_or_create_command(self) -> None:
        discovery = discover(ROOT / "python_unsafe")
        self.assertFalse(discovery.capabilities)
        self.assertIn("UNSAFE_COMMAND_NAME", {item.code for item in discovery.findings})

    def test_javascript_bin_target_cannot_escape_package(self) -> None:
        with tempfile.TemporaryDirectory() as source:
            root = Path(source)
            (root / "LICENSE").write_text("MIT License\n")
            (root / "package.json").write_text(
                '{"name":"unsafe","bin":{"unsafe":"../../outside.js"}}'
            )
            discovery = discover(root)
            self.assertFalse(discovery.capabilities)
            self.assertIn("ENTRYPOINT_PATH_UNSAFE", {item.code for item in discovery.findings})

    def test_command_conflict_is_case_insensitive(self) -> None:
        with tempfile.TemporaryDirectory() as source:
            root = Path(source)
            (root / "LICENSE").write_text("MIT License\n")
            (root / "package.json").write_text(
                '{"name":"case","bin":{"Tool":"a.js","tool":"b.js"}}'
            )
            (root / "a.js").write_text("console.log('a')\n")
            (root / "b.js").write_text("console.log('b')\n")
            discovery = discover(root)
            self.assertIn("COMMAND_CONFLICT", {item.code for item in discovery.findings})


if __name__ == "__main__":
    unittest.main()
