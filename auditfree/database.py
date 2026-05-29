from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pyodbc


# DDL do Azure SQL Database. Cada comando e executado isoladamente em init_db,
# protegido por verificacao de existencia (Azure SQL nao suporta IF NOT EXISTS
# inline em CREATE TABLE / CREATE INDEX).
CREATE_DEVICES = """
CREATE TABLE devices (
    id INT IDENTITY(1,1) PRIMARY KEY,
    ip NVARCHAR(255) NOT NULL CHECK (LEN(TRIM(ip)) > 0),
    machine_name NVARCHAR(255) NOT NULL CHECK (LEN(TRIM(machine_name)) > 0),
    anydesk_code NVARCHAR(255) NULL,
    created_at NVARCHAR(40) NOT NULL,
    last_status NVARCHAR(10) NULL CHECK (last_status IN ('online', 'offline') OR last_status IS NULL),
    last_checked_at NVARCHAR(40) NULL
)
"""

CREATE_CHECK_HISTORY = """
CREATE TABLE check_history (
    id INT IDENTITY(1,1) PRIMARY KEY,
    device_id INT NOT NULL,
    status NVARCHAR(10) NOT NULL CHECK (status IN ('online', 'offline')),
    checked_at NVARCHAR(40) NOT NULL,
    latency_ms INT NULL CHECK (latency_ms IS NULL OR latency_ms >= 0),
    error_message NVARCHAR(MAX) NULL,
    CONSTRAINT fk_check_history_device FOREIGN KEY (device_id)
        REFERENCES devices(id) ON DELETE CASCADE
)
"""

CREATE_IDX_DEVICE_ID = (
    "CREATE INDEX idx_check_history_device_id ON check_history(device_id)"
)
CREATE_IDX_CHECKED_AT = (
    "CREATE INDEX idx_check_history_checked_at ON check_history(checked_at DESC)"
)


_BRT = timezone(timedelta(hours=-3))


def _now_iso() -> str:
    return datetime.now(_BRT).isoformat(timespec="seconds")


def _row_to_dict(cursor: pyodbc.Cursor, row: pyodbc.Row | None) -> dict[str, object] | None:
    if row is None:
        return None
    columns = [c[0] for c in cursor.description]
    return dict(zip(columns, row))


