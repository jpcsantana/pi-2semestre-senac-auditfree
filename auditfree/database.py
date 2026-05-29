from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sqlite3


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS devices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ip TEXT NOT NULL CHECK (length(trim(ip)) > 0),
    machine_name TEXT NOT NULL CHECK (length(trim(machine_name)) > 0),
    anydesk_code TEXT,
    created_at TEXT NOT NULL,
    last_status TEXT CHECK (last_status IN ('online', 'offline') OR last_status IS NULL),
    last_checked_at TEXT
);

CREATE TABLE IF NOT EXISTS check_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('online', 'offline')),
    checked_at TEXT NOT NULL,
    latency_ms INTEGER CHECK (latency_ms IS NULL OR latency_ms >= 0),
    error_message TEXT,
    FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_check_history_device_id ON check_history(device_id);
CREATE INDEX IF NOT EXISTS idx_check_history_checked_at ON check_history(checked_at DESC);
"""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Database:
    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _table_exists(self, conn: sqlite3.Connection, name: str) -> bool:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (name,),
        ).fetchone()
        return row is not None

    def _columns(self, conn: sqlite3.Connection, table: str) -> set[str]:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        return {str(r["name"]) for r in rows}

    def init_db(self) -> None:
        with self._connect() as conn:
            if self._table_exists(conn, "devices"):
                cols = self._columns(conn, "devices")
                if "notify_email" in cols or "port" in cols or "device_id" in cols:
                    self._migrate_legacy(conn)
                elif "anydesk_code" not in cols:
                    conn.execute("ALTER TABLE devices ADD COLUMN anydesk_code TEXT")
            conn.executescript(SCHEMA_SQL)
            conn.commit()

    def _migrate_legacy(self, conn: sqlite3.Connection) -> None:
        conn.execute("ALTER TABLE devices RENAME TO _devices_old")
        if self._table_exists(conn, "check_history"):
            conn.execute("DROP TABLE check_history")
        conn.executescript(SCHEMA_SQL)
        old_cols = self._columns(conn, "_devices_old")
        has_id = "id" in old_cols
        id_select = "id" if has_id else "rowid AS id"
        conn.execute(
            f"""
            INSERT INTO devices (id, ip, machine_name, anydesk_code, created_at, last_status, last_checked_at)
            SELECT {id_select}, ip, machine_name, NULL,
                   COALESCE(created_at, ?), last_status, last_checked_at
            FROM _devices_old
            """,
            (_utc_now_iso(),),
        )
        conn.execute("DROP TABLE _devices_old")

    def add_device(
        self,
        ip: str,
        machine_name: str,
        anydesk_code: str | None = None,
    ) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO devices (ip, machine_name, anydesk_code, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (ip, machine_name, anydesk_code, _utc_now_iso()),
            )
            conn.commit()
        return int(cursor.lastrowid)

    def list_devices(self) -> list[dict[str, object]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, ip, machine_name, anydesk_code, created_at,
                       last_status, last_checked_at
                FROM devices
                ORDER BY id
                """
            ).fetchall()
        return [dict(r) for r in rows]

    def get_device(self, device_id: int) -> dict[str, object] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, ip, machine_name, anydesk_code, created_at,
                       last_status, last_checked_at
                FROM devices WHERE id = ?
                """,
                (device_id,),
            ).fetchone()
        return dict(row) if row else None

    def record_check(
        self,
        device_id: int,
        status: str,
        checked_at: str,
        latency_ms: int | None,
        error_message: str | None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO check_history (device_id, status, checked_at, latency_ms, error_message)
                VALUES (?, ?, ?, ?, ?)
                """,
                (device_id, status, checked_at, latency_ms, error_message),
            )
            conn.execute(
                "UPDATE devices SET last_status = ?, last_checked_at = ? WHERE id = ?",
                (status, checked_at, device_id),
            )
            conn.commit()

    def get_history(self, device_id: int | None = None, limit: int = 50) -> list[dict[str, object]]:
        safe_limit = max(1, min(limit, 1000))
        base = """
            SELECT h.id, h.device_id, d.machine_name, d.ip,
                   h.status, h.checked_at, h.latency_ms, h.error_message
            FROM check_history AS h
            JOIN devices AS d ON d.id = h.device_id
        """
        with self._connect() as conn:
            if device_id is not None:
                rows = conn.execute(
                    base + " WHERE h.device_id = ? ORDER BY h.checked_at DESC LIMIT ?",
                    (device_id, safe_limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    base + " ORDER BY h.checked_at DESC LIMIT ?",
                    (safe_limit,),
                ).fetchall()
        return [dict(r) for r in rows]
