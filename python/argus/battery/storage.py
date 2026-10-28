"""Local, opt-in report storage with parameterized SQL and bounded listing."""

from __future__ import annotations
import datetime as dt
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any


class BatteryStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=5)
        connection.execute(
            "CREATE TABLE IF NOT EXISTS assessments (id TEXT PRIMARY KEY,battery_id TEXT NOT NULL,created_at TEXT NOT NULL,report TEXT NOT NULL)"
        )
        return connection

    def save(self, report: dict[str, Any]) -> str:
        created = dt.datetime.now(dt.timezone.utc).isoformat()
        with closing(self._connect()) as connection, connection:
            connection.execute(
                "INSERT OR IGNORE INTO assessments (id,battery_id,created_at,report) VALUES (?,?,?,?)",
                (
                    report["assessment_id"],
                    report["battery_id"],
                    created,
                    json.dumps(report, allow_nan=False),
                ),
            )
        return report["assessment_id"]

    def list(self, battery_id: str) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT created_at,report FROM assessments WHERE battery_id=? ORDER BY created_at DESC LIMIT 50",
                (battery_id,),
            ).fetchall()
        return [{"saved_at": r[0], "assessment": json.loads(r[1])} for r in rows]
