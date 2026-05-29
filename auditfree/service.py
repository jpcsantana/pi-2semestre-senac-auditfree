from __future__ import annotations

import sqlite3

from .database import Database
from .logger import AuditLogger
from .network import PingResult, PortScanResult, ping_host, scan_insecure_ports
from .ssh_analyzer import SSHAnalysisResult, analyze_installed_programs


class AuditService:
    def __init__(self, db: Database, logger: AuditLogger) -> None:
        self.db = db
        self.logger = logger

    def register_device(
        self,
        ip: str,
        machine_name: str,
        anydesk_code: str | None = None,
    ) -> int:
        try:
            return self.db.add_device(
                ip=ip,
                machine_name=machine_name,
                anydesk_code=anydesk_code,
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError("Falha ao cadastrar dispositivo (restricao de integridade).") from exc

    def list_devices(self) -> list[dict[str, object]]:
        return self.db.list_devices()

    def get_device(self, device_id: int) -> dict[str, object]:
        device = self.db.get_device(device_id)
        if device is None:
            raise ValueError(f"Dispositivo '{device_id}' nao encontrado.")
        return device

    def check_device(self, device_id: int, timeout: float = 2.0) -> dict[str, object]:
        device = self.get_device(device_id)
        result = ping_host(str(device["ip"]), timeout=timeout)
        self.db.record_check(
            device_id=device_id,
            status=result.status,
            checked_at=result.checked_at,
            latency_ms=result.latency_ms,
            error_message=result.error_message,
        )
        self._log_ping(device, result)
        return {"device": device, "result": result}

    def check_all(self, timeout: float = 2.0) -> list[dict[str, object]]:
        reports: list[dict[str, object]] = []
        for device in self.db.list_devices():
            result = ping_host(str(device["ip"]), timeout=timeout)
            self.db.record_check(
                device_id=int(device["id"]),
                status=result.status,
                checked_at=result.checked_at,
                latency_ms=result.latency_ms,
                error_message=result.error_message,
            )
            self._log_ping(device, result)
            reports.append({"device": device, "result": result})
        return reports

    def scan_ports(self, device_id: int, timeout: float = 0.5) -> dict[str, object]:
        device = self.get_device(device_id)
        scan = scan_insecure_ports(str(device["ip"]), timeout=timeout)
        self._log_scan(device, scan)
        return {"device": device, "scan": scan}

    def ssh_analyze(
        self,
        device_id: int,
        username: str,
        password: str,
        port: int = 22,
        timeout: float = 10.0,
    ) -> dict[str, object]:
        device = self.get_device(device_id)
        result = analyze_installed_programs(
            host=str(device["ip"]),
            username=username,
            password=password,
            port=port,
            timeout=timeout,
        )
        self._log_ssh(device, result)
        return {"device": device, "result": result}

    def get_history(self, device_id: int | None = None, limit: int = 50) -> list[dict[str, object]]:
        return self.db.get_history(device_id=device_id, limit=limit)

    def _log_ping(self, device: dict[str, object], result: PingResult) -> None:
        target = f"{device['machine_name']} ({device['ip']})"
        summary = f"status={result.status}"
        if result.latency_ms is not None:
            summary += f" latencia_ms={result.latency_ms}"
        self.logger.log_audit("ping", target, summary)
        if result.status == "offline":
            self.logger.log_error("ping", target, result.error_message or "host inacessivel")

    def _log_scan(self, device: dict[str, object], scan: PortScanResult) -> None:
        target = f"{device['machine_name']} ({device['ip']})"
        if scan.open_ports:
            portas = ",".join(str(p) for p, _ in scan.open_ports)
            self.logger.log_audit("port_scan", target, f"portas_inseguras_abertas=[{portas}]")
            self.logger.log_error(
                "port_scan",
                target,
                f"portas inseguras abertas: {portas}",
            )
        else:
            self.logger.log_audit("port_scan", target, "nenhuma porta insegura aberta")

    def _log_ssh(self, device: dict[str, object], result: SSHAnalysisResult) -> None:
        target = f"{device['machine_name']} ({device['ip']})"
        if result.success:
            qty = len([line for line in result.programs.splitlines() if line.strip()])
            self.logger.log_audit(
                "ssh_programs",
                target,
                f"gerenciador={result.package_manager} pacotes={qty}",
            )
        else:
            self.logger.log_audit("ssh_programs", target, "falha")
            self.logger.log_error("ssh_programs", target, result.error_message or "erro desconhecido")
