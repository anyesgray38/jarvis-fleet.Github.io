"""Durable remote job queue for AEGIS project workers."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any
from uuid import uuid4

STATUSES = ("queued","claimed","running","verifying","passed","failed","rejected","escalated","cancelled")

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

@dataclass(frozen=True)
class RemoteJob:
    job_id: str
    objective: str
    repository: str
    ref: str
    capability: str
    trust: str
    input: dict[str, Any]
    status: str
    worker: str | None
    created_at: str
    updated_at: str
    result: dict[str, Any] | None = None
    error: str | None = None

class JobStore:
    """SQLite-backed durable job and event store."""
    def __init__(self, path: str | Path = ".jarvis/jobs.db") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self) -> None:
        with self._connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY, objective TEXT NOT NULL,
                    repository TEXT NOT NULL, ref TEXT NOT NULL,
                    capability TEXT NOT NULL, trust TEXT NOT NULL,
                    input_json TEXT NOT NULL, status TEXT NOT NULL,
                    worker TEXT, result_json TEXT, error TEXT,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT NOT NULL,
                    event TEXT NOT NULL, data_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
                CREATE INDEX IF NOT EXISTS idx_events_job ON events(job_id, id);
            """)

    def create(self, objective: str, repository: str, *, ref: str = "master",
               capability: str = "terminal.execute", trust: str = "PREPARE",
               input: dict[str, Any] | None = None, job_id: str | None = None) -> RemoteJob:
        if not objective.strip(): raise ValueError("objective is required")
        if not repository.strip(): raise ValueError("repository is required")
        job_id = job_id or f"job_{uuid4().hex}"
        now = _now()
        with self._connect() as db:
            db.execute(
                """INSERT INTO jobs
                (job_id, objective, repository, ref, capability, trust, input_json,
                 status, worker, result_json, error, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'queued', NULL, NULL, NULL, ?, ?)""",
                (job_id, objective, repository, ref, capability, trust,
                 json.dumps(input or {}, sort_keys=True), now, now),
            )
        self.event(job_id, "job.queued", {"objective": objective, "repository": repository})
        return self.get(job_id)

    def attach_remote(self, job_id: str, *, issue_number: int, issue_url: str | None = None) -> RemoteJob:
        job = self.get(job_id)
        payload = {"issue_number": issue_number}
        if issue_url: payload["issue_url"] = issue_url
        self.event(job_id, "job.remote_submitted", payload)
        return job

    def get(self, job_id: str) -> RemoteJob:
        with self._connect() as db:
            row = db.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
        if row is None: raise KeyError(f"unknown job: {job_id}")
        return self._row(row)

    def list(self, status: str | None = None) -> list[RemoteJob]:
        query, params = "SELECT * FROM jobs", ()
        if status:
            if status not in STATUSES: raise ValueError(f"invalid status: {status}")
            query += " WHERE status=?"; params = (status,)
        with self._connect() as db:
            rows = db.execute(query + " ORDER BY created_at DESC", params).fetchall()
        return [self._row(row) for row in rows]

    def claim(self, worker: str) -> RemoteJob | None:
        now = _now()
        with self._connect() as db:
            row = db.execute("SELECT * FROM jobs WHERE status='queued' ORDER BY created_at LIMIT 1").fetchone()
            if row is None: return None
            changed = db.execute(
                "UPDATE jobs SET status='claimed', worker=?, updated_at=? WHERE job_id=? AND status='queued'",
                (worker, now, row["job_id"]),
            )
            if changed.rowcount != 1: return None
        self.event(row["job_id"], "job.claimed", {"worker": worker})
        return self.get(row["job_id"])

    def transition(self, job_id: str, status: str, *, result: dict[str, Any] | None = None,
                   error: str | None = None, data: dict[str, Any] | None = None) -> RemoteJob:
        if status not in STATUSES: raise ValueError(f"invalid status: {status}")
        with self._connect() as db:
            db.execute(
                "UPDATE jobs SET status=?, result_json=?, error=?, updated_at=? WHERE job_id=?",
                (status, json.dumps(result, sort_keys=True, default=str) if result is not None else None,
                 error, _now(), job_id),
            )
        self.event(job_id, f"job.{status}", data or {})
        return self.get(job_id)

    def event(self, job_id: str, event: str, data: dict[str, Any] | None = None) -> None:
        with self._connect() as db:
            db.execute("INSERT INTO events(job_id,event,data_json,created_at) VALUES(?,?,?,?)",
                       (job_id, event, json.dumps(data or {}, sort_keys=True, default=str), _now()))

    def events(self, job_id: str, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT event,data_json,created_at FROM events WHERE job_id=? ORDER BY id DESC LIMIT ?",
                (job_id, max(1, min(limit, 1000))),
            ).fetchall()
        return [{"event": r["event"], "data": json.loads(r["data_json"]), "created_at": r["created_at"]}
                for r in reversed(rows)]

    @staticmethod
    def _row(row: sqlite3.Row) -> RemoteJob:
        return RemoteJob(
            job_id=row["job_id"], objective=row["objective"], repository=row["repository"],
            ref=row["ref"], capability=row["capability"], trust=row["trust"],
            input=json.loads(row["input_json"]), status=row["status"], worker=row["worker"],
            created_at=row["created_at"], updated_at=row["updated_at"],
            result=json.loads(row["result_json"]) if row["result_json"] else None, error=row["error"],
        )
