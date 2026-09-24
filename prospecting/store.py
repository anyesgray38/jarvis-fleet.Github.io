"""SQLite-backed prospect memory using the existing .jarvis persistence boundary."""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from .models import BusinessRecord, ScanResult


class ProspectStore:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path or os.environ.get("AEGIS_PROSPECT_DB", ".jarvis/prospects.db"))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init(self) -> None:
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS scans (
                    scan_id TEXT PRIMARY KEY,
                    request_json TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS businesses (
                    business_id TEXT PRIMARY KEY,
                    record_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_business_score ON businesses(json_extract(record_json, '$.opportunity_score'));
            """)

    def save_scan(self, result: ScanResult) -> None:
        payload = json.dumps(result.to_dict(), sort_keys=True)
        with self._connect() as db:
            db.execute("INSERT OR REPLACE INTO scans(scan_id, request_json, result_json, started_at, completed_at) VALUES(?,?,?,?,?)", (result.scan_id, json.dumps(result.request, sort_keys=True), payload, result.started_at, result.completed_at))
            for business in result.businesses:
                db.execute("INSERT OR REPLACE INTO businesses(business_id, record_json, updated_at) VALUES(?,?,CURRENT_TIMESTAMP)", (business.business_id, json.dumps(business.to_dict(), sort_keys=True)))

    def save_business(self, business: BusinessRecord) -> None:
        with self._connect() as db:
            db.execute("INSERT OR REPLACE INTO businesses(business_id, record_json, updated_at) VALUES(?,?,CURRENT_TIMESTAMP)", (business.business_id, json.dumps(business.to_dict(), sort_keys=True)))

    def get_scan(self, scan_id: str) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute("SELECT result_json FROM scans WHERE scan_id = ?", (scan_id,)).fetchone()
        return json.loads(row["result_json"]) if row else None

    def list_scans(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute("SELECT result_json FROM scans ORDER BY created_at DESC LIMIT ?", (max(1, min(100, limit)),)).fetchall()
        return [json.loads(row["result_json"]) for row in rows]

    def get_business(self, business_id: str) -> BusinessRecord | None:
        with self._connect() as db:
            row = db.execute("SELECT record_json FROM businesses WHERE business_id = ?", (business_id,)).fetchone()
        return BusinessRecord(**json.loads(row["record_json"])) if row else None

    def list_businesses(self, *, min_score: int = 0, limit: int = 100) -> list[BusinessRecord]:
        with self._connect() as db:
            rows = db.execute("SELECT record_json FROM businesses WHERE json_extract(record_json, '$.opportunity_score') >= ? ORDER BY json_extract(record_json, '$.opportunity_score') DESC LIMIT ?", (min_score, max(1, min(500, limit)))).fetchall()
        return [BusinessRecord(**json.loads(row["record_json"])) for row in rows]
