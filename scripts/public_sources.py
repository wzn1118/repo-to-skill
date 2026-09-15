from __future__ import annotations

import base64
import hashlib
import http.client
import json
import re
import shutil
import subprocess
import tarfile
import tempfile
import time
from pathlib import Path, PurePosixPath
from urllib.request import Request, urlopen

MAX_DOWNLOAD = 256 * 1024 * 1024
MAX_EXPANDED = 1024 * 1024 * 1024
MAX_MEMBERS = 100_000


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    staging = path.with_suffix(path.suffix + ".tmp")
    staging.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    staging.replace(path)


def extract_archive(archive: Path, source: Path) -> dict:
    source.mkdir()
    files = {}
    skipped = []
    total = 0
    prefix = None
    seen = set()
    with tarfile.open(archive, "r|gz") as handle:
        for index, member in enumerate(handle, 1):
            if index > MAX_MEMBERS:
                raise ValueError("ARCHIVE_MEMBER_LIMIT_EXCEEDED")
            path = PurePosixPath(member.name)
            if path.is_absolute() or ".." in path.parts or "\\" in member.name:
                raise ValueError("ARCHIVE_PATH_TRAVERSAL")
            if not path.parts or any(":" in part for part in path.parts):
                raise ValueError("ARCHIVE_INVALID_PATH")
            if prefix is None:
                prefix = path.parts[0]
            if path.parts[0] != prefix:
                raise ValueError("ARCHIVE_MULTIPLE_ROOTS")
            if len(path.parts) == 1:
                if not member.isdir():
                    raise ValueError("ARCHIVE_INVALID_ROOT")
                continue
            relative = PurePosixPath(*path.parts[1:]).as_posix()
            if relative in seen:
                raise ValueError("ARCHIVE_DUPLICATE_PATH")
            seen.add(relative)
            target = source.joinpath(*path.parts[1:])
            if member.issym() or member.islnk():
                skipped.append({"path": relative, "kind": "link", "target": member.linkname})
                continue
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            if not member.isfile():
                raise ValueError("ARCHIVE_SPECIAL_FILE")
            total += member.size
            if total > MAX_EXPANDED:
                raise ValueError("ARCHIVE_SIZE_LIMIT_EXCEEDED")
            target.parent.mkdir(parents=True, exist_ok=True)
            stream = handle.extractfile(member)
            if stream is None:
                raise ValueError("ARCHIVE_UNREADABLE_FILE")
            with stream, target.open("xb") as output:
                shutil.copyfileobj(stream, output, 1024 * 1024)
            files[relative] = {"sha256": digest(target), "bytes": member.size}
    if not files:
        raise ValueError("ARCHIVE_EMPTY")
    return {"files": files, "skipped": skipped, "expanded_bytes": total}


def verify_cache(destination: Path, record: dict) -> dict:
    if destination.is_symlink() or (destination / "source").is_symlink():
        raise ValueError("SNAPSHOT_SYMLINK")
    lock = json.loads((destination / "source.lock.json").read_text(encoding="utf-8"))
    if lock["repository"] != record["repository"] or lock["commit_sha"] != record["commit_sha"]:
        raise ValueError("SNAPSHOT_PIN_MISMATCH")
    actual = {}
    for path in (destination / "source").rglob("*"):
        if path.is_symlink():
            raise ValueError("SNAPSHOT_SYMLINK")
        if path.is_file():
            actual[path.relative_to(destination / "source").as_posix()] = {
                "sha256": digest(path), "bytes": path.stat().st_size,
            }
    if not actual or actual != lock["files"]:
        raise ValueError("SNAPSHOT_CONTENT_MISMATCH")
    return lock


