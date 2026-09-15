from __future__ import annotations

import argparse
import json
from pathlib import Path

from public_build_runtime import container
from public_sources import write_json

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not args.execute:
        print("Preview: offline formatting, linting, and filtering on synthetic inputs. Pass --execute.")
        return
    builds = json.loads((ROOT / "benchmark/build-runtime-results.json").read_text())
    cases = {
        "prettier": [
            ("explicit-parser", "node /tmp/source/bin/prettier.cjs --parser babel /tmp/tasks/sample.js", 0, "const value = 1;"),
            ("check-format", "node /tmp/source/bin/prettier.cjs --check /tmp/tasks/sample.js", 1, "Code style issues"),
            ("ignore-file", "node /tmp/source/bin/prettier.cjs --ignore-path /tmp/tasks/.ignore --check /tmp/tasks/sample.js", 0, "All matched files"),
        ],
        "eslint": [
            ("lint-with-config", "node /tmp/source/bin/eslint.js --config /tmp/tasks/eslint.config.mjs /tmp/tasks/sample.js", 1, "Missing semicolon"),
            ("apply-fix", "node /tmp/source/bin/eslint.js --config /tmp/tasks/eslint.config.mjs --fix /tmp/tasks/sample.js && cat /tmp/tasks/sample.js", 0, "const value = 1;"),
            ("ignore-path", "node /tmp/source/bin/eslint.js --config /tmp/tasks/eslint.config.mjs --ignore-pattern '**/sample.js' /tmp/tasks/sample.js", 0, "ignored"),
        ],
        "fzf": [("filter-input", "printf 'alpha\\nbeta\\n' | /deps/program --filter alpha", 0, "alpha")],
    }
    setup = (
        "cp -R /source /tmp/source && "
        "ln -s /deps/node_modules /tmp/source/node_modules && "
        "mkdir /tmp/tasks && cd /tmp/tasks && "
        "printf 'const value = 1\\n' > sample.js && "
        "printf 'sample.js\\n' > .ignore && "
        "printf 'export default [{rules: {semi: [\"error\", \"always\"]}}];\\n' > eslint.config.mjs && "
    )
    results = []
    for build in builds["repositories"]:
        if build["id"] not in cases or build["status"] != "SMOKE_PASSED":
            continue
        source = args.work / "snapshots" / f"{build['id']}-{build['commit_sha']}" / "source"
        for label, command, expected_exit, expected_text in cases[build["id"]]:
            shell = command if build["id"] == "fzf" else setup + command
            result = container(build["image_id"], source, args.work / "builds" / build["id"],
                               ["sh", "-c", shell], False)
            result.update({"id": build["id"], "case": label, "commit_sha": build["commit_sha"],
                           "expected_exit": expected_exit, "expected_text": expected_text,
                           "passed": result["exit_code"] == expected_exit
                           and expected_text in result["stdout"] + result["stderr"]})
            results.append(result)
    write_json(ROOT / "benchmark/functional-results.json", {
        "method": "Offline functional cases on pinned source; no agent, no with/without-skill comparison",
        "cases": results})
    print([(item["id"], item["case"], item["passed"]) for item in results])


if __name__ == "__main__":
    main()
