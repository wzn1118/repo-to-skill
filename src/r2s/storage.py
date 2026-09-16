from __future__ import annotations

import json
import shutil
import sqlite3
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from r2s.compiler_identity import compilation_request, compiler_identity
from r2s.discovery_contract import (
    _parse_discovery_structure,
    parse_discovery,
    strict_json_loads,
    validate_relations,
)
from r2s.domain import DiscoveryIR, DriftReport
from r2s.scan_policy import scan_coverage
from r2s.serialization import canonical_json, canonical_sha256, file_sha256, stable_id

DB_NAME = "runs.sqlite3"
MAX_DISCOVERY_ARTIFACT_BYTES = 32 * 1024 * 1024
DISCOVERY_ARTIFACTS = (
    "inventory.json",
    "evidence.json",
    "claims.json",
    "capabilities.json",
    "discovery.json",
    "source.lock.json",
    "run.json",
)
SCAN_ARTIFACT = "scan.json"


def _connect(output_root: Path) -> sqlite3.Connection:
    output_root.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(output_root / DB_NAME)
    connection.row_factory = sqlite3.Row
    connection.executescript(
        """
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS runs (
            run_id TEXT PRIMARY KEY,
            stage TEXT NOT NULL,
            parent_run_id TEXT,
            input_digest TEXT NOT NULL,
            target TEXT,
            goal_digest TEXT,
            outcome TEXT NOT NULL,
            readiness TEXT,
            artifact_root TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS artifacts (
            run_id TEXT NOT NULL,
            name TEXT NOT NULL,
            sha256 TEXT NOT NULL,
            relative_path TEXT NOT NULL,
            PRIMARY KEY (run_id, name)
        );
        CREATE TABLE IF NOT EXISTS run_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS run_links (
            source_run_id TEXT NOT NULL,
            target_run_id TEXT NOT NULL,
            link_type TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (source_run_id, target_run_id, link_type)
        );
        """
    )
    return connection


@contextmanager
def _database(output_root: Path) -> Iterator[sqlite3.Connection]:
    connection = _connect(output_root)
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()  # noqa: UP017


def _record_artifacts(
    connection: sqlite3.Connection,
    run_id: str,
    run_root: Path,
    recursive: bool = True,
) -> None:
    connection.execute("DELETE FROM artifacts WHERE run_id = ?", (run_id,))
    paths = run_root.rglob("*") if recursive else run_root.iterdir()
    for path in sorted(paths):
        if not path.is_file():
            continue
        relative = path.relative_to(run_root).as_posix()
        connection.execute(
            "INSERT OR REPLACE INTO artifacts"
            "(run_id, name, sha256, relative_path) VALUES(?, ?, ?, ?)",
            (run_id, relative, file_sha256(path), relative),
        )


