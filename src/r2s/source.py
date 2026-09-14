from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from r2s.domain import RepositorySnapshot

GITHUB_URL_RE = re.compile(
    r"^https://github\.com/(?P<owner>[A-Za-z0-9_.-]+)/"
    r"(?P<repo>[A-Za-z0-9_.-]+?)(?:\.git)?/?$"
)
GITHUB_LOCATOR_RE = re.compile(
    r"^github://(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+)$"
)
REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,199}$")
FULL_SHA_RE = re.compile(r"^[a-fA-F0-9]{40}$")


@dataclass(frozen=True)
class ResolvedSource:
    root: Path
    snapshot: RepositorySnapshot


def _git_environment(home: Path) -> dict[str, str]:
    environment = {
        "HOME": str(home),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_LFS_SKIP_SMUDGE": "1",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
    }
    for key in ("PATH", "SYSTEMROOT", "TMPDIR", "TMP", "TEMP"):
        if key in os.environ:
            environment[key] = os.environ[key]
    return environment


def _git(
    arguments: list[str],
    cwd: Path,
    home: Path,
    timeout: int = 120,
) -> str:
    command = [
        "git",
        "-c",
        "core.hooksPath=/dev/null",
        "-c",
        "core.autocrlf=false",
        "-c",
        "submodule.recurse=false",
        "-c",
        "protocol.file.allow=never",
        "-c",
        "filter.lfs.smudge=",
        "-c",
        "filter.lfs.required=false",
        *arguments,
    ]
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            env=_git_environment(home),
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise ValueError("GIT_UNAVAILABLE") from exc
    except subprocess.TimeoutExpired as exc:
        raise ValueError("GIT_COMMAND_TIMEOUT") from exc
    if result.returncode != 0:
        message = result.stderr.strip().splitlines()[-1:] or ["unknown git error"]
        raise ValueError(f"GIT_COMMAND_FAILED: {message[0][:300]}")
    return result.stdout.strip()


def _optional_git(arguments: list[str], cwd: Path, home: Path) -> str | None:
    try:
        return _git(arguments, cwd, home)
    except ValueError:
        return None


def _verify_checkout(root: Path, commit: str, home: Path) -> None:
    head = _git(["rev-parse", "HEAD^{commit}"], root, home)
    status = _git(
        ["status", "--porcelain=v1", "--untracked-files=normal"],
        root,
        home,
    )
    if head != commit or status:
        raise ValueError("SNAPSHOT_CACHE_INVALID")


def validate_ref(ref: str | None) -> str | None:
    if ref is None:
        return None
    if not REF_RE.fullmatch(ref) or ".." in ref or "//" in ref or "@{" in ref:
        raise ValueError("INVALID_GIT_REF")
    return ref


def resolve_local(source: str | Path, ref: str | None = None) -> ResolvedSource:
    requested_ref = validate_ref(ref)
    root = Path(source).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("SOURCE_NOT_DIRECTORY")
    with tempfile.TemporaryDirectory(prefix="r2s-git-home-") as home_value:
        home = Path(home_value)
        inside_worktree = _optional_git(
            ["rev-parse", "--is-inside-work-tree"],
            root,
            home,
        )
        is_git = inside_worktree == "true"
        if not is_git and (root / ".git").exists():
            raise ValueError("GIT_REPOSITORY_INVALID")
        commit = _optional_git(["rev-parse", "HEAD"], root, home) if is_git else None
        object_format = (
            _optional_git(["rev-parse", "--show-object-format"], root, home)
            if is_git
            else None
        )
        if is_git and object_format is None:
            object_format = "sha1"
        dirty_output = (
            _git(
                ["status", "--porcelain=v1", "--untracked-files=normal", "--", "."],
                root,
                home,
            )
            if is_git
            else None
        )
        dirty = bool(dirty_output) if is_git else None
        if requested_ref is not None:
            if not is_git:
                raise ValueError("LOCAL_REF_REQUIRES_GIT")
            resolved_ref = _git(
                ["rev-parse", "--verify", f"{requested_ref}^{{commit}}"],
                root,
                home,
            )
            if commit != resolved_ref:
                raise ValueError("LOCAL_REF_NOT_CHECKED_OUT")
            if dirty:
                raise ValueError("LOCAL_REF_DIRTY")
    snapshot = RepositorySnapshot(
        kind="local-git" if is_git else "local-directory",
        source_name=root.name,
        locator=f"local://{root.name}",
        requested_ref=requested_ref,
        resolved_commit_sha=commit,
        tree_sha256="",
        git_dirty=dirty,
        git_object_format=object_format,
    )
    return ResolvedSource(root, snapshot)


