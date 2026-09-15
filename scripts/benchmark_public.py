from __future__ import annotations

import argparse
import html
import http.client
import json
import os
import subprocess
import sys
import tarfile
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CORPUS = ROOT / "benchmark" / "corpus.yaml"
DEFAULT_METADATA = ROOT / "benchmark" / "repository-metadata.json"
SUPPORTED_LANGUAGES = {"Python", "JavaScript", "TypeScript", "Go"}
MAX_ARCHIVE_MEMBERS = 100_000
MAX_ARCHIVE_BYTES = 1_000_000_000

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


def _download_archive(request: Request) -> Path:
    last_error: Exception | None = None
    for _ in range(3):
        archive_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as archive:
                archive_path = Path(archive.name)
                with urlopen(request, timeout=120) as response:
                    while chunk := response.read(1024 * 1024):
                        archive.write(chunk)
            return archive_path
        except (HTTPError, OSError, http.client.IncompleteRead) as error:
            last_error = error
            if archive_path is not None:
                archive_path.unlink(missing_ok=True)
    if last_error is None:
        raise OSError("ARCHIVE_DOWNLOAD_FAILED")
    raise last_error


def download_repository(record: dict[str, Any], output_root: Path, token: str | None) -> str:
    if record.get("metadata_status") != "OK":
        return "METADATA_ERROR"
    destination = output_root / str(record["id"])
    output_root.resolve().mkdir(parents=True, exist_ok=True)
    if destination.is_symlink():
        record["fetch_error"] = "CHECKOUT_PATH_SYMLINK_REJECTED"
        return "FETCH_ERROR"
    if destination.exists():
        return "ALREADY_PRESENT"
    destination = destination.resolve()
    destination.mkdir(parents=True)
    archive_url = f"https://api.github.com/repos/{record['repository']}/tarball/{record['commit_sha']}"
    request = Request(
        archive_url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "repo-to-skill-benchmark/1.0",
            **({"Authorization": f"Bearer {token}"} if token else {}),
        },
    )
    archive_path: Path | None = None
    try:
        archive_path = _download_archive(request)
        with tarfile.open(archive_path, mode="r:gz") as tar:
                members = tar.getmembers()
                if len(members) > MAX_ARCHIVE_MEMBERS:
                    raise ValueError("ARCHIVE_MEMBER_LIMIT_EXCEEDED")
                total_bytes = sum(member.size for member in members if member.isfile())
                if total_bytes > MAX_ARCHIVE_BYTES:
                    raise ValueError("ARCHIVE_SIZE_LIMIT_EXCEEDED")
                root_prefix = PurePosixPath(members[0].name).parts[0] if members else ""
                for member in members:
                    member_path = PurePosixPath(member.name)
                    relative_parts = member_path.parts[1:] if root_prefix in member_path.parts else member_path.parts
                    relative = PurePosixPath(*relative_parts)
                    if not relative.parts and member.isdir():
                        continue
                    if not relative.parts or relative.is_absolute() or ".." in relative.parts:
                        raise ValueError("ARCHIVE_PATH_TRAVERSAL")
                    target = (destination / Path(*relative.parts)).resolve()
                    target.relative_to(destination)
                    if member.issym() or member.islnk():
                        continue
                    if member.isdir():
                        target.mkdir(parents=True, exist_ok=True)
                    elif member.isfile():
                        target.parent.mkdir(parents=True, exist_ok=True)
                        source = tar.extractfile(member)
                        if source is None:
                            raise ValueError(f"ARCHIVE_MEMBER_UNREADABLE: {member.name}")
                        with source, target.open("wb") as handle:
                            while chunk := source.read(1024 * 1024):
                                handle.write(chunk)
    except (HTTPError, OSError, tarfile.TarError, ValueError) as error:
        for path in sorted(destination.rglob("*"), reverse=True):
            if path.is_file() or path.is_symlink():
                path.unlink()
            elif path.is_dir():
                path.rmdir()
        destination.rmdir()
        record["fetch_error"] = str(error)
        return "FETCH_ERROR"
    finally:
        if archive_path is not None:
            archive_path.unlink(missing_ok=True)
    return "FETCHED"


