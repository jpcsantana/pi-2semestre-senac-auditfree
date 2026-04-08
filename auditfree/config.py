from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

DEFAULT_DB_PATH = Path("data/auditfree.db")


def _to_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on", "sim"}


@dataclass(frozen=True)
class SMTPSettings:
    host: str
    port: int
    from_email: str
    username: str | None = None
    password: str | None = None
    use_tls: bool = True
    use_ssl: bool = False

    @property
    def is_configured(self) -> bool:
        if not self.host or not self.from_email:
            return False
        if self.use_ssl and self.use_tls:
            return False
        if (self.username and not self.password) or (self.password and not self.username):
            return False
        return True

    @classmethod
    def from_env(cls) -> "SMTPSettings":
        host = os.getenv("AUDITFREE_SMTP_HOST", "").strip()
        from_email = os.getenv("AUDITFREE_SMTP_FROM", "").strip()
        username = os.getenv("AUDITFREE_SMTP_USER")
        password = os.getenv("AUDITFREE_SMTP_PASS")

        raw_port = os.getenv("AUDITFREE_SMTP_PORT", "587")
        try:
            port = int(raw_port)
        except ValueError:
            port = 587

        use_tls = _to_bool(os.getenv("AUDITFREE_SMTP_USE_TLS"), default=True)
        use_ssl = _to_bool(os.getenv("AUDITFREE_SMTP_USE_SSL"), default=False)

        return cls(
            host=host,
            port=port,
            from_email=from_email,
            username=username,
            password=password,
            use_tls=use_tls,
            use_ssl=use_ssl,
        )
