from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

try:
    import paramiko
except ImportError:
    paramiko = None  # type: ignore[assignment]


PACKAGE_COMMANDS = [
    ("dpkg", "dpkg-query -W -f='${Package} ${Version}\\n'"),
    ("rpm", "rpm -qa --queryformat '%{NAME} %{VERSION}\\n'"),
    ("pacman", "pacman -Q"),
    ("apk", "apk info -v"),
]


@dataclass(frozen=True)
class SSHAnalysisResult:
    checked_at: str
    success: bool
    distro_info: str = ""
    package_manager: str = ""
    programs: str = ""
    error_message: str = ""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _exec(client, command: str, timeout: float = 20.0) -> tuple[int, str, str]:
    _, stdout, stderr = client.exec_command(command, timeout=timeout)
    code = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    return code, out, err


def analyze_installed_programs(
    host: str,
    username: str,
    password: str,
    port: int = 22,
    timeout: float = 10.0,
) -> SSHAnalysisResult:
    if paramiko is None:
        return SSHAnalysisResult(
            checked_at=_utc_now_iso(),
            success=False,
            error_message="Modulo paramiko nao instalado. Execute: pip install paramiko",
        )

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            hostname=host,
            port=port,
            username=username,
            password=password,
            timeout=timeout,
            allow_agent=False,
            look_for_keys=False,
        )
    except Exception as exc:
        return SSHAnalysisResult(
            checked_at=_utc_now_iso(),
            success=False,
            error_message=f"Falha ao conectar via SSH: {exc}",
        )

    try:
        _, distro_out, _ = _exec(client, "cat /etc/os-release 2>/dev/null || uname -a")
        distro_info = distro_out.strip()

        for name, command in PACKAGE_COMMANDS:
            code, out, _ = _exec(client, command)
            if code == 0 and out.strip():
                return SSHAnalysisResult(
                    checked_at=_utc_now_iso(),
                    success=True,
                    distro_info=distro_info,
                    package_manager=name,
                    programs=out.strip(),
                )

        return SSHAnalysisResult(
            checked_at=_utc_now_iso(),
            success=False,
            distro_info=distro_info,
            error_message="Nenhum gerenciador de pacotes conhecido foi detectado.",
        )
    finally:
        client.close()
