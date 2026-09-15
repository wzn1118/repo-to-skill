from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CORPUS = ROOT / "benchmark" / "corpus.yaml"
DEFAULT_METADATA = ROOT / "benchmark" / "repository-metadata.json"

try:
    from datetime import UTC
except ImportError:
    UTC = timezone.utc  # noqa: UP017


def _scalar(value: str) -> Any:
    value = value.split(" #", 1)[0].strip()
    if value.startswith(("'", '"')) and value.endswith(value[0]):
        return value[1:-1]
    if value in {"true", "false"}:
        return value == "true"
    try:
        return int(value)
    except ValueError:
        return value


def load_corpus(path: Path = DEFAULT_CORPUS) -> dict[str, Any]:
    """Read the deliberately small benchmark YAML without adding a runtime dependency."""
    result: dict[str, Any] = {"repositories": [], "star_policy": {}}
    current: dict[str, Any] | None = None
    section = ""
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not line.startswith(" ") and stripped.endswith(":"):
            section = stripped[:-1]
            continue
        if stripped.startswith("- "):
            current = {}
            result["repositories"].append(current)
            key, value = stripped[2:].split(":", 1)
            current[key.strip()] = _scalar(value)
            continue
        if ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        target: dict[str, Any]
        if current is not None and section == "repositories":
            target = current
        elif section == "star_policy":
            target = result["star_policy"]
        else:
            target = result
        target[key.strip()] = _scalar(value)
    return result


def _github_token() -> str | None:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        return token
    try:
        completed = subprocess.run(
            ["gh", "auth", "status", "--show-token"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    for line in (completed.stdout + completed.stderr).splitlines():
        if "Token:" in line:
            return line.split("Token:", 1)[1].strip()
    return None


def github_json(path: str, token: str | None) -> dict[str, Any]:
    request = Request(
        f"https://api.github.com{path}",
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "repo-to-skill-benchmark/1.0",
            **({"Authorization": f"Bearer {token}"} if token else {}),
        },
    )
    with urlopen(request, timeout=30) as response:
        value = json.load(response)
    if not isinstance(value, dict):
        raise TypeError("GitHub API response was not an object")
    return value


def fetch_metadata(entry: dict[str, Any], token: str | None, date: str) -> dict[str, Any]:
    repository = str(entry["repository"])
    try:
        repo = github_json(f"/repos/{repository}", token)
        default_branch = str(repo.get("default_branch") or "")
        commit = github_json(
            f"/repos/{repository}/commits/{quote(default_branch, safe='')}",
            token,
        )
        license_value = repo.get("license")
        record = {
            "repository": repository,
            "id": entry["id"],
            "tier": entry["tier"],
            "set": entry["set"],
            "benchmark_area": entry["benchmark_area"],
            "ground_truth": bool(entry.get("ground_truth", False)),
            "stars_at_benchmark": int(repo["stargazers_count"]),
            "forks_at_benchmark": int(repo["forks_count"]),
            "benchmark_date": date,
            "commit_sha": str(commit["sha"]),
            "default_branch": default_branch,
            "archived": bool(repo.get("archived", False)),
            "language": repo.get("language"),
            "license": license_value.get("spdx_id") if isinstance(license_value, dict) else None,
            "metadata_status": "OK",
        }
    except (HTTPError, URLError, KeyError, ValueError, TimeoutError) as error:
        record = {
            "repository": repository,
            "id": entry["id"],
            "tier": entry["tier"],
            "set": entry["set"],
            "benchmark_area": entry["benchmark_area"],
            "ground_truth": bool(entry.get("ground_truth", False)),
            "benchmark_date": date,
            "metadata_status": "ERROR",
            "error": str(error),
        }
    return record


def validate_snapshot(snapshot: dict[str, Any]) -> list[str]:
    records = [
        record
        for record in snapshot.get("repositories", [])
        if record.get("metadata_status") == "OK"
    ]
    errors: list[str] = []
    core = [record for record in records if record.get("set") == "core"]
    tier_a = [record for record in core if record.get("tier") == "A"]
    tier_b = [record for record in core if record.get("tier") == "B"]
    policy = snapshot.get("star_policy", {})
    if len(core) < int(policy.get("core_minimum", 30)):
        errors.append(f"CORE_COUNT: {len(core)} < {policy.get('core_minimum', 30)}")
    if len(tier_a) < int(policy.get("tier_a_minimum", 10)):
        errors.append(f"TIER_A_COUNT: {len(tier_a)} < {policy.get('tier_a_minimum', 10)}")
    if len(tier_b) < int(policy.get("tier_b_minimum", 20)):
        errors.append(f"TIER_B_COUNT: {len(tier_b)} < {policy.get('tier_b_minimum', 20)}")
    for record in records:
        stars = int(record.get("stars_at_benchmark", 0))
        tier = record.get("tier")
        if tier == "A" and stars < int(policy.get("tier_a_min", 30000)):
            errors.append(f"TIER_POLICY_MISMATCH: {record['repository']} is below Tier A")
        elif tier == "B" and stars < int(policy.get("tier_b_min", 10000)):
            errors.append(f"TIER_POLICY_MISMATCH: {record['repository']} is below Tier B")
        elif tier == "C" and stars > int(policy.get("tier_c_max", 9999)):
            errors.append(f"TIER_POLICY_MISMATCH: {record['repository']} is above Tier C")
    return errors


def write_metadata(corpus_path: Path, output_path: Path) -> dict[str, Any]:
    if output_path.exists():
        raise FileExistsError("Metadata is immutable; choose a new output path")
    corpus = load_corpus(corpus_path)
    date = datetime.now(UTC).date().isoformat()
    token = _github_token()
    records = [fetch_metadata(entry, token, date) for entry in corpus["repositories"]]
    snapshot = {
        "schema_version": 1,
        "benchmark": corpus["name"],
        "snapshot_type": "github-metadata",
        "benchmark_date": date,
        "fetched_at": datetime.now(UTC).isoformat(),
        "source": "https://api.github.com",
        "star_policy": corpus["star_policy"],
        "repositories": records,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(snapshot, indent=2, sort_keys=True) + "\n")
    return snapshot


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Collect immutable GitHub metadata; measure with public_measure.py and render with public_report.py"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    metadata = subparsers.add_parser("metadata")
    metadata.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    metadata.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    snapshot = write_metadata(args.corpus, args.output)
    errors = validate_snapshot(snapshot)
    print(f"wrote {args.output} ({len(snapshot['repositories'])} repositories)")
    for error in errors:
        print(error, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