def write_discovery(discovery: DiscoveryIR, output_root: Path) -> Path:
    discovery = parse_discovery(discovery.to_dict())
    snapshot_digest = stable_id("snapshot", asdict(discovery.snapshot))
    discovery_sha256 = canonical_sha256(discovery.to_dict())
    run_id = stable_id(
        "run",
        [
            discovery.schema_version,
            snapshot_digest,
            discovery_sha256,
            "discovery-envelope-v2",
        ],
    )
    run_root = output_root / run_id
    if run_root.is_symlink():
        raise ValueError("DISCOVERY_RUN_SYMLINK")
    if run_root.exists():
        existing = load_discovery(run_root)
        _require_equal("existing discovery", existing.to_dict(), discovery.to_dict())
        return run_root
    output_root.mkdir(parents=True, exist_ok=True)
    artifacts = {
        "inventory.json": [asdict(item) for item in discovery.inventory],
        "evidence.json": [asdict(item) for item in discovery.evidence],
        "claims.json": [asdict(item) for item in discovery.claims],
        "capabilities.json": [asdict(item) for item in discovery.capabilities],
        "discovery.json": discovery.to_dict(),
        "source.lock.json": {
            "schema_version": discovery.schema_version,
            "snapshot": asdict(discovery.snapshot),
            "discovery_sha256": discovery_sha256,
        },
        "run.json": {
            "run_id": run_id,
            "stage": "discovery",
            "outcome": "COMPLETED",
            "tree_sha256": discovery.tree_sha256,
            "input_digest": snapshot_digest,
            "discovery_sha256": discovery_sha256,
        },
    }
    if discovery.snapshot.scan_policy_id.startswith("workspace-bounded-v1:"):
        artifacts["scan.json"] = scan_coverage(discovery.inventory, discovery.snapshot.scan_policy_id)
    staging = Path(tempfile.mkdtemp(prefix=".discovery-stage-", dir=output_root))
    try:
        for name, value in artifacts.items():
            (staging / name).write_text(canonical_json(value), encoding="utf-8", newline="\n")
        staging.rename(run_root)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    with _database(output_root) as connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO runs(
                run_id, stage, parent_run_id, input_digest, target, goal_digest,
                outcome, readiness, artifact_root, created_at
            ) VALUES(?, 'discovery', NULL, ?, NULL, NULL, 'COMPLETED', NULL, ?, ?)
            """,
            (run_id, snapshot_digest, run_root.name, _now()),
        )
        connection.execute(
            "INSERT INTO run_events"
            "(run_id, event_type, payload_json, created_at) VALUES(?, ?, ?, ?)",
            (
                run_id,
                "DISCOVERY_WRITTEN",
                canonical_json({"tree_sha256": discovery.tree_sha256}),
                _now(),
            ),
        )
        _record_artifacts(connection, run_id, run_root, recursive=False)
    return run_root


def _read_json(run_root: Path, name: str) -> Any:
    path = run_root / name
    if path.is_symlink():
        raise ValueError(f"DISCOVERY_ARTIFACT_SYMLINK: {name}")
    if not path.is_file():
        raise ValueError(f"DISCOVERY_ARTIFACT_MISSING: {name}")
    if path.stat().st_size > MAX_DISCOVERY_ARTIFACT_BYTES:
        raise ValueError(f"DISCOVERY_ARTIFACT_TOO_LARGE: {name}")
    try:
        return strict_json_loads(path.read_bytes())
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"DISCOVERY_ARTIFACT_INVALID: {name}: {exc}") from exc


def _require_equal(name: str, actual: Any, expected: Any) -> None:
    if canonical_json(actual) != canonical_json(expected):
        raise ValueError(f"DISCOVERY_ARTIFACT_MISMATCH: {name}")


def _verify_discovery_index(
    run_root: Path,
    run_id: str,
    snapshot_digest: str,
) -> None:
    database = run_root.parent / DB_NAME
    if not database.is_file():
        return
    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        run = connection.execute(
            """
            SELECT stage, input_digest, outcome, artifact_root
            FROM runs WHERE run_id = ?
            """,
            (run_id,),
        ).fetchone()
        if run is None:
            raise ValueError("DISCOVERY_INDEX_RUN_MISSING")
        _require_equal(
            "runs.sqlite3:runs",
            dict(run),
            {
                "stage": "discovery",
                "input_digest": snapshot_digest,
                "outcome": "COMPLETED",
                "artifact_root": run_root.name,
            },
        )
        rows = connection.execute(
            """
            SELECT name, sha256, relative_path
            FROM artifacts WHERE run_id = ?
            """,
            (run_id,),
        ).fetchall()
    except sqlite3.Error as exc:
        raise ValueError(f"DISCOVERY_INDEX_INVALID: {exc}") from exc
    finally:
        if connection is not None:
            connection.close()

    indexed = {row["name"]: row for row in rows}
    required = (*DISCOVERY_ARTIFACTS, SCAN_ARTIFACT) if (run_root / SCAN_ARTIFACT).is_file() else DISCOVERY_ARTIFACTS
    for name in required:
        row = indexed.get(name)
        if row is None:
            raise ValueError(f"DISCOVERY_INDEX_ARTIFACT_MISSING: {name}")
        if row["relative_path"] != name:
            raise ValueError(f"DISCOVERY_INDEX_PATH_MISMATCH: {name}")
        if row["sha256"] != file_sha256(run_root / name):
            raise ValueError(f"DISCOVERY_INDEX_HASH_MISMATCH: {name}")


def _load_discovery_envelope(run_root: Path, *, migration: bool = False) -> DiscoveryIR:
    run_root = run_root.resolve()
    values = {name: _read_json(run_root, name) for name in DISCOVERY_ARTIFACTS}
    try:
        if migration:
            from r2s.legacy_contracts import import_structure

            discovery = import_structure(values["discovery.json"])
        else:
            discovery = _parse_discovery_structure(values["discovery.json"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"DISCOVERY_IR_INVALID: {exc}") from exc

    discovery_value = discovery.to_dict()
    locked_schema = values["discovery.json"]["schema_version"]
    if locked_schema == "1.2.0" and migration:
        discovery_value.pop("commands")
    if locked_schema in {"1.2.0", "1.3.0"} and migration:
        discovery_value["schema_version"] = locked_schema
    discovery_sha256 = canonical_sha256(discovery_value)
    snapshot_value = asdict(discovery.snapshot)
    snapshot_digest = stable_id("snapshot", snapshot_value)
    expected_run_id = stable_id(
        "run",
        [
            locked_schema,
            snapshot_digest,
            discovery_sha256,
            "discovery-envelope-v2",
        ],
    )
    _require_equal("run directory", run_root.name, expected_run_id)
    _require_equal("inventory.json", values["inventory.json"], discovery_value["inventory"])
    _require_equal("evidence.json", values["evidence.json"], discovery_value["evidence"])
    _require_equal("claims.json", values["claims.json"], discovery_value["claims"])
    _require_equal(
        "capabilities.json",
        values["capabilities.json"],
        discovery_value["capabilities"],
    )
    _require_equal(
        "source.lock.json",
        values["source.lock.json"],
        {
            "schema_version": locked_schema,
            "snapshot": snapshot_value,
            "discovery_sha256": discovery_sha256,
        },
    )
    _require_equal(
        "run.json",
        values["run.json"],
        {
            "run_id": expected_run_id,
            "stage": "discovery",
            "outcome": "COMPLETED",
            "tree_sha256": discovery.tree_sha256,
            "input_digest": snapshot_digest,
            "discovery_sha256": discovery_sha256,
        },
    )
    if discovery.snapshot.scan_policy_id.startswith("workspace-bounded-v1:"):
        _require_equal(
            SCAN_ARTIFACT, _read_json(run_root, SCAN_ARTIFACT),
            scan_coverage(discovery.inventory, discovery.snapshot.scan_policy_id),
        )
    _verify_discovery_index(run_root, expected_run_id, snapshot_digest)
    return discovery


def load_discovery(run_root: Path) -> DiscoveryIR:
    discovery = _load_discovery_envelope(run_root)
    validate_relations(discovery)
    return discovery


def resolve_discovery(source: str, output_root: Path) -> tuple[DiscoveryIR | None, Path | None]:
    direct = Path(source)
    candidates = [direct, output_root / source]
    for candidate in candidates:
        if candidate.is_dir() and (candidate / "discovery.json").is_file():
            return load_discovery(candidate), candidate
    return None, None


def compilation_root(
    discovery_root: Path, goal: str, target: str, capability_ids: set[str] | None = None,
) -> Path:
    identity = compiler_identity(target)
    discovery = load_discovery(discovery_root)
    request = compilation_request(discovery, goal, target, capability_ids, identity, discovery_root.name)
    compilation_id = stable_id(
        "compile",
        request,
    )
    root = discovery_root / "compilations" / compilation_id
    if root.parent.is_symlink() or root.is_symlink():
        raise ValueError("COMPILATION_PATH_SYMLINK")
    root.mkdir(parents=True, exist_ok=True)
    lock = root / "compiler.lock.json"
    value = {"compiler": identity, "request": request, "request_sha256": canonical_sha256(request)}
    if lock.exists():
        if lock.is_symlink():
            raise ValueError("COMPILER_LOCK_SYMLINK")
        _require_equal("compiler.lock.json", _read_json(root, lock.name), value)
    else:
        with lock.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(canonical_json(value))
    return root


def record_update(
    old_run_root: Path,
    new_run_root: Path,
    report: DriftReport,
) -> Path:
    output_root = new_run_root.parent
    update_id = stable_id("update", [old_run_root.name, new_run_root.name])
    relative = f"updates/{update_id}.json"
    path = new_run_root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(report.to_dict()), encoding="utf-8")
    with _database(output_root) as connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO run_links(
                source_run_id, target_run_id, link_type, payload_json, created_at
            ) VALUES(?, ?, 'updates_to', ?, ?)
            """,
            (
                old_run_root.name,
                new_run_root.name,
                canonical_json(
                    {
                        "artifact": relative,
                        "affected_capabilities": len(
                            report.affected_new_capability_ids
                        ),
                    }
                ),
                _now(),
            ),
        )
        connection.execute(
            "INSERT OR REPLACE INTO artifacts"
            "(run_id, name, sha256, relative_path) VALUES(?, ?, ?, ?)",
            (new_run_root.name, relative, file_sha256(path), relative),
        )
        connection.execute(
            "INSERT INTO run_events"
            "(run_id, event_type, payload_json, created_at) VALUES(?, ?, ?, ?)",
            (
                new_run_root.name,
                "DISCOVERY_UPDATED",
                canonical_json(
                    {
                        "source_run_id": old_run_root.name,
                        "update_id": update_id,
                    }
                ),
                _now(),
            ),
        )
    return path