def resolve_github(
    url: str,
    output_root: Path,
    ref: str | None = None,
) -> ResolvedSource:
    match = GITHUB_URL_RE.fullmatch(url)
    if match is None:
        raise ValueError("INVALID_GITHUB_URL")
    requested_ref = validate_ref(ref)
    owner = match.group("owner")
    repo = match.group("repo")
    if owner in {".", ".."} or repo in {".", ".."}:
        raise ValueError("INVALID_GITHUB_URL")
    snapshot_base = (output_root / ".snapshots").resolve()
    snapshot_base.mkdir(parents=True, exist_ok=True)
    snapshots_root = snapshot_base / f"{owner}-{repo}"
    if snapshots_root.is_symlink():
        raise ValueError("SNAPSHOT_PATH_SYMLINK_REJECTED")
    snapshots_root.mkdir(parents=True, exist_ok=True)
    if requested_ref is not None and FULL_SHA_RE.fullmatch(requested_ref):
        cached_root = snapshots_root / requested_ref.lower()
        if cached_root.is_symlink():
            raise ValueError("SNAPSHOT_PATH_SYMLINK_REJECTED")
        if cached_root.exists():
            with tempfile.TemporaryDirectory(prefix="r2s-git-home-") as cache_home:
                _verify_checkout(cached_root, requested_ref.lower(), Path(cache_home))
            return ResolvedSource(
                cached_root,
                RepositorySnapshot(
                    "github",
                    repo,
                    f"github://{owner}/{repo}",
                    requested_ref,
                    requested_ref.lower(),
                    "",
                    False,
                    git_object_format=_git(
                        ["rev-parse", "--show-object-format"],
                        cached_root,
                        Path(cache_home),
                    ),
                ),
            )
    staging = Path(tempfile.mkdtemp(prefix="fetch-", dir=snapshots_root))
    home = staging / ".git-home"
    home.mkdir()
    try:
        _git(["init", "--quiet"], staging, home)
        _git(["remote", "add", "origin", url], staging, home)
        fetch_ref = requested_ref or "HEAD"
        _git(
            [
                "fetch",
                "--depth=1",
                "--filter=blob:none",
                "--no-tags",
                "origin",
                fetch_ref,
            ],
            staging,
            home,
        )
        commit = _git(["rev-parse", "FETCH_HEAD^{commit}"], staging, home)
        object_format = _git(["rev-parse", "--show-object-format"], staging, home)
        final_root = snapshots_root / commit
        if final_root.is_symlink():
            raise ValueError("SNAPSHOT_PATH_SYMLINK_REJECTED")
        if final_root.exists():
            if not (final_root / ".git").is_dir():
                raise ValueError("SNAPSHOT_CACHE_INVALID")
            _verify_checkout(final_root, commit, home)
            shutil.rmtree(staging)
            snapshot = RepositorySnapshot(
                "github",
                repo,
                f"github://{owner}/{repo}",
                requested_ref,
                commit,
                "",
                False,
                git_object_format=object_format,
            )
            return ResolvedSource(final_root, snapshot)
        _git(["checkout", "--quiet", "--detach", "FETCH_HEAD"], staging, home)
        shutil.rmtree(home)
        with tempfile.TemporaryDirectory(prefix="r2s-git-home-") as verify_home:
            _verify_checkout(staging, commit, Path(verify_home))
        staging.rename(final_root)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise
    snapshot = RepositorySnapshot(
        "github",
        repo,
        f"github://{owner}/{repo}",
        requested_ref,
        commit,
        "",
        False,
        git_object_format=object_format,
    )
    return ResolvedSource(final_root, snapshot)


def resolve_source(
    source: str,
    output_root: Path,
    ref: str | None = None,
) -> ResolvedSource:
    if Path(source).exists():
        return resolve_local(source, ref)
    if source.startswith(("http://", "https://", "git@", "ssh://", "file://")):
        return resolve_github(source, output_root, ref)
    raise ValueError("SOURCE_NOT_FOUND")


def update_source(snapshot: RepositorySnapshot, override: str | None = None) -> str:
    if override is not None:
        return override
    if snapshot.kind == "github":
        match = GITHUB_LOCATOR_RE.fullmatch(snapshot.locator)
        if match is None:
            raise ValueError("UPDATE_GITHUB_LOCATOR_INVALID")
        return f"https://github.com/{match.group('owner')}/{match.group('repo')}"
    raise ValueError("UPDATE_SOURCE_REQUIRED_FOR_LOCAL")
