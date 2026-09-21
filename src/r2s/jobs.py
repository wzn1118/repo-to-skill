from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from r2s.application import build_workflow
from r2s.core import discover_source, write_discovery
from r2s.serialization import canonical_json, canonical_sha256
from r2s.workflows import WorkflowRequest


class JobStore:
    def __init__(self, output: Path):
        self.output = output
        output.mkdir(parents=True, exist_ok=True)
        self.path = output / "jobs.sqlite3"
        self.slots = threading.BoundedSemaphore(2)
        if self.path.is_symlink():
            raise ValueError("JOB_DATABASE_SYMLINK")
        with self.connect() as connection:
            connection.executescript("CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, request TEXT NOT NULL, status TEXT NOT NULL, result TEXT, cancellation INTEGER NOT NULL DEFAULT 0, attempt INTEGER NOT NULL DEFAULT 0); CREATE TABLE IF NOT EXISTS events (sequence INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT NOT NULL, attempt INTEGER NOT NULL, stage TEXT NOT NULL, timestamp TEXT NOT NULL, payload TEXT NOT NULL);")
            if "lease" not in {row[1] for row in connection.execute("PRAGMA table_info(jobs)")}:
                connection.execute("ALTER TABLE jobs ADD COLUMN lease REAL NOT NULL DEFAULT 0")

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def recover_interrupted(self) -> None:
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute("SELECT id,attempt FROM jobs WHERE status='RUNNING' AND lease<?", (time.time()-30,)).fetchall()
            for row in rows:
                connection.execute("UPDATE jobs SET status='INTERRUPTED' WHERE id=?", (row["id"],))
                self.event(connection, row["id"], row["attempt"], "INTERRUPTED", {"reason": "worker lease expired"})

    def submit(self, request: dict[str, Any]) -> str:
        if request.get("action") not in {"inspect", "build"}:
            raise ValueError("JOB_ACTION_INVALID")
        identifier = "job_" + uuid.uuid4().hex[:20]
        with self.connect() as connection:
            connection.execute("INSERT INTO jobs(id,request,status) VALUES(?,?,?)", (identifier, canonical_json(request), "QUEUED"))
            self.event(connection, identifier, 0, "QUEUED", {"request_sha256": canonical_sha256(request)})
        return identifier

    def event(self, connection: sqlite3.Connection, identifier: str, attempt: int, stage: str, payload: dict[str, Any]) -> None:
        connection.execute("INSERT INTO events(job_id,attempt,stage,timestamp,payload) VALUES(?,?,?,?,?)", (identifier, attempt, stage, datetime.now(UTC).isoformat(), canonical_json(payload)))

    def get(self, identifier: str) -> dict[str, Any]:
        self.recover_interrupted()
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM jobs WHERE id=?", (identifier,)).fetchone()
            if row is None:
                raise ValueError("JOB_NOT_FOUND")
            events = connection.execute("SELECT sequence,attempt,stage,timestamp,payload FROM events WHERE job_id=? ORDER BY sequence", (identifier,)).fetchall()
        return {"id": identifier, "status": row["status"], "attempt": row["attempt"], "cancel_requested": bool(row["cancellation"]), "result": json.loads(row["result"]) if row["result"] else None, "events": [{**dict(event), "payload": json.loads(event["payload"])} for event in events]}

    def cancel(self, identifier: str) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute("SELECT status,attempt FROM jobs WHERE id=?", (identifier,)).fetchone()
            if row is None:
                raise ValueError("JOB_NOT_FOUND")
            if row["status"] in {"QUEUED", "RUNNING"}:
                status = "CANCELLED" if row["status"] == "QUEUED" else "RUNNING"
                connection.execute("UPDATE jobs SET cancellation=1,status=? WHERE id=?", (status, identifier))
                self.event(connection, identifier, row["attempt"], "CANCEL_REQUESTED", {"boundary": "after current static phase"})
        return self.get(identifier)

    def resume(self, identifier: str) -> None:
        with self.connect() as connection:
            row = connection.execute("SELECT status,attempt FROM jobs WHERE id=?", (identifier,)).fetchone()
            if row is None or row["status"] not in {"FAILED", "CANCELLED", "INTERRUPTED"}:
                raise ValueError("JOB_NOT_RESUMABLE")
            connection.execute("UPDATE jobs SET status='QUEUED',cancellation=0,result=NULL,attempt=attempt+1 WHERE id=?", (identifier,))
            self.event(connection, identifier, row["attempt"]+1, "QUEUED", {"resumed": True})

    def checkpoint(self, identifier: str, stage: str) -> bool:
        with self.connect() as connection:
            row = connection.execute("SELECT cancellation,attempt FROM jobs WHERE id=?", (identifier,)).fetchone()
            if row["cancellation"]:
                connection.execute("UPDATE jobs SET status='CANCELLED' WHERE id=?", (identifier,))
                self.event(connection, identifier, row["attempt"], "CANCELLED", {})
                return False
            self.event(connection, identifier, row["attempt"], stage, {})
        return True

    def run(self, identifier: str) -> None:
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM jobs WHERE id=?", (identifier,)).fetchone()
            if row is None or row["status"] != "QUEUED":
                return
            connection.execute("UPDATE jobs SET status='RUNNING',lease=? WHERE id=?", (time.time(), identifier))
            request = json.loads(row["request"])
        finished = threading.Event()
        def heartbeat() -> None:
            while not finished.wait(5):
                with self.connect() as connection:
                    connection.execute("UPDATE jobs SET lease=? WHERE id=? AND status='RUNNING' AND attempt=?", (time.time(), identifier, row["attempt"]))
        thread = threading.Thread(target=heartbeat, daemon=True)
        thread.start()
        try:
            if not self.checkpoint(identifier, "DISCOVERY" if request["action"] == "inspect" else "COMPILATION"):
                return
            if request["action"] == "inspect":
                discovery = discover_source(request["source"], self.output, request.get("ref"))
                if not self.checkpoint(identifier, "STORE_DISCOVERY"):
                    return
                result = {"run_id": write_discovery(discovery, self.output).name}
            else:
                workflow = WorkflowRequest.model_validate(request["workflow"]) if request.get("workflow") else None
                result = build_workflow(self.output / request["run_id"], request["goal"], request.get("target", "portable"), workflow)
            if not self.checkpoint(identifier, "FINALIZE"):
                return
            status = "SUCCEEDED"
        except (ValueError, TypeError, OSError, KeyError) as error:
            result = {"error": str(error)[:2000], "failure_class": type(error).__name__}
            status = "FAILED"
        finally:
            finished.set()
            thread.join(timeout=2)
        with self.connect() as connection:
            connection.execute("UPDATE jobs SET status=?,result=? WHERE id=?", (status, canonical_json(result), identifier))
            self.event(connection, identifier, row["attempt"], status, result)

    def start(self, identifier: str) -> None:
        def worker() -> None:
            with self.slots:
                self.run(identifier)
        threading.Thread(target=worker, daemon=True).start()
