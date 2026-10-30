"""SQLite store of raw OCPP meter values. Parameterized queries only.

The card identifier (``idTag``) is never read, so it cannot be stored.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Any

from argus.ingest.ocpp_mapping import MappedSample, map_meter_value, parse_time

CLOCK_DRIFT_SECONDS = 300.0
SCHEMA = """
CREATE TABLE IF NOT EXISTS stations (
    station_id TEXT PRIMARY KEY, vendor TEXT, model TEXT, last_seen REAL);
CREATE TABLE IF NOT EXISTS meter_values (
    station_id TEXT NOT NULL, connector_id INTEGER NOT NULL, ts REAL NOT NULL,
    measurand TEXT NOT NULL, phase TEXT NOT NULL, location TEXT NOT NULL,
    unit TEXT, value TEXT NOT NULL, received_at REAL NOT NULL,
    PRIMARY KEY (station_id, connector_id, ts, measurand, phase, location));
CREATE TABLE IF NOT EXISTS ingest_log (
    station_id TEXT NOT NULL, received_at REAL NOT NULL, kind TEXT NOT NULL);
"""


def _text(value: Any) -> str | None:
    return None if value is None else str(getattr(value, "value", value))


class OcppStore:
    def __init__(self, path: str | Path) -> None:
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock:
            self._db.executescript(SCHEMA)

    def close(self) -> None:
        with self._lock:
            self._db.close()

    def upsert_station(
        self, station_id: str, vendor: str | None, model: str | None, now: float
    ) -> None:
        with self._lock, self._db:
            self._db.execute(
                "INSERT INTO stations VALUES (?, ?, ?, ?) ON CONFLICT(station_id) "
                "DO UPDATE SET vendor=excluded.vendor, model=excluded.model, "
                "last_seen=excluded.last_seen",
                (station_id, vendor, model, now),
            )

    def log(self, station_id: str, kind: str, now: float) -> None:
        with self._lock, self._db:
            self._db.execute(
                "INSERT INTO ingest_log VALUES (?, ?, ?)", (station_id, now, kind)
            )

    def add_meter_values(
        self,
        station_id: str,
        connector_id: int,
        meter_value: list[dict[str, Any]],
        received_at: float,
    ) -> dict[str, int]:
        """Store the raw readings; report how many were new, repeated or rejected."""
        added = repeated = rejected = 0
        drifted = False
        with self._lock, self._db:
            for entry in meter_value:
                ts = parse_time(entry.get("timestamp"))
                if ts is None:
                    rejected += 1
                    continue
                drifted = drifted or abs(ts - received_at) > CLOCK_DRIFT_SECONDS
                for item in entry.get("sampled_value") or []:
                    cur = self._db.execute(
                        "INSERT OR IGNORE INTO meter_values VALUES (?,?,?,?,?,?,?,?,?)",
                        (
                            station_id,
                            int(connector_id),
                            ts,
                            _text(item.get("measurand"))
                            or "Energy.Active.Import.Register",
                            _text(item.get("phase")) or "",
                            _text(item.get("location")) or "",
                            _text(item.get("unit")),
                            str(item.get("value")),
                            received_at,
                        ),
                    )
                    if cur.rowcount:
                        added += 1
                    else:
                        repeated += 1
            for kind, hit in (
                ("rejected_timestamp", rejected),
                ("repeated_values", repeated),
                ("clock_drift", drifted),
            ):
                if hit:
                    self._db.execute(
                        "INSERT INTO ingest_log VALUES (?, ?, ?)",
                        (station_id, received_at, kind),
                    )
        return {"added": added, "repeated": repeated, "rejected": rejected}

    def samples(self, station_id: str, connector_id: int) -> list[MappedSample]:
        with self._lock:
            rows = self._db.execute(
                "SELECT ts, measurand, phase, location, unit, value FROM meter_values "
                "WHERE station_id=? AND connector_id=? ORDER BY ts",
                (station_id, int(connector_id)),
            ).fetchall()
        grouped: dict[float, list[dict[str, Any]]] = {}
        for ts, measurand, phase, location, unit, value in rows:
            grouped.setdefault(ts, []).append(
                {
                    "measurand": measurand,
                    "phase": phase or None,
                    "location": location or None,
                    "unit": unit,
                    "value": value,
                }
            )
        out = []
        for ts, items in grouped.items():
            stamp = _iso(ts)
            mapped = map_meter_value({"timestamp": stamp, "sampled_value": items})
            if mapped is not None:
                out.append(mapped)
        return out

    def quality(self, station_id: str) -> dict[str, int]:
        with self._lock:
            rows = self._db.execute(
                "SELECT kind, COUNT(*) FROM ingest_log WHERE station_id=? GROUP BY kind",
                (station_id,),
            ).fetchall()
        return {kind: count for kind, count in rows}


def _iso(ts: float) -> str:
    import datetime as dt

    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).isoformat()
