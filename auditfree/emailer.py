from __future__ import annotations

from email.message import EmailMessage
import smtplib

from .config import SMTPSettings
from .network import AvailabilityResult


def _auth_and_send(server: smtplib.SMTP, message: EmailMessage, settings: SMTPSettings) -> None:
    if settings.username and settings.password:
        server.login(settings.username, settings.password)
    server.send_message(message)


def send_offline_alert(
    device: dict[str, object],
    result: AvailabilityResult,
    settings: SMTPSettings,
) -> tuple[bool, str]:
    if not settings.is_configured:
        return False, "SMTP nao configurado. Defina variaveis AUDITFREE_SMTP_* para habilitar alertas."

    subject = (
        f"[ALERTA AUDITFREE] Dispositivo offline: {device['machine_name']} "
        f"(ID {device['id']})"
    )
    message = EmailMessage()
    message["From"] = settings.from_email
    message["To"] = str(device["notify_email"])
    message["Subject"] = subject
    message.set_content(
        "\n".join(
            [
                "Foi detectada uma falha de comunicacao com o dispositivo monitorado.",
                "",
                f"ID: {device['id']}",
                f"Nome: {device['machine_name']}",
                f"IP: {device['ip']}",
                f"Porta: {device['port']}",
                f"Horario da verificacao: {result.checked_at}",
                f"Mensagem de erro: {result.error_message or 'Nao informado'}",
                "",
                "Este e-mail foi enviado automaticamente pelo AuditFree.",
            ]
        )
    )

    try:
        if settings.use_ssl:
            with smtplib.SMTP_SSL(settings.host, settings.port, timeout=15) as server:
                _auth_and_send(server, message, settings)
        else:
            with smtplib.SMTP(settings.host, settings.port, timeout=15) as server:
                server.ehlo()
                if settings.use_tls:
                    server.starttls()
                    server.ehlo()
                _auth_and_send(server, message, settings)
        return True, "Alerta enviado com sucesso."
    except Exception as exc:  # pragma: no cover - depends on external SMTP server
        return False, f"Falha ao enviar alerta por e-mail: {exc}"