def fetch_snapshots(metadata_path: Path, repos_dir: Path, include_sets: set[str]) -> dict[str, Any]:
    snapshot = json.loads(metadata_path.read_text(encoding="utf-8"))
    token = _github_token()
    counts: Counter[str] = Counter()
    for record in snapshot["repositories"]:
        if record.get("set") not in include_sets:
            continue
        status = download_repository(record, repos_dir, token)
        record["snapshot_status"] = status
        counts[status] += 1
    metadata_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("snapshot status:", dict(sorted(counts.items())))
    return snapshot


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
    output_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return snapshot


def _local_status(record: dict[str, Any], repos_dir: Path) -> dict[str, Any]:
    if record.get("metadata_status") != "OK":
        return {"status": "METADATA_ERROR"}
    if record.get("snapshot_status") == "FETCH_ERROR":
        return {"status": "FETCH_ERROR", "reason": record.get("fetch_error", "unknown")}
    if record.get("set") == "unsupported-challenge":
        return {"status": "UNSUPPORTED_LANGUAGE", "reason": "challenge-set"}
    local_path = repos_dir / str(record["id"])
    if not local_path.is_dir():
        return {"status": "NOT_TESTED"}
    language = record.get("language")
    if language not in SUPPORTED_LANGUAGES:
        return {"status": "UNSUPPORTED_LANGUAGE", "reason": f"primary-language:{language}"}
    try:
        sys.path.insert(0, str(ROOT / "src"))
        from r2s.core import discover

        discovery = discover(local_path)
    except (ImportError, KeyError, OSError, TypeError, UnicodeError, ValueError) as error:
        return {"status": "REVIEW_REQUIRED", "reason": f"analyzer-error:{error.__class__.__name__}"}
    if discovery.findings:
        return {"status": "REVIEW_REQUIRED", "reason": "analyzer-findings"}
    if not discovery.capabilities:
        return {"status": "NO_ACTIONABLE_CAPABILITY"}
    return {
        "status": "STATIC_READY",
        "capabilities": len(discovery.capabilities),
        "claims": len(discovery.claims),
        "evidence": len(discovery.evidence),
    }


def analyze_local(metadata_path: Path, repos_dir: Path, output_path: Path) -> dict[str, Any]:
    snapshot = json.loads(metadata_path.read_text(encoding="utf-8"))
    for record in snapshot["repositories"]:
        record["analysis"] = _local_status(record, repos_dir)
    output_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return snapshot


def build_report(snapshot: dict[str, Any]) -> dict[str, Any]:
    records = [record for record in snapshot["repositories"] if record.get("metadata_status") == "OK"]
    core = [record for record in records if record.get("set") == "core"]
    completed_statuses = {
        "NO_ACTIONABLE_CAPABILITY",
        "REVIEW_REQUIRED",
        "STATIC_READY",
        "UNSUPPORTED_LANGUAGE",
    }
    tested = [record for record in core if record.get("analysis", {}).get("status") in completed_statuses]
    successful = [record for record in tested if record["analysis"]["status"] == "STATIC_READY"]
    denominator = sum(int(record["stars_at_benchmark"]) for record in tested)
    numerator = sum(int(record["stars_at_benchmark"]) for record in successful)
    status_counts = Counter(
        record.get("analysis", {}).get("status", "NOT_TESTED") for record in snapshot["repositories"]
    )
    ground_truth = [record for record in core if record.get("ground_truth")]
    return {
        "schema_version": 1,
        "benchmark": snapshot["benchmark"],
        "benchmark_date": snapshot["benchmark_date"],
        "headline": {
            "high_star_public_repositories_selected": len(core),
            "high_star_public_repositories_tested": len(tested),
            "high_star_core_stars": sum(int(record["stars_at_benchmark"]) for record in core),
            "ground_truth_repositories": len(ground_truth),
        },
        "metrics": {
            "star_weighted_repository_coverage": (numerator / denominator if denominator else None),
            "successful_tested_repositories": len(successful),
            "tested_repository_stars": denominator,
            "successful_repository_stars": numerator,
            "hallucinated_executable_facts": None,
        },
        "status_counts": dict(sorted(status_counts.items())),
        "validation_errors": validate_snapshot(snapshot),
        "interpretation": {
            "tested_denominator": "core repositories with a completed local analysis",
            "star_weighted_coverage": "sum(stars of STATIC_READY tested repos) / sum(stars of tested core repos)",
            "hallucination_metric": "pending ground-truth task execution; null is intentional",
        },
    }


