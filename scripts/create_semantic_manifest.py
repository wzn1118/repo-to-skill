from __future__ import annotations

import argparse
import json
from pathlib import Path

from semantic_gold import digest, strict_load, write_new


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    args = parser.parse_args()
    run = args.run.resolve()
    files = {
        name: run / name
        for name in (
            "semantic-gold.json",
            "v22-semantic-results.json",
            "semantic-evaluation-v2.json",
            "report-v2.md",
            "semantic-coverage-v2.svg",
        )
    }
    for name, path in files.items():
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"SEMANTIC_MANIFEST_INPUT_INVALID: {name}")
    evaluation = strict_load(files["semantic-evaluation-v2.json"])
    root = Path(__file__).resolve().parents[1]
    identity = {
        "scripts/semantic_gold.py": digest((root / "scripts/semantic_gold.py").read_bytes()),
        "scripts/freeze_semantic_gold.py": digest((root / "scripts/freeze_semantic_gold.py").read_bytes()),
        "scripts/render_semantic_report.py": digest((root / "scripts/render_semantic_report.py").read_bytes()),
        "scripts/create_semantic_manifest.py": digest(Path(__file__).read_bytes()),
        "benchmark/repository-metadata.json": digest((root / "benchmark/repository-metadata.json").read_bytes()),
    }
    payload = {
        "format": "r2s-semantic-gold-run-v1",
        "run_id": run.name,
        "scope": "Retrospective agent-curated selected-field agreement; no human sign-off, held-out accuracy, complete precision or Agent uplift.",
        "artifacts": {name: digest(path.read_bytes()) for name, path in files.items()},
        "evaluation_identity": identity,
        "counts": {
            "positive_subjects": evaluation["positive_subjects"],
            "negative_subjects": evaluation["negative_subjects"],
            "statuses": evaluation["counts"],
            "fields": evaluation["field_counts"],
        },
    }
    write_new(run / "semantic-manifest.json", payload)
    print(json.dumps({"manifest": str(run / "semantic-manifest.json"), "artifacts": len(files)}))


if __name__ == "__main__":
    main()