def adopt_snapshot(record: dict, existing: Path, cache: Path) -> None:
    if not existing.is_dir() or existing.is_symlink():
        raise ValueError("SNAPSHOT_MISSING")
    endpoint = f"repos/{record['repository']}/git/trees/{record['commit_sha']}?recursive=1"
    def walk_tree(sha: str, prefix: str = "") -> list[dict]:
        route = f"repos/{record['repository']}/git/trees/{sha}"
        recursive = bool(prefix)
        response = subprocess.run(["gh", "api", route + ("?recursive=1" if recursive else "")],
                                  capture_output=True, text=True, check=True, timeout=180)
        value = json.loads(response.stdout)
        if recursive and not value.get("truncated"):
            return [dict(item, path=prefix + item["path"]) for item in value["tree"]]
        if value.get("truncated"):
            value = json.loads(subprocess.check_output(["gh", "api", route], text=True, timeout=60))
        entries = []
        for item in value["tree"]:
            if item["type"] == "tree":
                entries.extend(walk_tree(item["sha"], prefix + item["path"] + "/"))
            else:
                entries.append(dict(item, path=prefix + item["path"]))
        return entries

    tree = {"tree": walk_tree(record["commit_sha"])}
    files = {}
    replacements = {}
    skipped = []
    for item in tree["tree"]:
        path = PurePosixPath(item["path"])
        if path.is_absolute() or ".." in path.parts or "\\" in item["path"]:
            raise ValueError("GIT_TREE_UNSAFE_PATH")
        if item["mode"] in {"120000", "160000"}:
            skipped.append({"path": item["path"], "kind": item["mode"], "git_sha": item["sha"]})
        elif item["type"] == "blob":
            source = existing / item["path"]
            if source.is_symlink():
                raise ValueError("GIT_FILE_SYMLINK")
            content = source.read_bytes() if source.is_file() else b""
            blob = hashlib.sha1(f"blob {len(content)}\0".encode() + content).hexdigest()
            if blob != item["sha"]:
                payload = json.loads(subprocess.check_output([
                    "gh", "api", f"repos/{record['repository']}/git/blobs/{item['sha']}"
                ], text=True))
                content = base64.b64decode(payload["content"])
                if hashlib.sha1(f"blob {len(content)}\0".encode() + content).hexdigest() != item["sha"]:
                    raise ValueError("GIT_BLOB_MISMATCH")
                replacements[item["path"]] = content
            files[item["path"]] = {"sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content)}
    if not files:
        raise ValueError("EMPTY_GIT_TREE")
    cache.mkdir(parents=True, exist_ok=True)
    destination = cache / f"{record['id']}-{record['commit_sha']}"
    with tempfile.TemporaryDirectory(prefix="adopt-", dir=cache) as directory:
        staging = Path(directory)
        for relative in files:
            target = staging / "source" / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if relative in replacements:
                target.write_bytes(replacements[relative])
            else:
                shutil.copyfile(existing / relative, target)
        write_json(staging / "source.lock.json", {
            "repository": record["repository"], "commit_sha": record["commit_sha"],
            "identity_method": "all regular files matched GitHub Git tree blob SHA-1",
            "files": files, "skipped": skipped, "archive_sha256": None,
            "expanded_bytes": sum(item["bytes"] for item in files.values()),
            "git_tree_response_sha256": hashlib.sha256(json.dumps(tree, sort_keys=True).encode()).hexdigest(),
            "restored_files": sorted(replacements),
            "download_url": f"https://api.github.com/{endpoint}",
        })
        staging.rename(destination)


def fetch(record: dict, cache: Path) -> tuple[Path, dict]:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", record["repository"]):
        raise ValueError("INVALID_REPOSITORY")
    if not re.fullmatch(r"[a-f0-9]{40}", record["commit_sha"]):
        raise ValueError("INVALID_COMMIT")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", record["id"]):
        raise ValueError("INVALID_ID")
    cache.mkdir(parents=True, exist_ok=True)
    destination = cache / f"{record['id']}-{record['commit_sha']}"
    if destination.exists() or destination.is_symlink():
        return destination / "source", verify_cache(destination, record)
    url = f"https://codeload.github.com/{record['repository']}/tar.gz/{record['commit_sha']}"
    with tempfile.TemporaryDirectory(prefix="fetch-", dir=cache) as temporary:
        staging = Path(temporary)
        archive = staging / "archive.tar.gz"
        request = Request(url, headers={"User-Agent": "repo-to-skill-benchmark/2"})
        for attempt in range(3):
            try:
                started = time.monotonic()
                with urlopen(request, timeout=30) as response, archive.open("wb") as output:
                    size = 0
                    while block := response.read(1024 * 1024):
                        size += len(block)
                        if size > MAX_DOWNLOAD:
                            raise ValueError("DOWNLOAD_SIZE_LIMIT_EXCEEDED")
                        if time.monotonic() - started > 1200:
                            raise TimeoutError("DOWNLOAD_TIME_LIMIT_EXCEEDED")
                        output.write(block)
                break
            except (OSError, http.client.HTTPException):
                if attempt == 2:
                    raise
        lock = extract_archive(archive, staging / "source")
        lock.update({"repository": record["repository"], "commit_sha": record["commit_sha"],
                     "archive_sha256": digest(archive), "download_url": url})
        archive.unlink()
        write_json(staging / "source.lock.json", lock)
        staging.rename(destination)
    return destination / "source", lock
