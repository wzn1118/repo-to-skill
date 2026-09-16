from __future__ import annotations

import argparse
import json
from pathlib import Path

from measurement_identity import write_new
from public_sources import digest

ROOT = Path(__file__).resolve().parents[1]
WRONG_NAMES = {
    "goreleaser": ("goreleaser", "cmd/root.go", 'Use:   "goreleaser"'),
    "gum": ("gum", "main.go", '"gum version %s"'),
    "yq": ("yq", "cmd/root.go", 'Use:   "yq"'),
    "direnv": ("direnv", "GNUmakefile", "exe = direnv"),
}


def audit(results: dict, work: Path) -> dict:
    records = []
    regressions = []
    for repository in results["repositories"]:
        if repository["set"] != "core":
            continue
        if repository["id"] in WRONG_NAMES:
            correct, relative, anchor = WRONG_NAMES[repository["id"]]
            source = work / "snapshots" / f"{repository['id']}-{repository['commit_sha']}" / "source"
            path = source / relative
            lines = path.read_text().splitlines()
            matches = [index for index, value in enumerate(lines, 1) if anchor in value]
            commands = [fact["value"].get("command") for fact in repository.get("facts", [])
                        if fact["emitted"] and fact["predicate"] == "provides_cli"]
            regressions.append({
                "repository": repository["repository"], "expected_binary_name": correct,
                "emitted_commands": commands, "source_anchor_found": bool(matches),
                "name_regression_fixed": bool(matches) and correct in commands and not ({"v2", "v4"} & set(commands)),
                "scope": "binary name only; not complete semantic audit",
                "source": {"path": relative, "line": matches[0] if matches else None,
                           "commit_sha": repository["commit_sha"], "sha256": digest(path)},
            })
        for fact in repository.get("facts", []):
            if not fact["emitted"]:
                continue
            result = {"repository": repository["repository"], "claim_id": fact["id"],
                      "predicate": fact["predicate"], "value": fact["value"],
                      "command_path": fact["value"].get("command_path") if isinstance(fact["value"], dict) else None,
                      "verdict": "NOT_SEMANTICALLY_REVIEWED"}
            if (repository["id"] in WRONG_NAMES and fact["predicate"] == "provides_cli"
                    and fact["value"].get("command") in {"v2", "v4"}):
                correct, relative, anchor = WRONG_NAMES[repository["id"]]
                source = work / "snapshots" / f"{repository['id']}-{repository['commit_sha']}" / "source"
                path = source / relative
                lines = path.read_text().splitlines()
                line = next(index for index, value in enumerate(lines, 1) if anchor in value)
                result.update({"verdict": "CONFIRMED_WRONG_EXECUTABLE_NAME", "correct_command": correct,
                               "evidence": {"path": relative, "line": line, "sha256": digest(path),
                                            "commit_sha": repository["commit_sha"],
                                            "url": f"https://github.com/{repository['repository']}/blob/{repository['commit_sha']}/{relative}#L{line}"}})
            records.append(result)
    return {"scope": "All emitted Core facts indexed; targeted source review of Go binary-name failures",
            "indexed_executable_facts": len(records),
            "confirmed_wrong_executable_facts": sum(item["verdict"] == "CONFIRMED_WRONG_EXECUTABLE_NAME" for item in records),
            "not_semantically_reviewed": sum(item["verdict"] == "NOT_SEMANTICALLY_REVIEWED" for item in records),
            "hallucination_rate": None,
            "binary_name_regressions": regressions,
            "interpretation": "Confirmed errors are a lower bound; unreviewed is not correct. Provenance-valid facts can still be wrong.",
            "facts": records}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--results", type=Path, default=ROOT / "benchmark/results.json")
    parser.add_argument("--output", type=Path, default=ROOT / "benchmark/fact-audit.json")
    args = parser.parse_args()
    if args.output.exists() or (args.output.parent / "manifest.json").exists():
        raise ValueError("AUDIT_OUTPUT_EXISTS: use a new run directory")
    result = audit(json.loads(args.results.read_text()), args.work)
    write_new(args.output, result)
    print(result["confirmed_wrong_executable_facts"], "confirmed wrong executable names")


if __name__ == "__main__":
    main()