def _rows_to_dicts(cursor: pyodbc.Cursor) -> list[dict[str, object]]:
    columns = [c[0] for c in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


class Database:
    def __init__(self, connection_string: str) -> None:
        self.connection_string = connection_string

    def _connect(self) -> pyodbc.Connection:
        return pyodbc.connect(self.connection_string)

    def _table_exists(self, conn: pyodbc.Connection, name: str) -> bool:
        row = conn.cursor().execute(
            "SELECT 1 FROM sys.tables WHERE name = ?", name
        ).fetchone()
        return row is not None

    def _index_exists(self, conn: pyodbc.Connection, name: str) -> bool:
        row = conn.cursor().execute(
            "SELECT 1 FROM sys.indexes WHERE name = ?", name
        ).fetchone()
        return row is not None

    def init_db(self) -> None:
        conn = self._connect()
        try:
            cursor = conn.cursor()
            if not self._table_exists(conn, "devices"):
                cursor.execute(CREATE_DEVICES)
            if not self._table_exists(conn, "check_history"):
                cursor.execute(CREATE_CHECK_HISTORY)
            if not self._index_exists(conn, "idx_check_history_device_id"):
                cursor.execute(CREATE_IDX_DEVICE_ID)
            if not self._index_exists(conn, "idx_check_history_checked_at"):
                cursor.execute(CREATE_IDX_CHECKED_AT)
            conn.commit()
        finally:
            conn.close()

    def add_device(
        self,
        ip: str,
        machine_name: str,
        anydesk_code: str | None = None,
    ) -> int:
        conn = self._connect()
        try:
            cursor = conn.cursor()
            row = cursor.execute(
                """
                INSERT INTO devices (ip, machine_name, anydesk_code, created_at)
                OUTPUT INSERTED.id
                VALUES (?, ?, ?, ?)
                """,
                ip, machine_name, anydesk_code, _now_iso(),
            ).fetchone()
            conn.commit()
            return int(row[0])
        finally:
            conn.close()

    def get_device_by_ip(self, ip: str) -> dict[str, object] | None:
        conn = self._connect()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT TOP (1) id, ip, machine_name, anydesk_code, created_at,
                       last_status, last_checked_at
                FROM devices WHERE ip = ?
                """,
                ip,
            )
            return _row_to_dict(cursor, cursor.fetchone())
        finally:
            conn.close()

    def update_device(
        self,
        device_id: int,
        ip: str,
        machine_name: str,
        anydesk_code: str | None,
    ) -> None:
        conn = self._connect()
        try:
            conn.cursor().execute(
                "UPDATE devices SET ip = ?, machine_name = ?, anydesk_code = ? WHERE id = ?",
                ip, machine_name, anydesk_code, device_id,
            )
            conn.commit()
        finally:
            conn.close()

    def update_device_name(self, device_id: int, new_name: str) -> None:
        conn = self._connect()
        try:
            conn.cursor().execute(
                "UPDATE devices SET machine_name = ? WHERE id = ?",
                new_name, device_id,
            )
            conn.commit()
        finally:
            conn.close()

    def delete_device(self, device_id: int) -> None:
        conn = self._connect()
        try:
            conn.cursor().execute("DELETE FROM devices WHERE id = ?", device_id)
            conn.commit()
        finally:
            conn.close()

    def list_devices(self) -> list[dict[str, object]]:
        conn = self._connect()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, ip, machine_name, anydesk_code, created_at,
                       last_status, last_checked_at
                FROM devices
                ORDER BY id
                """
            )
            return _rows_to_dicts(cursor)
        finally:
            conn.close()

    def get_device(self, device_id: int) -> dict[str, object] | None:
        conn = self._connect()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, ip, machine_name, anydesk_code, created_at,
                       last_status, last_checked_at
                FROM devices WHERE id = ?
                """,
                device_id,
            )
            return _row_to_dict(cursor, cursor.fetchone())
        finally:
            conn.close()

    def record_check(
        self,
        device_id: int,
        status: str,
        checked_at: str,
        latency_ms: int | None,
        error_message: str | None,
    ) -> None:
        conn = self._connect()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO check_history (device_id, status, checked_at, latency_ms, error_message)
                VALUES (?, ?, ?, ?, ?)
                """,
                device_id, status, checked_at, latency_ms, error_message,
            )
            cursor.execute(
                "UPDATE devices SET last_status = ?, last_checked_at = ? WHERE id = ?",
                status, checked_at, device_id,
            )
            conn.commit()
        finally:
            conn.close()

    def get_history(self, device_id: int | None = None, limit: int = 50) -> list[dict[str, object]]:
        safe_limit = max(1, min(limit, 1000))
        conn = self._connect()
        try:
            cursor = conn.cursor()
            if device_id is not None:
                cursor.execute(
                    """
                    SELECT TOP (?) h.id, h.device_id, d.machine_name, d.ip,
                           h.status, h.checked_at, h.latency_ms, h.error_message
                    FROM check_history AS h
                    JOIN devices AS d ON d.id = h.device_id
                    WHERE h.device_id = ?
                    ORDER BY h.checked_at DESC
                    """,
                    safe_limit, device_id,
                )
            else:
                cursor.execute(
                    """
                    SELECT TOP (?) h.id, h.device_id, d.machine_name, d.ip,
                           h.status, h.checked_at, h.latency_ms, h.error_message
                    FROM check_history AS h
                    JOIN devices AS d ON d.id = h.device_id
                    ORDER BY h.checked_at DESC
                    """,
                    safe_limit,
                )
            return _rows_to_dicts(cursor)
        finally:
            conn.close()