def report_markdown(report: dict[str, Any]) -> str:
    headline = report["headline"]
    metrics = report["metrics"]
    coverage = metrics["star_weighted_repository_coverage"]
    coverage_text = "pending" if coverage is None else f"{coverage:.1%}"
    rows = "\n".join(
        f"| `{key}` | {value} |" for key, value in report["status_counts"].items()
    )
    errors = "none" if not report["validation_errors"] else ", ".join(report["validation_errors"])
    return f"""# Public Repo Benchmark 1.0

This report is generated from the pinned snapshot in `repository-metadata.json`.
GitHub stars are corpus metadata, not a proxy for unique users.

## Headline

| Metric | Value |
| --- | ---: |
| High-Star Public Repositories Selected | {headline['high_star_public_repositories_selected']} |
| High-Star Public Repositories Tested | {headline['high_star_public_repositories_tested']} |
| High-Star Core Stars | {headline['high_star_core_stars']:,} |
| Ground-truth repositories | {headline['ground_truth_repositories']} |
| Star-weighted repository coverage | {coverage_text} |
| Hallucinated executable facts | pending ground-truth execution |

## Status

| Status | Repositories |
| --- | ---: |
{rows}

Validation errors: `{errors}`.

The runner intentionally reports `NOT_TESTED` until a pinned repository checkout is supplied with
`analyze`. It never turns metadata collection into an analysis success.
"""


