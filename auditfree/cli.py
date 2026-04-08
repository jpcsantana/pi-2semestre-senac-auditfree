from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Sequence

from .config import DEFAULT_DB_PATH, SMTPSettings
from .database import Database
from .service import AuditService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="auditfree",
        description=(
            "Sistema em linha de comando para cadastro de dispositivos, verificacao de "
            "disponibilidade com Socket e envio de alerta por e-mail."
        ),
    )
    parser.add_argument(
        "--db-path",
        default=str(DEFAULT_DB_PATH),
        help="Caminho do banco SQLite (padrao: data/auditfree.db).",
    )

    return parser


def _clear_console() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def _frame_line(width: int = 78) -> str:
    return "+" + ("-" * (width - 2)) + "+"


def _frame_text(text: str, width: int = 78) -> str:
    content_width = width - 4
    safe = text[:content_width]
    return "| " + safe.ljust(content_width) + " |"


def _print_header(db_path: Path) -> None:
    print(_frame_line())
    print(_frame_text("AUDITFREE - Auditoria e Disponibilidade de Rede"))
    print(_frame_text("Monitoramento com Socket, SQLite e alerta por e-mail"))
    print(_frame_line())
    print(f"Banco em uso: {db_path.resolve()}")


def _print_running(message: str) -> None:
    print(f"\n[....] {message}")


def _pause() -> None:
    input("\nPressione ENTER para voltar ao menu...")


def _ask_non_empty(prompt: str) -> str:
    value = input(prompt).strip()
    if not value:
        raise ValueError("Campo obrigatorio nao pode ficar vazio.")
    return value


def _ask_int(prompt: str, *, minimum: int, maximum: int, default: int | None = None) -> int:
    raw = input(prompt).strip()
    if raw == "" and default is not None:
        value = default
    else:
        try:
            value = int(raw)
        except ValueError as exc:
            raise ValueError("Valor numerico inteiro invalido.") from exc

    if value < minimum or value > maximum:
        raise ValueError(f"Valor deve estar entre {minimum} e {maximum}.")
    return value


def _ask_float(prompt: str, *, minimum: float, default: float) -> float:
    raw = input(prompt).strip()
    if raw == "":
        value = default
    else:
        try:
            value = float(raw)
        except ValueError as exc:
            raise ValueError("Valor numerico invalido.") from exc

    if value <= minimum:
        raise ValueError(f"Valor deve ser maior que {minimum}.")
    return value


def _ask_yes_no(prompt: str, *, default: bool = True) -> bool:
    raw = input(prompt).strip().lower()
    if raw == "":
        return default
    if raw in {"s", "sim", "y", "yes", "1", "true"}:
        return True
    if raw in {"n", "nao", "no", "0", "false"}:
        return False
    raise ValueError("Resposta invalida. Use s/sim ou n/nao.")


def _print_menu() -> None:
    print()
    print("Selecione uma opcao:")
    print("1) Inicializar banco           -> cria/valida tabelas e integridade")
    print("2) Cadastrar dispositivo       -> registra IP, nome, e-mail e porta")
    print("3) Listar dispositivos         -> exibe dispositivos e ultimo status")
    print("4) Verificar um dispositivo    -> testa conectividade de um ID")
    print("5) Verificar todos             -> testa todos os dispositivos")
    print("6) Consultar historico         -> lista resultados de verificacao")
    print("0) Sair")


def _print_devices(devices: list[dict[str, object]]) -> None:
    if not devices:
        print("Nenhum dispositivo cadastrado.")
        return

    print("ID   IP                 PORTA  NOME                    ULTIMO_STATUS  ULTIMA_VERIFICACAO")
    print("-" * 100)
    for device in devices:
        print(
            f"{str(device['id']):<4} "
            f"{str(device['ip']):<17}  "
            f"{str(device['port']):<5}  "
            f"{str(device['machine_name'])[:22]:<22}  "
            f"{str(device.get('last_status') or '-'): <13}  "
            f"{str(device.get('last_checked_at') or '-')}"
        )


def _print_history(rows: list[dict[str, object]]) -> None:
    if not rows:
        print("Nenhum registro de historico encontrado.")
        return

    print("ID  DISPOSITIVO    STATUS   CHECKED_AT                  LATENCIA_MS  ERRO")
    print("-" * 105)
    for row in rows:
        print(
            f"{str(row['id']):<3} "
            f"{str(row['device_id']):<12}  "
            f"{str(row['status']):<7}  "
            f"{str(row['checked_at']):<26}  "
            f"{str(row['latency_ms'] if row['latency_ms'] is not None else '-'): <11}  "
            f"{str(row['error_message'] or '-')[:35]}"
        )


