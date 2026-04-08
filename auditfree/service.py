from __future__ import annotations

import sqlite3

from .config import SMTPSettings
from .database import Database
from .emailer import send_offline_alert
from .network import check_availability


class AuditService:
    def __init__(self, db: Database, smtp_settings: SMTPSettings) -> None:
        self.db = db
        self.smtp_settings = smtp_settings

    def register_device(
        self,
        ip: str,
        machine_name: str,
        notify_email: str,
        port: int,
    ) -> int:
        try:
            return self.db.add_device(
                ip=ip,
                machine_name=machine_name,
                notify_email=notify_email,
                port=port,
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError("Falha ao cadastrar dispositivo por restricao de integridade do banco.") from exc

    def list_devices(self) -> list[dict[str, object]]:
        return self.db.list_devices()

    def check_device(self, device_id: int, timeout: float = 2.0, send_alert: bool = True) -> dict[str, object]:
        device = self.db.get_device(device_id)
        if device is None:
            raise ValueError(f"Dispositivo '{device_id}' nao encontrado.")

        result = check_availability(str(device["ip"]), int(device["port"]), timeout=timeout)
        self.db.record_check(
            device_id=device_id,
            status=result.status,
            checked_at=result.checked_at,
            latency_ms=result.latency_ms,
            error_message=result.error_message,
        )

        alert_sent = False
        alert_message = ""
        if send_alert and result.status == "offline":
            alert_sent, alert_message = send_offline_alert(device, result, self.smtp_settings)

        return {
            "device": device,
            "result": result,
            "alert_sent": alert_sent,
            "alert_message": alert_message,
        }

    def check_all(self, timeout: float = 2.0, send_alert: bool = True) -> list[dict[str, object]]:
        devices = self.db.list_devices()
        reports: list[dict[str, object]] = []

        for device in devices:
            result = check_availability(str(device["ip"]), int(device["port"]), timeout=timeout)
            self.db.record_check(
                device_id=int(device["id"]),
                status=result.status,
                checked_at=result.checked_at,
                latency_ms=result.latency_ms,
                error_message=result.error_message,
            )

            alert_sent = False
            alert_message = ""
            if send_alert and result.status == "offline":
                alert_sent, alert_message = send_offline_alert(device, result, self.smtp_settings)

            reports.append(
                {
                    "device": device,
                    "result": result,
                    "alert_sent": alert_sent,
                    "alert_message": alert_message,
                }
            )

        return reports

    def get_history(self, device_id: int | None = None, limit: int = 50) -> list[dict[str, object]]:
        return self.db.get_history(device_id=device_id, limit=limit)