def report_svg(snapshot: dict[str, Any], report: dict[str, Any]) -> str:
    records = snapshot["repositories"]
    groups = {
        "High-Star Core": sum(record.get("set") == "core" for record in records),
        "Unsupported challenge": sum(
            record.get("set") == "unsupported-challenge" for record in records
        ),
        "Tier C edge": sum(record.get("set") == "edge" for record in records),
    }
    statuses = report["status_counts"]
    max_group = max(groups.values(), default=1)
    max_status = max(statuses.values(), default=1)

    def text(x: int, y: int, value: object, class_name: str = "body") -> str:
        return f'<text x="{x}" y="{y}" class="{class_name}">{html.escape(str(value))}</text>'

    def bar(x: int, y: int, label: str, value: int, maximum: int, color: str) -> str:
        width = round(410 * value / maximum) if maximum else 0
        return (
            text(x, y, label)
            + f'<rect x="{x + 170}" y="{y - 16}" width="410" height="18" rx="9" fill="#263449"/>'
            + f'<rect x="{x + 170}" y="{y - 16}" width="{width}" height="18" rx="9" fill="{color}"/>'
            + text(x + 620, y, value, "number")
        )

    group_rows = "".join(
        bar(70, 190 + index * 48, label, value, max_group, "#66b3ff")
        for index, (label, value) in enumerate(groups.items())
    )
    status_rows = "".join(
        bar(700, 190 + index * 42, label, value, max_status, "#f5b84b")
        for index, (label, value) in enumerate(sorted(statuses.items()))
    )
    core_stars = report["headline"]["high_star_core_stars"]
    tested = report["headline"]["high_star_public_repositories_tested"]
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1400 420" role="img" aria-labelledby="title description">
  <title id="title">Public Repo Benchmark 1.0 snapshot</title>
  <desc id="description">Thirty-six high-star core repositories selected, zero tested until pinned checkouts are analyzed.</desc>
  <style>
    .title {{ fill: #f8fafc; font: 700 30px system-ui, sans-serif; }}
    .subtitle {{ fill: #9fb0c6; font: 400 15px system-ui, sans-serif; }}
    .panel {{ fill: #f8fafc; font: 700 17px system-ui, sans-serif; }}
    .body {{ fill: #cbd5e1; font: 500 14px system-ui, sans-serif; }}
    .number {{ fill: #f8fafc; font: 700 15px system-ui, sans-serif; text-anchor: end; }}
    .metric {{ fill: #f8fafc; font: 700 26px system-ui, sans-serif; }}
    .label {{ fill: #9fb0c6; font: 600 12px system-ui, sans-serif; }}
  </style>
  <rect width="1400" height="420" rx="24" fill="#0f172a"/>
  {text(54, 52, "Repo-to-Skill · Public Repo Benchmark 1.0", "title")}
  {text(54, 80, "Live GitHub metadata snapshot · selection is not analysis success", "subtitle")}
  <text x="54" y="126" class="label">HIGH-STAR CORE SELECTED</text>
  <text x="54" y="157" class="metric">{report["headline"]["high_star_public_repositories_selected"]}</text>
  <text x="270" y="126" class="label">CUMULATIVE STARS</text>
  <text x="270" y="157" class="metric">{core_stars:,}</text>
  <text x="540" y="126" class="label">HIGH-STAR TESTED</text>
  <text x="540" y="157" class="metric">{tested}</text>
  <text x="810" y="126" class="label">GROUND TRUTH</text>
  <text x="810" y="157" class="metric">{report["headline"]["ground_truth_repositories"]}</text>
  <text x="70" y="174" class="panel">Corpus composition</text>
  <text x="700" y="174" class="panel">Recorded analysis status</text>
  {group_rows}
  {status_rows}
</svg>
'''


def main() -> int:
    parser = argparse.ArgumentParser(description="Reproducible high-star public repository benchmark")
    subparsers = parser.add_subparsers(dest="command", required=True)
    metadata = subparsers.add_parser("metadata")
    metadata.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    metadata.add_argument("--output", type=Path, default=DEFAULT_METADATA)
    analyze = subparsers.add_parser("analyze")
    analyze.add_argument("--metadata", type=Path, default=DEFAULT_METADATA)
    analyze.add_argument("--repos-dir", type=Path, required=True)
    analyze.add_argument("--output", type=Path, default=DEFAULT_METADATA)
    fetch = subparsers.add_parser("fetch")
    fetch.add_argument("--metadata", type=Path, default=DEFAULT_METADATA)
    fetch.add_argument("--repos-dir", type=Path, default=ROOT / "benchmark" / "checkouts")
    fetch.add_argument(
        "--set",
        dest="sets",
        action="append",
        choices=("core", "unsupported-challenge", "edge"),
        default=["core"],
    )
    report = subparsers.add_parser("report")
    report.add_argument("--metadata", type=Path, default=DEFAULT_METADATA)
    report.add_argument("--output", type=Path, default=ROOT / "benchmark" / "report.json")
    report.add_argument("--markdown", type=Path, default=ROOT / "benchmark" / "report.md")
    report.add_argument("--svg", type=Path, default=ROOT / "docs" / "assets" / "public-benchmark.svg")
    args = parser.parse_args()
    if args.command == "metadata":
        snapshot = write_metadata(args.corpus, args.output)
        errors = validate_snapshot(snapshot)
        print(f"wrote {args.output} ({len(snapshot['repositories'])} repositories)")
        for error in errors:
            print(error, file=sys.stderr)
        return 1 if errors else 0
    if args.command == "analyze":
        analyze_local(args.metadata, args.repos_dir, args.output)
        print(f"wrote {args.output}")
        return 0
    if args.command == "fetch":
        fetch_snapshots(args.metadata, args.repos_dir, set(args.sets))
        return 0
    snapshot = json.loads(args.metadata.read_text(encoding="utf-8"))
    value = build_report(snapshot)
    args.output.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.markdown.write_text(report_markdown(value), encoding="utf-8")
    args.svg.parent.mkdir(parents=True, exist_ok=True)
    args.svg.write_text(report_svg(snapshot, value), encoding="utf-8")
    print(report_markdown(value))
    return 1 if value["validation_errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
