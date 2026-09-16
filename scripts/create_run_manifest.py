from __future__ import annotations

import argparse
import json
from pathlib import Path

from measurement_identity import write_new
from public_sources import digest

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    args = parser.parse_args()
    run = args.run.resolve()
    if (run / "manifest.json").exists():
        raise ValueError("RUN_FINALIZED: manifest cannot be replaced")
    results = json.loads((run / "results.json").read_text())
    truth = json.loads((run / "ground-truth-results.json").read_text())
    truth_input = truth["ground_truth_input"]
    truth_path = (ROOT / truth_input["path"]).resolve()
    if not truth_path.is_relative_to(ROOT) or digest(truth_path) != truth_input["sha256"]:
        raise ValueError("GROUND_TRUTH_INPUT_CHANGED")
    metadata_path = ROOT / "benchmark/repository-metadata.json"
    if digest(metadata_path) != results["metadata_sha256"]:
        raise ValueError("REPOSITORY_METADATA_CHANGED")
    payload = {
        "format": "r2s-benchmark-run-v2", "run_id": run.name,
        "compiler_sha256": results["compiler_sha256"],
        "metadata_sha256": results["metadata_sha256"],
        "source_artifacts": {
            path.name: digest(path) for path in sorted(run.iterdir())
            if path.is_file() and path.name != "manifest.json"
        },
        "evaluation_tools": {
            f"scripts/{name}": digest(ROOT / "scripts" / name) for name in (
                "public_evaluate.py", "public_fact_audit.py", "render_run_report.py", "create_run_manifest.py",
            )
        },
        "evaluation_inputs": {
            "benchmark/repository-metadata.json": digest(metadata_path),
            truth_input["path"]: truth_input["sha256"],
        },
        "scope": "static discovery and generation; local regression checks, if present, are separate",
        "source_authentication": "HTTPS archives addressed by pinned commit; self-consistent unsigned manifest",
        "human_verified_repositories": 0,
    }
    write_new(run / "manifest.json", payload)
    print(run / "manifest.json")


if __name__ == "__main__":
    main()
