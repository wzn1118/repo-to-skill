from __future__ import annotations

import argparse
import json
from pathlib import Path

from measurement_identity import write_new
from public_sources import digest

ROOT = Path(__file__).resolve().parents[1]
TASK_REQUIREMENTS = {
    "prettier": [["prettier", "--parser"], ["prettier", "--check", "--config"], ["prettier", "--ignore-path"]],
    "github-cli": [["gh", "status"], ["gh", "issue create"], ["gh", "pr list", "--json"]],
    "yt-dlp": [["yt-dlp", "--dump-json"], ["yt-dlp", "--format"], ["yt-dlp", "--output"]],
    "eslint": [["eslint", "--config"], ["eslint", "--fix"], ["eslint", "--ignore-pattern"]],
    "hugo": [["hugo", "server"], ["hugo", "--destination"], ["hugo", "--buildDrafts"]],
    "fzf": [["fzf", "--filter"], ["fzf", "--preview"], ["fzf", "--bind"]],
    "black": [["black"], ["black", "--check"], ["black", "--exclude"]],
    "pre-commit": [["pre-commit", "run", "--all-files"], ["pre-commit", "run"], ["pre-commit", "install"]],
    "webpack": [["webpack", "webpack-cli"]] * 3,
    "poetry": [["poetry", "install"], ["poetry", "add"], ["poetry", "env info"]],
}


def path_parts(value: object) -> tuple[str, ...] | None:
    if isinstance(value, str):
        return tuple(value.split())
    if isinstance(value, (list, tuple)) and all(isinstance(part, str) and part and not any(character.isspace() for character in part) for part in value):
        return tuple(value)
    return None


def covered(fact: dict, generated: list[dict], command: str) -> bool:
    for candidate in generated:
        if not candidate["emitted"]:
            continue
        candidate_value = candidate["value"]
        candidate_command = candidate_value.get("command")
        candidate_path = candidate_value.get("command_path")
        expected_path = path_parts(fact.get("command_path", []))
        candidate_owner = candidate_command or candidate.get("subject")
        if fact["kind"] != "command" and candidate_owner != command:
            continue
        if (fact["kind"] == "command" and candidate["predicate"] == "provides_cli"
                and candidate_command == fact["value"]):
            return True
        if (fact["kind"] == "option" and candidate["predicate"] == "supports_option"
                and candidate["value"].get("option") == fact["value"]
                and expected_path is not None
                and path_parts(candidate_value.get("command_path", [])) == expected_path):
            return True
        if fact["kind"] == "subcommand" and candidate["predicate"] in {
            "provides_subcommand", "supports_subcommand",
        }:
            if candidate_path is None:
                candidate_path = candidate_value.get("subcommand")
            if candidate_path is not None and path_parts(candidate_path) == path_parts(fact["value"]):
                return True
    return False


