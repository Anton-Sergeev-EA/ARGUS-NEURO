"""Local, opt-in report storage with parameterized SQL and bounded listing."""

from __future__ import annotations
import datetime as dt
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

HISTORY_LIMIT = 50

SCHEMA = """
CREATE TABLE IF NOT EXISTS reports (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    assessment_id TEXT NOT NULL,
    battery_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    schema_version INTEGER NOT NULL,
    report TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS reports_by_battery ON reports (battery_id, seq DESC);
"""


class BatteryStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=5)
        connection.executescript(SCHEMA)
        self._migrate_legacy(connection)
        return connection

    @staticmethod
    def _migrate_legacy(connection: sqlite3.Connection) -> None:
        """Move rows of the first storage layout (one row per content hash) once."""
        legacy = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='assessments'"
        ).fetchone()
        if legacy is None:
            return
        with connection:
            connection.execute(
                "INSERT INTO reports (assessment_id,battery_id,created_at,schema_version,report) "
                "SELECT id,battery_id,created_at,1,report FROM assessments ORDER BY created_at"
            )
            connection.execute("DROP TABLE assessments")

    def save(self, report: dict[str, Any]) -> str:
        """Append a report; an identical report right after itself adds nothing new."""
        created = dt.datetime.now(dt.timezone.utc).isoformat()
        with closing(self._connect()) as connection, connection:
            latest = connection.execute(
                "SELECT assessment_id FROM reports WHERE battery_id=? ORDER BY seq DESC LIMIT 1",
                (report["battery_id"],),
            ).fetchone()
            if latest is None or latest[0] != report["assessment_id"]:
                connection.execute(
                    "INSERT INTO reports (assessment_id,battery_id,created_at,schema_version,report) "
                    "VALUES (?,?,?,?,?)",
                    (
                        report["assessment_id"],
                        report["battery_id"],
                        created,
                        report.get("schema_version", 1),
                        json.dumps(report, allow_nan=False),
                    ),
                )
        return report["assessment_id"]

    def list(self, battery_id: str) -> list[dict[str, Any]]:
        """Newest first, at most ``HISTORY_LIMIT`` reports."""
        if not self.path.exists():
            return []
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT created_at,report FROM reports WHERE battery_id=? "
                "ORDER BY seq DESC LIMIT ?",
                (battery_id, HISTORY_LIMIT),
            ).fetchall()
        return [{"saved_at": r[0], "assessment": json.loads(r[1])} for r in rows]
