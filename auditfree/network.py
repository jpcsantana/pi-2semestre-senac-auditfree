from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import socket
import time


@dataclass(frozen=True)
class AvailabilityResult:
    status: str
    checked_at: str
    latency_ms: int | None = None
    error_message: str | None = None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def check_availability(ip: str, port: int, timeout: float = 2.0) -> AvailabilityResult:
    start = time.perf_counter()
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            latency_ms = int((time.perf_counter() - start) * 1000)
            return AvailabilityResult(
                status="online",
                checked_at=_utc_now_iso(),
                latency_ms=latency_ms,
            )
    except OSError as exc:
        return AvailabilityResult(
            status="offline",
            checked_at=_utc_now_iso(),
            error_message=str(exc),
        )
