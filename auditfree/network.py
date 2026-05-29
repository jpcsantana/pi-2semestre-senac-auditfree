from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import platform
import socket
import subprocess
import time


INSECURE_PORTS: dict[int, str] = {
    21: "FTP - credenciais em texto puro",
    23: "Telnet - sem criptografia",
    25: "SMTP exposto sem TLS",
    69: "TFTP - sem autenticacao",
    135: "MS RPC - alvo comum de exploits",
    137: "NetBIOS Name Service",
    138: "NetBIOS Datagram",
    139: "NetBIOS Session",
    445: "SMB - vetor de ransomware (ex: WannaCry)",
    1433: "Microsoft SQL Server exposto",
    1521: "Oracle DB exposto",
    2049: "NFS exposto",
    3306: "MySQL exposto",
    3389: "RDP - alvo de brute force",
    5432: "PostgreSQL exposto",
    5900: "VNC - frequentemente sem senha",
    6379: "Redis - frequentemente sem autenticacao",
    11211: "Memcached exposto",
    27017: "MongoDB - frequentemente sem autenticacao",
}


@dataclass(frozen=True)
class PingResult:
    status: str
    checked_at: str
    latency_ms: int | None = None
    error_message: str | None = None


@dataclass(frozen=True)
class PortScanResult:
    ip: str
    checked_at: str
    open_ports: list[tuple[int, str]] = field(default_factory=list)
    host_responded: bool = True
    error_message: str | None = None


_BRT = timezone(timedelta(hours=-3))


def _now_iso() -> str:
    return datetime.now(_BRT).isoformat(timespec="seconds")


def ping_host(ip: str, timeout: float = 2.0) -> PingResult:
    is_windows = platform.system().lower().startswith("win")
    if is_windows:
        cmd = ["ping", "-n", "1", "-w", str(int(timeout * 1000)), ip]
    else:
        cmd = ["ping", "-c", "1", "-W", str(max(1, int(timeout))), ip]

    start = time.perf_counter()
    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout + 3,
        )
    except subprocess.TimeoutExpired:
        return PingResult(
            status="offline",
            checked_at=_now_iso(),
            error_message="Timeout ao executar ping.",
        )
    except OSError as exc:
        return PingResult(
            status="offline",
            checked_at=_now_iso(),
            error_message=f"Falha ao executar ping: {exc}",
        )

    latency_ms = int((time.perf_counter() - start) * 1000)
    if completed.returncode == 0:
        return PingResult(
            status="online",
            checked_at=_now_iso(),
            latency_ms=latency_ms,
        )

    msg = (completed.stdout or completed.stderr or "Host nao respondeu ao ping.").strip()
    last_line = msg.splitlines()[-1] if msg else "Host nao respondeu ao ping."
    return PingResult(
        status="offline",
        checked_at=_now_iso(),
        latency_ms=latency_ms,
        error_message=last_line,
    )


def scan_insecure_ports(ip: str, timeout: float = 0.5) -> PortScanResult:
    try:
        socket.getaddrinfo(ip, None)
    except socket.gaierror as exc:
        return PortScanResult(
            ip=ip,
            checked_at=_now_iso(),
            open_ports=[],
            host_responded=False,
            error_message=f"Host nao encontrado: {exc.strerror}",
        )

    open_ports: list[tuple[int, str]] = []
    host_responded = False

    for port, reason in INSECURE_PORTS.items():
        try:
            with socket.create_connection((ip, port), timeout=timeout):
                open_ports.append((port, reason))
                host_responded = True
        except ConnectionRefusedError:
            host_responded = True
        except OSError:
            pass

    error_message = (
        None if host_responded
        else "Host nao respondeu a nenhuma tentativa de conexao. Verifique se o IP existe e esta acessivel."
    )
    return PortScanResult(
        ip=ip,
        checked_at=_now_iso(),
        open_ports=open_ports,
        host_responded=host_responded,
        error_message=error_message,
    )


def lookup_hostname(ip: str) -> tuple[str | None, str | None]:
    """Returns (hostname, error_message)."""
    try:
        hostname, _, _ = socket.gethostbyaddr(ip)
        return hostname, None
    except (socket.herror, socket.gaierror, OSError) as exc:
        return None, str(exc)
