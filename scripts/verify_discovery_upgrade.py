from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from measurement_identity import fingerprint, require_identity, write_new

from r2s.discovery_contract import parse_discovery, strict_json_loads
from r2s.migration import migrate_discovery
from r2s.serialization import file_sha256
from r2s.storage import load_discovery

ROOT = Path(__file__).resolve().parents[1]


def verify(source: Path, migrations: Path, output: Path) -> dict:
    if output.exists() or migrations.exists():
        raise ValueError("UPGRADE_VERIFICATION_OUTPUT_EXISTS")
    identity = fingerprint(ROOT)
    records = []
    for path in sorted(source.glob("*/discovery.json")):
        original_hash = file_sha256(path)
        payload = strict_json_loads(path.read_bytes())
        record = {"id": path.parent.name, "source_sha256": original_hash}
        try:
            parse_discovery(payload)
            record["result"] = "STRICT_PASS"
        except ValueError as error:
            record["initial_failure"] = str(error)[:1000]
            try:
                result = migrate_discovery(path, migrations / path.parent.name)
                migrated = load_discovery(Path(result["run_root"]))
                if migrated.snapshot.resolved_commit_sha != payload["snapshot"]["resolved_commit_sha"]:
                    raise ValueError("MIGRATION_COMMIT_CHANGED")
                record["result"] = "MIGRATED_REVIEW_REQUIRED"
                record["migration"] = result["report"]
            except ValueError as migration_error:
                record["result"] = "REJECTED"
                record["migration_failure"] = str(migration_error)[:1000]
        if file_sha256(path) != original_hash:
            raise ValueError("HISTORICAL_SOURCE_CHANGED")
        records.append(record)
    if not records:
        raise ValueError("NO_DISCOVERY_ARTIFACTS")
    require_identity(ROOT, identity)
    report = {
        "format": "r2s-discovery-upgrade-verification-v1",
        "compiler_sha256": identity["compiler_sha256"],
        "verification_script_sha256": file_sha256(Path(__file__)),
        "source_run": source.parent.name,
        "source_artifacts": len(records),
        "summary": dict(Counter(item["result"] for item in records)),
        "scope": "Strict IR import and explicit migration of retained historical JSON; not semantic or runtime evaluation",
        "historical_files_unchanged": True,
        "records": records,
    }
    write_new(output, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--migrations", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = verify(args.source, args.migrations, args.output)
    print(report["summary"])
    return 1 if report["summary"].get("REJECTED", 0) else 0


if __name__ == "__main__":
    raise SystemExit(main())
