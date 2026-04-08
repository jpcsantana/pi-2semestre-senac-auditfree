from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sqlite3


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

    def _table_exists(self, conn: sqlite3.Connection, table_name: str) -> bool:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table_name,),
        ).fetchone()
        return row is not None

    def _table_columns(self, conn: sqlite3.Connection, table_name: str) -> set[str]:
        rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        return {str(row["name"]) for row in rows}

    def _is_legacy_schema(self, conn: sqlite3.Connection) -> bool:
        if not self._table_exists(conn, "devices"):
            return False
        columns = self._table_columns(conn, "devices")
        return "device_id" in columns and "id" not in columns

    def _create_schema(self, conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip TEXT NOT NULL CHECK (length(trim(ip)) > 0),
                machine_name TEXT NOT NULL CHECK (length(trim(machine_name)) > 0),
                notify_email TEXT NOT NULL CHECK (length(trim(notify_email)) > 0),
                port INTEGER NOT NULL DEFAULT 80 CHECK (port BETWEEN 1 AND 65535),
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

            CREATE INDEX IF NOT EXISTS idx_check_history_device_id
                ON check_history(device_id);
            CREATE INDEX IF NOT EXISTS idx_check_history_checked_at
                ON check_history(checked_at DESC);
            """
        )

    def _migrate_legacy_schema(self, conn: sqlite3.Connection) -> None:
        conn.execute("ALTER TABLE devices RENAME TO devices_legacy")
        if self._table_exists(conn, "check_history"):
            conn.execute("ALTER TABLE check_history RENAME TO check_history_legacy")

        self._create_schema(conn)

        legacy_devices = conn.execute(
            """
            SELECT
                device_id,
                ip,
                machine_name,
                notify_email,
                port,
                created_at,
                last_status,
                last_checked_at
            FROM devices_legacy
            ORDER BY rowid
            """
        ).fetchall()

        id_map: dict[str, int] = {}
        for row in legacy_devices:
            try:
                port = int(row["port"]) if row["port"] is not None else 80
            except (TypeError, ValueError):
                port = 80
            if port < 1 or port > 65535:
                port = 80

            created_at = str(row["created_at"] or _utc_now_iso())
            status = row["last_status"]
            safe_status = str(status) if status in {"online", "offline"} else None

            cursor = conn.execute(
                """
                INSERT INTO devices (
                    ip, machine_name, notify_email, port, created_at, last_status, last_checked_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(row["ip"]),
                    str(row["machine_name"]),
                    str(row["notify_email"]),
                    port,
                    created_at,
                    safe_status,
                    row["last_checked_at"],
                ),
            )
            legacy_key = str(row["device_id"])
            id_map[legacy_key] = int(cursor.lastrowid)

        if self._table_exists(conn, "check_history_legacy"):
            legacy_history = conn.execute(
                """
                SELECT
                    device_id,
                    status,
                    checked_at,
                    latency_ms,
                    error_message
                FROM check_history_legacy
                ORDER BY id
                """
            ).fetchall()

            for row in legacy_history:
                mapped_id = id_map.get(str(row["device_id"]))
                if mapped_id is None:
                    continue

                status = str(row["status"])
                safe_status = status if status in {"online", "offline"} else "offline"
                latency = row["latency_ms"]
                if latency is None:
                    safe_latency = None
                else:
                    try:
                        parsed_latency = int(latency)
                    except (TypeError, ValueError):
                        safe_latency = None
                    else:
                        safe_latency = parsed_latency if parsed_latency >= 0 else None
                checked_at = str(row["checked_at"] or _utc_now_iso())

                conn.execute(
                    """
                    INSERT INTO check_history (
                        device_id, status, checked_at, latency_ms, error_message
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        mapped_id,
                        safe_status,
                        checked_at,
                        safe_latency,
                        row["error_message"],
                    ),
                )

        conn.execute("DROP TABLE devices_legacy")
        if self._table_exists(conn, "check_history_legacy"):
            conn.execute("DROP TABLE check_history_legacy")

    def init_db(self) -> None:
        with self._connect() as conn:
            if self._is_legacy_schema(conn):
                self._migrate_legacy_schema(conn)
            else:
                self._create_schema(conn)
            conn.commit()

    def add_device(
        self,
        ip: str,
        machine_name: str,
        notify_email: str,
        port: int,
    ) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO devices (
                    ip, machine_name, notify_email, port, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (ip, machine_name, notify_email, port, _utc_now_iso()),
            )
            conn.commit()
        return int(cursor.lastrowid)

    def list_devices(self) -> list[dict[str, object]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    id,
                    ip,
                    machine_name,
                    notify_email,
                    port,
                    created_at,
                    last_status,
                    last_checked_at
                FROM devices
                ORDER BY id
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def get_device(self, device_id: int) -> dict[str, object] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    id,
                    ip,
                    machine_name,
                    notify_email,
                    port,
                    created_at,
                    last_status,
                    last_checked_at
                FROM devices
                WHERE id = ?
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
                INSERT INTO check_history (
                    device_id, status, checked_at, latency_ms, error_message
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (device_id, status, checked_at, latency_ms, error_message),
            )
            conn.execute(
                """
                UPDATE devices
                SET last_status = ?, last_checked_at = ?
                WHERE id = ?
                """,
                (status, checked_at, device_id),
            )
            conn.commit()

    def get_history(self, device_id: int | None = None, limit: int = 50) -> list[dict[str, object]]:
        safe_limit = max(1, min(limit, 1000))
        with self._connect() as conn:
            if device_id is not None:
                rows = conn.execute(
                    """
                    SELECT
                        h.id,
                        h.device_id,
                        d.machine_name,
                        d.ip,
                        d.port,
                        h.status,
                        h.checked_at,
                        h.latency_ms,
                        h.error_message
                    FROM check_history AS h
                    JOIN devices AS d ON d.id = h.device_id
                    WHERE h.device_id = ?
                    ORDER BY h.checked_at DESC
                    LIMIT ?
                    """,
                    (device_id, safe_limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT
                        h.id,
                        h.device_id,
                        d.machine_name,
                        d.ip,
                        d.port,
                        h.status,
                        h.checked_at,
                        h.latency_ms,
                        h.error_message
                    FROM check_history AS h
                    JOIN devices AS d ON d.id = h.device_id
                    ORDER BY h.checked_at DESC
                    LIMIT ?
                    """,
                    (safe_limit,),
                ).fetchall()
        return [dict(row) for row in rows]
