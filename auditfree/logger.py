from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from .config import DEFAULT_LOG_DIR


_BRT = timezone(timedelta(hours=-3))


def _now_iso() -> str:
    return datetime.now(_BRT).isoformat(timespec="seconds")


def _safe_name(name: str) -> str:
    return "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in name) or "machine"


class AuditLogger:
    def __init__(self, log_dir: Path = DEFAULT_LOG_DIR) -> None:
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.errors_file = self.log_dir / "errors.log"
        self.audits_file = self.log_dir / "audits.log"
        self.local_audit_file = self.log_dir / "local_audit.log"

    def log_audit(self, audit_type: str, target: str, summary: str) -> None:
        line = f"[{_now_iso()}] {audit_type} | alvo={target} | {summary}\n"
        with self.audits_file.open("a", encoding="utf-8") as fh:
            fh.write(line)

    def log_error(self, audit_type: str, target: str, error: str) -> None:
        line = f"[{_now_iso()}] {audit_type} | alvo={target} | ERRO: {error}\n"
        with self.errors_file.open("a", encoding="utf-8") as fh:
            fh.write(line)

    def save_local_audit(self, content: str) -> Path:
        self.local_audit_file.write_text(content, encoding="utf-8")
        return self.local_audit_file