def _run_add_device(service: AuditService) -> None:
    print("Cadastro de dispositivo")
    ip = _ask_non_empty("IP ou hostname: ")
    machine_name = _ask_non_empty("Nome da maquina: ")
    notify_email = _ask_non_empty("E-mail para notificacao: ")
    port = _ask_int("Porta TCP [80]: ", minimum=1, maximum=65535, default=80)

    device_id = service.register_device(
        ip=ip,
        machine_name=machine_name,
        notify_email=notify_email,
        port=port,
    )
    print(f"Dispositivo cadastrado com sucesso. ID gerado: {device_id}")


def _run_check_device(service: AuditService) -> None:
    print("Verificacao de dispositivo")
    device_id = _ask_int("ID do dispositivo: ", minimum=1, maximum=2147483647)
    timeout = _ask_float("Timeout em segundos [2.0]: ", minimum=0.0, default=2.0)
    send_alert = _ask_yes_no("Enviar alerta por e-mail se offline? [S/n]: ", default=True)

    report = service.check_device(
        device_id=device_id,
        timeout=timeout,
        send_alert=send_alert,
    )
    device = report["device"]
    result = report["result"]
    print(
        f"Dispositivo ID {device['id']} ({device['machine_name']}): "
        f"{result.status.upper()} em {result.checked_at}"
    )
    if result.latency_ms is not None:
        print(f"Latencia: {result.latency_ms} ms")
    if result.error_message:
        print(f"Erro de conectividade: {result.error_message}")
    if result.status == "offline" and send_alert:
        print(f"Status do alerta: {report['alert_message']}")


def _run_check_all(service: AuditService) -> None:
    print("Verificacao de todos os dispositivos")
    timeout = _ask_float("Timeout em segundos [2.0]: ", minimum=0.0, default=2.0)
    send_alert = _ask_yes_no("Enviar alerta por e-mail se offline? [S/n]: ", default=True)

    reports = service.check_all(timeout=timeout, send_alert=send_alert)
    if not reports:
        print("Nenhum dispositivo cadastrado para monitorar.")
        return

    online = 0
    offline = 0
    for report in reports:
        device = report["device"]
        result = report["result"]
        if result.status == "online":
            online += 1
        else:
            offline += 1

        line = (
            f"ID {device['id']} ({device['ip']}:{device['port']}) -> "
            f"{result.status.upper()}"
        )
        if result.latency_ms is not None:
            line += f" [{result.latency_ms} ms]"
        if result.error_message:
            line += f" [erro: {result.error_message}]"
        print(line)
        if result.status == "offline" and send_alert:
            print(f"  alerta: {report['alert_message']}")

    print(f"Resumo: {online} online, {offline} offline")


def _run_history(service: AuditService) -> None:
    print("Consulta de historico")
    raw_id = input("Filtrar por ID do dispositivo (vazio para todos): ").strip()
    if raw_id:
        try:
            device_id = int(raw_id)
        except ValueError as exc:
            raise ValueError("ID do filtro deve ser numerico.") from exc
        if device_id <= 0:
            raise ValueError("ID do filtro deve ser maior que zero.")
    else:
        device_id = None

    limit = _ask_int("Limite de registros [20]: ", minimum=1, maximum=1000, default=20)
    rows = service.get_history(device_id=device_id, limit=limit)
    _print_history(rows)


def run(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    db = Database(Path(args.db_path))
    db.init_db()
    service = AuditService(db, SMTPSettings.from_env())

    try:
        while True:
            _clear_console()
            _print_header(Path(args.db_path))
            _print_menu()

            option = input("\nOpcao: ").strip()

            if option == "0":
                print("\nEncerrando aplicacao...")
                return 0

            try:
                if option == "1":
                    _print_running("Inicializando estrutura do banco...")
                    db.init_db()
                    print("[OK] Banco inicializado e validado com sucesso.")
                elif option == "2":
                    _print_running("Registrando novo dispositivo...")
                    _run_add_device(service)
                    print("[OK] Cadastro concluido.")
                elif option == "3":
                    _print_running("Consultando lista de dispositivos...")
                    _print_devices(service.list_devices())
                    print("[OK] Consulta concluida.")
                elif option == "4":
                    _print_running("Executando verificacao de dispositivo...")
                    _run_check_device(service)
                    print("[OK] Verificacao concluida.")
                elif option == "5":
                    _print_running("Executando verificacao em lote...")
                    _run_check_all(service)
                    print("[OK] Verificacao em lote concluida.")
                elif option == "6":
                    _print_running("Consultando historico de verificacoes...")
                    _run_history(service)
                    print("[OK] Historico exibido.")
                else:
                    raise ValueError("Opcao de menu invalida.")
            except ValueError as exc:
                print(f"[ERRO] {exc}")

            _pause()
    except KeyboardInterrupt:
        print("\nExecucao interrompida pelo usuario.")
        return 130


if __name__ == "__main__":
    raise SystemExit(run())