def record_compilation(
    discovery_root: Path,
    compile_root: Path,
    goal: str,
    target: str,
    readiness: str,
) -> None:
    output_root = discovery_root.parent
    parent_run_id = discovery_root.name
    run_id = compile_root.name
    goal_digest = stable_id("goal", " ".join(goal.split()))
    with _database(output_root) as connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO runs(
                run_id, stage, parent_run_id, input_digest, target, goal_digest,
                outcome, readiness, artifact_root, created_at
            ) VALUES(?, 'compilation', ?, ?, ?, ?, 'COMPLETED', ?, ?, ?)
            """,
            (
                run_id,
                parent_run_id,
                parent_run_id,
                target,
                goal_digest,
                readiness,
                compile_root.relative_to(output_root).as_posix(),
                _now(),
            ),
        )
        connection.execute(
            "INSERT INTO run_events"
            "(run_id, event_type, payload_json, created_at) VALUES(?, ?, ?, ?)",
            (
                run_id,
                "COMPILATION_WRITTEN",
                canonical_json(
                    {
                        "parent_run_id": parent_run_id,
                        "target": target,
                        "readiness": readiness,
                    }
                ),
                _now(),
            ),
        )
        _record_artifacts(connection, run_id, compile_root)


def list_runs(output_root: Path) -> list[dict[str, Any]]:
    if not (output_root / DB_NAME).is_file():
        return []
    with _database(output_root) as connection:
        rows = connection.execute(
            """
            SELECT run_id, stage, parent_run_id, target, outcome, readiness,
                   artifact_root, created_at
            FROM runs ORDER BY created_at, run_id
            """
        ).fetchall()
    return [dict(row) for row in rows]
