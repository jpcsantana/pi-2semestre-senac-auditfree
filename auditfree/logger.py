from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .config import DEFAULT_LOG_DIR


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _safe_name(name: str) -> str:
    return "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in name) or "machine"


class AuditLogger:
    def __init__(self, log_dir: Path = DEFAULT_LOG_DIR) -> None:
        self.log_dir = Path(log_dir)
        self.programs_dir = self.log_dir / "programs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.programs_dir.mkdir(parents=True, exist_ok=True)
        self.errors_file = self.log_dir / "errors.log"
        self.audits_file = self.log_dir / "audits.log"

    def log_audit(self, audit_type: str, target: str, summary: str) -> None:
        line = f"[{_now_iso()}] {audit_type} | alvo={target} | {summary}\n"
        with self.audits_file.open("a", encoding="utf-8") as fh:
            fh.write(line)

    def log_error(self, audit_type: str, target: str, error: str) -> None:
        line = f"[{_now_iso()}] {audit_type} | alvo={target} | ERRO: {error}\n"
        with self.errors_file.open("a", encoding="utf-8") as fh:
            fh.write(line)

    def save_programs(self, machine_name: str, content: str, header: str = "") -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = self.programs_dir / f"{_safe_name(machine_name)}_{timestamp}.txt"
        body = (header + "\n\n" if header else "") + content + "\n"
        path.write_text(body, encoding="utf-8")
        return path
