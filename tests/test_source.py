import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from r2s.analyzers import discover
from r2s.generator import generate, validate_path
from r2s.source import (
    _git_environment,
    resolve_github,
    resolve_local,
    resolve_source,
    validate_ref,
)
from r2s.storage import load_discovery, write_discovery


def _git(root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-c", "user.name=R2S Test", "-c", "user.email=r2s@example.invalid", *arguments],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _committed_cli(root: Path) -> str:
    (root / "LICENSE").write_text("MIT License\n")
    (root / "pyproject.toml").write_text(
        '[project]\nname = "git-cli"\nversion = "1"\n'
        '[project.scripts]\ngit-tool = "tool:main"\n'
    )
    (root / "tool.py").write_text(
        "import argparse\n\n"
        "def main():\n"
        "    parser = argparse.ArgumentParser()\n"
        "    parser.add_argument('--safe')\n"
    )
    _git(root, "init", "--quiet")
    _git(root, "config", "core.autocrlf", "false")
    _git(root, "add", "LICENSE", "pyproject.toml", "tool.py")
    _git(root, "commit", "--quiet", "-m", "fixture")
    return _git(root, "rev-parse", "HEAD")


class SourceResolverTests(unittest.TestCase):
    def test_fifo_is_rejected_without_reading(self) -> None:
        if not hasattr(os, "mkfifo"):
            self.skipTest("FIFOs unavailable")
        with tempfile.TemporaryDirectory() as source:
            root = Path(source)
            os.mkfifo(root / "hostile.py")
            with self.assertRaisesRegex(ValueError, "UNTRUSTED_SPECIAL_FILE"):
                discover(root)

    def test_clean_git_snapshot_pins_commit_and_blob(self) -> None:
        with tempfile.TemporaryDirectory() as source:
            root = Path(source)
            commit = _committed_cli(root)
            resolved = resolve_local(root, "HEAD")
            self.assertEqual(resolved.snapshot.resolved_commit_sha, commit)
            self.assertFalse(resolved.snapshot.git_dirty)
            self.assertEqual(resolved.snapshot.git_object_format, "sha1")
            discovery = discover(resolved.root, resolved.snapshot, resolved.committed_blob_oids)
            source_locations = [item.source for item in discovery.evidence]
            self.assertTrue(source_locations)
            self.assertTrue(all(item.commit_sha == commit for item in source_locations))
            tool_evidence = next(
                item
                for item in discovery.evidence
                if item.source.path == "tool.py"
            )
            expected_blob = _git(root, "hash-object", "tool.py")
            self.assertEqual(tool_evidence.source.blob_sha, expected_blob)

    def test_crlf_worktree_keeps_raw_hash_and_reads_committed_blob_oid(self) -> None:
        with tempfile.TemporaryDirectory() as source:
            root = Path(source)
            (root / "LICENSE").write_bytes(b"MIT License\r\n")
            (root / "pyproject.toml").write_bytes(
                b"[project]\r\nname = 'git-cli'\r\nversion = '1'\r\n"
                b"[project.scripts]\r\ngit-tool = 'tool:main'\r\n"
            )
            (root / "tool.py").write_bytes(
                b"import argparse\r\n\r\ndef main():\r\n"
                b"    parser = argparse.ArgumentParser()\r\n"
                b"    parser.add_argument('--safe')\r\n"
            )
            commit = _git(root, "init", "--quiet")
            _git(root, "config", "core.autocrlf", "false")
            _git(root, "add", "LICENSE", "pyproject.toml", "tool.py")
            _git(root, "commit", "--quiet", "-m", "crlf")
            commit = _git(root, "rev-parse", "HEAD")
            resolved = resolve_local(root, "HEAD")
            discovery = discover(resolved.root, resolved.snapshot, resolved.committed_blob_oids)
            tool = next(item for item in discovery.inventory if item.path == "tool.py")
            self.assertEqual(
                tool.content_sha256,
                hashlib.sha256((root / "tool.py").read_bytes()).hexdigest(),
            )
            evidence = next(item for item in discovery.evidence if item.source.path == "tool.py")
            self.assertEqual(evidence.source.commit_sha, commit)
            self.assertEqual(evidence.source.blob_sha, _git(root, "rev-parse", "HEAD:tool.py"))

    def test_repository_git_helpers_are_disabled_during_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as source:
            root = Path(source)
            _committed_cli(root)
            _git(root, "config", "core.fsmonitor", "touch FS_MONITOR_EXECUTED")
            _git(root, "config", "filter.bad.clean", "touch CLEAN_EXECUTED")
            _git(root, "config", "filter.bad.process", "touch PROCESS_EXECUTED")
            (root / ".gitattributes").write_text("tool.py filter=bad\n")
            (root / "tool.py").write_text("def main(): pass\n")
            resolved = resolve_local(root)
            self.assertTrue(resolved.snapshot.git_dirty)
            self.assertFalse(any((root / name).exists() for name in (
                "FS_MONITOR_EXECUTED", "CLEAN_EXECUTED", "PROCESS_EXECUTED",
            )))

    def test_clean_crlf_conversion_keeps_distinct_raw_and_blob_identity(self) -> None:
        with tempfile.TemporaryDirectory() as source:
            root = Path(source)
            _committed_cli(root)
            _git(root, "config", "core.autocrlf", "true")
            raw = b"def main():\r\n    pass\r\n"
            (root / "tool.py").write_bytes(raw)
            _git(root, "add", "tool.py")
            _git(root, "commit", "--quiet", "-m", "normalize CRLF")
            resolved = resolve_local(root, "HEAD")
            self.assertFalse(resolved.snapshot.git_dirty)
            discovery = discover(root, resolved.snapshot, resolved.committed_blob_oids)
            entry = next(item for item in discovery.inventory if item.path == "tool.py")
            self.assertEqual(entry.content_sha256, hashlib.sha256(raw).hexdigest())
            self.assertEqual(entry.blob_sha, _git(root, "rev-parse", "HEAD:tool.py"))
            raw_oid = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
            self.assertNotEqual(entry.blob_sha, raw_oid)

    def test_sha256_git_identity_and_bom_raw_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as source:
            root = Path(source)
            try:
                _git(root, "init", "--quiet", "--object-format=sha256")
            except subprocess.CalledProcessError:
                self.skipTest("Git SHA-256 repositories unavailable")
            _committed_cli(root)
            (root / "data.txt").write_bytes(b"\xef\xbb\xbfraw\r\n")
            _git(root, "config", "core.autocrlf", "false")
            _git(root, "add", "data.txt")
            _git(root, "commit", "--quiet", "-m", "BOM")
            resolved = resolve_local(root, "HEAD")
            self.assertEqual(resolved.snapshot.git_object_format, "sha256")
            discovery = discover(root, resolved.snapshot, resolved.committed_blob_oids)
            item = next(entry for entry in discovery.inventory if entry.path == "data.txt")
            self.assertEqual(item.blob_sha, _git(root, "rev-parse", "HEAD:data.txt"))
            self.assertEqual(item.content_sha256, hashlib.sha256(b"\xef\xbb\xbfraw\r\n").hexdigest())

    def test_dirty_git_ref_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as source:
            root = Path(source)
            _committed_cli(root)
            (root / "tool.py").write_text("def main():\n    print('dirty')\n")
            with self.assertRaisesRegex(ValueError, "LOCAL_REF_DIRTY"):
                resolve_local(root, "HEAD")

    def test_dirty_snapshot_does_not_claim_head_commit(self) -> None:
        with tempfile.TemporaryDirectory() as source:
            root = Path(source)
            commit = _committed_cli(root)
            (root / "tool.py").write_text("def main():\n    print('dirty')\n")
            resolved = resolve_local(root)
            self.assertEqual(resolved.snapshot.resolved_commit_sha, commit)
            self.assertTrue(resolved.snapshot.git_dirty)
            discovery = discover(resolved.root, resolved.snapshot)
            self.assertTrue(all(item.source.commit_sha is None for item in discovery.evidence))

    def test_bundle_validation_rejects_evidence_commit_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as output:
            root = Path(source)
            _committed_cli(root)
            resolved = resolve_local(root, "HEAD")
            discovery = discover(resolved.root, resolved.snapshot)
            result = generate(discovery, "use git-tool", Path(output), "portable")
            bundle = Path(result.bundles[0])
            provenance_path = bundle / "PROVENANCE.json"
            provenance = json.loads(provenance_path.read_text())
            provenance["evidence"][0]["source"]["commit_sha"] = "0" * 40
            provenance_path.write_text(json.dumps(provenance))
            codes = {item.code for item in validate_path(bundle)}
            self.assertIn("EVIDENCE_COMMIT_MISMATCH", codes)

    def test_sensitive_files_are_not_serialized(self) -> None:
        with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as output:
            root = Path(source)
            _committed_cli(root)
            secret = "SUPER_SECRET_VALUE"
            (root / ".env").write_text(f"TOKEN={secret}\n")
            resolved = resolve_local(root)
            discovery = discover(resolved.root, resolved.snapshot)
            entry = next(item for item in discovery.inventory if item.path == ".env")
            self.assertEqual(entry.reason, "SENSITIVE_PATH_SKIPPED")
            self.assertIsNone(entry.content_sha256)
            run_root = write_discovery(discovery, Path(output))
            serialized = (run_root / "discovery.json").read_text()
            self.assertNotIn(secret, serialized)
            self.assertEqual(load_discovery(run_root).snapshot.tree_sha256, discovery.tree_sha256)

    def test_sensitive_content_change_invalidates_analysis_tree(self) -> None:
        with tempfile.TemporaryDirectory() as source:
            root = Path(source)
            (root / ".env").write_text("TOKEN=first\n")
            first = discover(root).tree_sha256
            (root / ".env").write_text("TOKEN=other\n")
            second = discover(root).tree_sha256
            self.assertNotEqual(first, second)

    def test_sensitive_directory_is_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as source:
            root = Path(source)
            (root / ".ssh").mkdir()
            (root / ".ssh/id_rsa").write_text("private-key")
            discovery = discover(root)
            entry = next(item for item in discovery.inventory if item.path == ".ssh")
            self.assertEqual(entry.reason, "SENSITIVE_DIRECTORY_SKIPPED")
            self.assertNotIn("private-key", json.dumps(discovery.to_dict()))

    def test_directory_symlink_escape_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as outside:
            root = Path(source)
            try:
                (root / "escape-dir").symlink_to(Path(outside), target_is_directory=True)
            except OSError:
                self.skipTest("directory symlinks unavailable")
            with self.assertRaisesRegex(ValueError, "UNTRUSTED_SYMLINK_ESCAPE"):
                discover(root)

    def test_remote_source_policy_rejects_non_github_urls(self) -> None:
        with tempfile.TemporaryDirectory() as output:
            for source in (
                "http://github.com/owner/repo",
                "https://example.com/owner/repo",
                "git@github.com:owner/repo.git",
                "file:///tmp/repo",
            ):
                with self.subTest(source=source), self.assertRaisesRegex(
                    ValueError,
                    "INVALID_GITHUB_URL",
                ):
                    resolve_source(source, Path(output))

    def test_malicious_refs_are_rejected(self) -> None:
        for ref in ("-main", "main..evil", "main@{1}", "main//evil", "main evil"):
            with self.subTest(ref=ref), self.assertRaisesRegex(
                ValueError,
                "INVALID_GIT_REF",
            ):
                validate_ref(ref)

    def test_non_git_directory_rejects_ref(self) -> None:
        with tempfile.TemporaryDirectory() as source, self.assertRaisesRegex(
            ValueError,
            "LOCAL_REF_REQUIRES_GIT",
        ):
            resolve_local(source, "main")

    def test_git_environment_does_not_inherit_tokens(self) -> None:
        with patch.dict(
            "os.environ",
            {"PATH": "/usr/bin", "GITHUB_TOKEN": "secret", "AWS_SECRET_ACCESS_KEY": "secret"},
            clear=True,
        ):
            environment = _git_environment(Path("/tmp/isolated-home"))
        self.assertNotIn("GITHUB_TOKEN", environment)
        self.assertNotIn("AWS_SECRET_ACCESS_KEY", environment)

    def test_github_resolver_builds_pinned_snapshot_without_network(self) -> None:
        commit = "a" * 40

        def fake_git(arguments, cwd, home, timeout=120):
            del home, timeout
            if arguments[:2] == ["init", "--quiet"]:
                (cwd / ".git").mkdir()
            elif arguments[:2] == ["rev-parse", "FETCH_HEAD^{commit}"]:
                return commit
            elif arguments == ["rev-parse", "--show-object-format"]:
                return "sha1"
            elif arguments[:2] == ["checkout", "--quiet"]:
                (cwd / "LICENSE").write_text("MIT License\n")
                (cwd / "pyproject.toml").write_text(
                    '[project]\nname = "remote"\nversion = "1"\n'
                    '[project.scripts]\nremote = "tool:main"\n'
                )
                (cwd / "tool.py").write_text("def main():\n    pass\n")
            elif arguments == ["rev-parse", "HEAD^{commit}"]:
                return commit
            elif arguments[:2] == ["status", "--porcelain=v1"]:
                return ""
            return ""

        with tempfile.TemporaryDirectory() as output:
            with patch("r2s.source._git", side_effect=fake_git) as mocked_git:
                resolved = resolve_github(
                    "https://github.com/example/remote.git",
                    Path(output),
                    "main",
                )
            self.assertEqual(resolved.snapshot.resolved_commit_sha, commit)
            self.assertTrue((resolved.root / "pyproject.toml").is_file())
            fetch = next(
                call.args[0]
                for call in mocked_git.call_args_list
                if call.args[0] and call.args[0][0] == "fetch"
            )
            self.assertIn("--no-tags", fetch)
            self.assertIn("--filter=blob:none", fetch)


if __name__ == "__main__":
    unittest.main()
