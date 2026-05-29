from __future__ import annotations

import socket
import sqlite3

from .database import Database
from .local_audit import LocalAuditResult, collect_local_audit
from .logger import AuditLogger
from .network import PingResult, PortScanResult, lookup_hostname, ping_host, scan_insecure_ports


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

    def update_device(
        self,
        device_id: int,
        ip: str,
        machine_name: str,
        anydesk_code: str | None,
    ) -> None:
        if not ip.strip():
            raise ValueError("IP nao pode ficar vazio.")
        if not machine_name.strip():
            raise ValueError("Nome da maquina nao pode ficar vazio.")
        self.get_device(device_id)
        self.db.update_device(device_id, ip.strip(), machine_name.strip(), anydesk_code)
        self.logger.log_audit(
            "edit_device", ip.strip(), f"machine_name={machine_name.strip()}"
        )

    def delete_device(self, device_id: int) -> None:
        device = self.get_device(device_id)
        self.db.delete_device(device_id)
        self.logger.log_audit(
            "delete_device",
            f"{device['machine_name']} ({device['ip']})",
            "dispositivo_excluido=true",
        )

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

    def run_local_audit(self) -> dict[str, object]:
        result = collect_local_audit()

        local_ip = next(
            (iface["ip"] for iface in result.network_interfaces if not iface["ip"].startswith("127.")),
            None,
        )
        if local_ip is None:
            try:
                local_ip = socket.gethostbyname(result.hostname)
            except OSError:
                local_ip = "127.0.0.1"

        device = self.db.get_device_by_ip(local_ip)
        if device is None:
            device_id = self.db.add_device(ip=local_ip, machine_name=result.hostname)
            device = self.db.get_device(device_id)

        self.db.record_check(
            device_id=int(device["id"]),
            status="online",
            checked_at=result.captured_at,
            latency_ms=None,
            error_message=None,
        )

        log_content = _format_local_audit_log(result, int(device["id"]))
        log_path = self.logger.save_local_audit(log_content)
        self.logger.log_audit("local_audit", result.hostname, f"device_id={device['id']}")
        return {"result": result, "log_path": log_path, "device": device}

    def dns_validate(self, device_id: int) -> dict[str, object]:
        device = self.get_device(device_id)
        hostname, error = lookup_hostname(str(device["ip"]))
        return {"device": device, "hostname": hostname, "error": error}

    def update_device_name(self, device_id: int, new_name: str) -> None:
        if not new_name.strip():
            raise ValueError("Nome da maquina nao pode ficar vazio.")
        self.db.update_device_name(device_id, new_name.strip())
        device = self.db.get_device(device_id)
        if device:
            self.logger.log_audit(
                "dns_validate", str(device["ip"]), f"nome_atualizado={new_name.strip()}"
            )

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
        if not scan.host_responded:
            self.logger.log_error("port_scan", target, scan.error_message or "host inacessivel")
            self.logger.log_audit("port_scan", target, "host_inacessivel=true")
        elif scan.open_ports:
            portas = ",".join(str(p) for p, _ in scan.open_ports)
            self.logger.log_audit("port_scan", target, f"portas_inseguras_abertas=[{portas}]")
            self.logger.log_error("port_scan", target, f"portas inseguras abertas: {portas}")
        else:
            self.logger.log_audit("port_scan", target, "nenhuma porta insegura aberta")


def _format_local_audit_log(result: "LocalAuditResult", device_id: int) -> str:
    def _val(v: object, unit: str = "") -> str:
        return f"{v}{unit}" if v is not None else "-"

    lines = [
        f"=== Auditoria Local (device_id={device_id}) ===",
        f"Data/hora:   {result.captured_at}",
        f"Hostname:    {result.hostname}",
        f"Sistema:     {result.os_info}",
        "",
        "--- Recursos de hardware ---",
        f"CPUs logicas: {_val(result.cpu_count)}",
        f"Freq. CPU:    {_val(result.cpu_freq_mhz, ' MHz')}",
        f"RAM total:    {_val(result.ram_total_mb, ' MB')}",
        f"RAM usada:    {_val(result.ram_used_mb, ' MB')}",
        f"Disco total:  {_val(result.disk_total_gb, ' GB')}",
        f"Disco usado:  {_val(result.disk_used_gb, ' GB')}",
    ]

    if result.active_users:
        lines += ["", "--- Usuarios ativos ---"]
        lines += [f"  {u}" for u in result.active_users]

    if result.network_interfaces:
        lines += ["", "--- Interfaces de rede (IPv4) ---"]
        for iface in result.network_interfaces:
            lines.append(f"  {iface['interface']}: {iface['ip']}")

    if result.top_processes:
        lines += ["", "--- Top 10 processos por CPU ---"]
        lines.append(f"  {'PID':>7}  {'CPU%':>6}  {'MEM%':>6}  Nome")
        for p in result.top_processes:
            lines.append(
                f"  {p.get('pid', '-'):>7}  {p.get('cpu_percent', 0):>6.1f}"
                f"  {p.get('memory_percent', 0):>6.1f}  {p.get('name', '-')}"
            )
    else:
        lines += ["", "(instale psutil para coletar processos, RAM, disco e CPU freq.)"]

    lines.append("")
    return "\n".join(lines)