def evaluate(results: dict, work: Path, truth_path: Path = ROOT / "benchmark/ground-truth-facts-v2.json") -> dict:
    truth = json.loads(truth_path.read_text())
    records = {item["id"]: item for item in results["repositories"]}
    evaluated = []
    for expected in truth["repositories"]:
        record = records[expected["id"]]
        source = work / "snapshots" / f"{record['id']}-{record['commit_sha']}" / "source"
        facts = []
        for fact in expected["facts"]:
            path = source / fact["path"]
            lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
            matches = [index for index, line in enumerate(lines, 1) if fact["anchor"] in line]
            item = dict(fact, source_verified=bool(matches), line=matches[0] if matches else None,
                        commit_sha=record["commit_sha"], sha256=digest(path) if path.is_file() else None,
                        generated_coverage=covered(fact, record.get("facts", []), expected["command"]))
            item["url"] = f"https://github.com/{record['repository']}/blob/{record['commit_sha']}/{fact['path']}#L{item['line'] or 1}"
            facts.append(item)
        lookup = {item["value"]: item for item in facts}
        tasks = [{"task_index": index, "required_facts": values,
                  "facts_covered": all(lookup[value]["generated_coverage"]
                                       and lookup[value]["source_verified"] for value in values),
                  "scope": "static prerequisite coverage only; not execution success"}
                 for index, values in enumerate(TASK_REQUIREMENTS[record["id"]], 1)]
        evaluated.append({"id": record["id"], "repository": record["repository"], "tasks": tasks,
                          "expected": len(facts), "verified": sum(item["source_verified"] for item in facts),
                          "covered": sum(item["generated_coverage"] and item["source_verified"] for item in facts),
                          "facts": facts})
    return {"method": truth["review_method"], "human_verified_repositories": 0,
            "ground_truth_input": {"path": truth_path.resolve().relative_to(ROOT).as_posix(), "sha256": digest(truth_path), "schema_version": truth["schema_version"]},
            "scope": "Selected source-grounded facts, not an exhaustive CLI inventory or task success metric",
            "repositories": evaluated,
            "expected_facts": sum(item["expected"] for item in evaluated),
            "source_verified_facts": sum(item["verified"] for item in evaluated),
            "generated_covered_facts": sum(item["covered"] for item in evaluated),
            "static_task_prerequisites_covered": sum(task["facts_covered"] for item in evaluated for task in item["tasks"]),
            "tasks_evaluated": sum(len(item["tasks"]) for item in evaluated),
            "hallucinated_executable_facts": None,
            "semantic_precision_status": "Full generated-fact semantic audit not completed; hash provenance is not semantic correctness"}


def compare_official(results: dict, ground_truth: dict, work: Path) -> dict:
    record = next(item for item in results["repositories"] if item["id"] == "github-cli")
    source = work / "snapshots" / f"github-cli-{record['commit_sha']}" / "source"
    official = source / "skills/gh/SKILL.md"
    official_text = official.read_text()
    generated = work / "artifacts/github-cli/portable/gh"
    selected = next(item for item in ground_truth["repositories"] if item["id"] == "github-cli")
    rows = []
    for fact in selected["facts"]:
        needle = "gh " + fact["value"] if fact["kind"] == "subcommand" else fact["value"]
        rows.append({"fact": fact["value"], "generated": fact["generated_coverage"],
                     "official_text_mentions": needle in official_text})
    return {"repository": record["repository"], "commit_sha": record["commit_sha"],
            "official_url": f"https://github.com/cli/cli/blob/{record['commit_sha']}/skills/gh/SKILL.md",
            "official_sha256": digest(official),
            "generated_bytes": sum(path.stat().st_size for path in generated.rglob("*") if path.is_file()),
            "official_bytes": official.stat().st_size,
            "generated_files": sum(path.is_file() for path in generated.rglob("*")),
            "official_files": sum(path.is_file() for path in official.parent.rglob("*")),
            "generated_explicit_source_pin": record["commit_sha"] in (generated / "PROVENANCE.json").read_text(),
            "official_explicit_source_pin_in_text": record["commit_sha"] in official_text,
            "selected_facts": rows,
            "generated_task_pass_rate": None, "official_task_pass_rate": None,
            "maintenance_experiment": "not executed across two real upstream commits",
            "interpretation": "Textual mention comparison for five preselected facts; not exhaustive command coverage or proof of superiority"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--results", type=Path, default=ROOT / "benchmark/results.json")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "benchmark")
    parser.add_argument("--ground-truth", type=Path, default=ROOT / "benchmark/ground-truth-facts-v2.json")
    args = parser.parse_args()
    if (args.output_dir / "manifest.json").exists() or any((args.output_dir / name).exists() for name in ("ground-truth-results.json", "official-comparison.json")):
        raise ValueError("EVALUATION_OUTPUT_EXISTS: use a new run directory")
    results = json.loads(args.results.read_text())
    truth = evaluate(results, args.work, args.ground_truth)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    comparison = compare_official(results, truth, args.work)
    write_new(args.output_dir / "ground-truth-results.json", truth)
    write_new(args.output_dir / "official-comparison.json", comparison)
    print({key: value for key, value in truth.items() if key != "repositories"})


if __name__ == "__main__":
    main()
