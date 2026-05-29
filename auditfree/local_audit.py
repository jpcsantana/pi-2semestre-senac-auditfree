from __future__ import annotations

import os
import platform
import socket
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone

try:
    import psutil
    _HAS_PSUTIL = True
except ImportError:
    _HAS_PSUTIL = False

_DISK_ROOT = "C:\\" if sys.platform == "win32" else "/"


@dataclass
class LocalAuditResult:
    captured_at: str
    hostname: str
    os_info: str
    cpu_count: int | None
    cpu_freq_mhz: float | None
    ram_total_mb: int | None
    ram_used_mb: int | None
    disk_total_gb: float | None
    disk_used_gb: float | None
    active_users: list[str] = field(default_factory=list)
    top_processes: list[dict] = field(default_factory=list)
    network_interfaces: list[dict] = field(default_factory=list)


def collect_local_audit() -> LocalAuditResult:
    captured_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    hostname = socket.gethostname()
    os_info = f"{platform.system()} {platform.release()} ({platform.machine()})"

    cpu_count: int | None = os.cpu_count()
    cpu_freq_mhz: float | None = None
    ram_total_mb: int | None = None
    ram_used_mb: int | None = None
    disk_total_gb: float | None = None
    disk_used_gb: float | None = None
    active_users: list[str] = []
    top_processes: list[dict] = []
    network_interfaces: list[dict] = []

    if _HAS_PSUTIL:
        freq = psutil.cpu_freq()
        if freq:
            cpu_freq_mhz = round(freq.current, 1)

        mem = psutil.virtual_memory()
        ram_total_mb = mem.total >> 20
        ram_used_mb = mem.used >> 20

        try:
            disk = psutil.disk_usage(_DISK_ROOT)
            disk_total_gb = round(disk.total / 2**30, 2)
            disk_used_gb = round(disk.used / 2**30, 2)
        except Exception:
            pass

        try:
            active_users = sorted({u.name for u in psutil.users()})
        except Exception:
            pass

        try:
            procs: list[dict] = []
            for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
                try:
                    procs.append(p.info)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            top_processes = sorted(
                procs, key=lambda x: x.get("cpu_percent") or 0.0, reverse=True
            )[:10]
        except Exception:
            pass

        try:
            for iface, addrs in psutil.net_if_addrs().items():
                for addr in addrs:
                    if addr.family == socket.AF_INET:
                        network_interfaces.append({"interface": iface, "ip": addr.address})
        except Exception:
            pass

    return LocalAuditResult(
        captured_at=captured_at,
        hostname=hostname,
        os_info=os_info,
        cpu_count=cpu_count,
        cpu_freq_mhz=cpu_freq_mhz,
        ram_total_mb=ram_total_mb,
        ram_used_mb=ram_used_mb,
        disk_total_gb=disk_total_gb,
        disk_used_gb=disk_used_gb,
        active_users=active_users,
        top_processes=top_processes,
        network_interfaces=network_interfaces,
    )
