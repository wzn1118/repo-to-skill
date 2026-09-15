from __future__ import annotations

import argparse
import json
from pathlib import Path

from public_sources import digest, write_json

ROOT = Path(__file__).resolve().parents[1]
WRONG_NAMES = {
    "goreleaser": ("goreleaser", "cmd/root.go", 'Use:   "goreleaser"'),
    "gum": ("gum", "main.go", '"gum version %s"'),
    "yq": ("yq", "cmd/root.go", 'Use:   "yq"'),
    "direnv": ("direnv", "GNUmakefile", "exe = direnv"),
}


def audit(results: dict, work: Path) -> dict:
    records = []
    for repository in results["repositories"]:
        if repository["set"] != "core":
            continue
        for fact in repository.get("facts", []):
            if not fact["emitted"]:
                continue
            result = {"repository": repository["repository"], "claim_id": fact["id"],
                      "predicate": fact["predicate"], "value": fact["value"],
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
            "interpretation": "Confirmed errors are a lower bound; unreviewed is not correct. Provenance-valid facts can still be wrong.",
            "facts": records}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work", type=Path, required=True)
    args = parser.parse_args()
    result = audit(json.loads((ROOT / "benchmark/results.json").read_text()), args.work)
    write_json(ROOT / "benchmark/fact-audit.json", result)
    print(result["confirmed_wrong_executable_facts"], "confirmed wrong executable names")


if __name__ == "__main__":
    main()
