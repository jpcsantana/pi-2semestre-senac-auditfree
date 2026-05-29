from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from pyfiglet import figlet_format
from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.text import Text

from .config import DEFAULT_DB_PATH, DEFAULT_LOG_DIR
from .database import Database
from .logger import AuditLogger
from .network import lookup_hostname
from .service import AuditService


console = Console()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="auditfree",
        description=(
            "Sistema em linha de comando para auditoria de maquinas: "
            "conectividade (ping), varredura de portas inseguras, "
            "auditoria local e validacao de registros DNS."
        ),
    )
    parser.add_argument(
        "--db-path",
        default=str(DEFAULT_DB_PATH),
        help="Caminho do banco SQLite (padrao: data/auditfree.db).",
    )
    parser.add_argument(
        "--log-dir",
        default=str(DEFAULT_LOG_DIR),
        help="Diretorio para logs de auditoria (padrao: logs/).",
    )
    return parser


def _print_header(db_path: Path, log_dir: Path) -> None:
    banner = figlet_format("AUDITFREE", font="big")
    title = Text(banner, style="bold cyan", no_wrap=True)
    subtitle = Text(
        "Auditoria de Maquinas",
        style="bold magenta",
        justify="center",
    )
    info = Text.from_markup(
        f"[dim]Banco:[/dim] [green]{db_path.resolve()}[/green]\n"
        f"[dim]Logs: [/dim] [green]{log_dir.resolve()}[/green]",
        justify="center",
    )
    content = Text("\n").join([title, subtitle, Text(""), info])
    console.print(Panel(Align.center(content), border_style="bright_cyan", padding=(1, 4)))


def _print_menu() -> None:
    table = Table(
        title="[bold yellow]MENU PRINCIPAL[/bold yellow]",
        show_header=True,
        header_style="bold bright_white on blue",
        border_style="bright_blue",
        padding=(0, 2),
    )
    table.add_column("Opcao", justify="center", style="bold yellow", width=8)
    table.add_column("Acao", style="bold bright_white")
    table.add_column("Descricao", style="dim")

    table.add_row("1", "Gerenciar dispositivos", "cadastrar, listar, editar ou excluir maquinas")
    table.add_row("2", "Verificar conectividade", "ping em uma maquina por ID")
    table.add_row("3", "Verificar todas", "ping em todas as maquinas cadastradas")
    table.add_row("4", "Varredura de portas", "escaneia portas inseguras conhecidas")
    table.add_row("5", "Auditoria local", "audita a maquina onde o programa esta rodando")
    table.add_row("6", "Validar registros DNS", "consulta hostname via IP e atualiza cadastro")
    table.add_row("7", "Historico de ping", "mostra verificacoes anteriores")
    table.add_row("[red]0[/red]", "[red]Sair[/red]", "[dim]encerra a aplicacao[/dim]")

    console.print(table)


def _print_manage_menu() -> None:
    table = Table(
        title="[bold yellow]GERENCIAR DISPOSITIVOS[/bold yellow]",
        show_header=True,
        header_style="bold bright_white on blue",
        border_style="bright_blue",
        padding=(0, 2),
    )
    table.add_column("Opcao", justify="center", style="bold yellow", width=8)
    table.add_column("Acao", style="bold bright_white")

    table.add_row("1", "Cadastrar maquina")
    table.add_row("2", "Listar maquinas")
    table.add_row("3", "Editar maquina")
    table.add_row("4", "Excluir maquina")
    table.add_row("[dim]0[/dim]", "[dim]Voltar ao menu principal[/dim]")

    console.print(table)


def _section(title: str) -> None:
    console.rule(f"[bold cyan]{title}[/bold cyan]", style="bright_cyan")


def _info(msg: str) -> None:
    console.print(f"[cyan]>[/cyan] {msg}")


def _ok(msg: str) -> None:
    console.print(f"[bold green][OK][/bold green] {msg}")


def _err(msg: str) -> None:
    console.print(f"[bold red][ERRO][/bold red] {msg}")


def _pause() -> None:
    console.input("\n[dim]Pressione ENTER para continuar...[/dim]")


def _ask_non_empty(prompt: str) -> str:
    value = Prompt.ask(f"[bright_white]{prompt}[/bright_white]", console=console).strip()
    if not value:
        raise ValueError("Campo obrigatorio nao pode ficar vazio.")
    return value


def _ask_optional(prompt: str, default: str = "") -> str:
    return Prompt.ask(
        f"[bright_white]{prompt}[/bright_white]",
        default=default,
        console=console,
    ).strip()


def _ask_int(prompt: str, *, minimum: int, maximum: int, default: int | None = None) -> int:
    default_str = str(default) if default is not None else None
    raw = Prompt.ask(
        f"[bright_white]{prompt}[/bright_white]",
        default=default_str,
        console=console,
    )
    if raw is None or raw == "":
        if default is None:
            raise ValueError("Valor numerico obrigatorio.")
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError("Valor numerico inteiro invalido.") from exc
    if value < minimum or value > maximum:
        raise ValueError(f"Valor deve estar entre {minimum} e {maximum}.")
    return value


def _ask_float(prompt: str, *, minimum: float, default: float) -> float:
    raw = Prompt.ask(
        f"[bright_white]{prompt}[/bright_white]",
        default=str(default),
        console=console,
    )
    if raw is None or raw == "":
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError("Valor numerico invalido.") from exc
    if value <= minimum:
        raise ValueError(f"Valor deve ser maior que {minimum}.")
    return value


def _ask_yes_no(prompt: str, *, default: bool = True) -> bool:
    return Confirm.ask(f"[bright_white]{prompt}[/bright_white]", default=default, console=console)


def _print_devices(devices: list[dict[str, object]]) -> None:
    if not devices:
        _info("Nenhuma maquina cadastrada.")
        return
    table = Table(
        title="[bold cyan]Maquinas cadastradas[/bold cyan]",
        header_style="bold bright_white on blue",
        border_style="bright_blue",
        row_styles=["", "dim"],
    )
    table.add_column("ID", style="bold yellow", justify="right")
    table.add_column("IP", style="green")
    table.add_column("Maquina", style="bright_white")
    table.add_column("AnyDesk", style="magenta")
    table.add_column("Ultimo status", justify="center")
    table.add_column("Ultima verificacao", style="dim")

    for d in devices:
        status = str(d.get("last_status") or "-")
        if status == "online":
            status_cell = "[bold green]online[/bold green]"
        elif status == "offline":
            status_cell = "[bold red]offline[/bold red]"
        else:
            status_cell = "[dim]-[/dim]"
        table.add_row(
            str(d["id"]),
            str(d["ip"]),
            str(d["machine_name"]),
            str(d.get("anydesk_code") or "-"),
            status_cell,
            str(d.get("last_checked_at") or "-"),
        )
    console.print(table)


def _print_history(rows: list[dict[str, object]]) -> None:
    if not rows:
        _info("Nenhum registro de historico encontrado.")
        return
    table = Table(
        title="[bold cyan]Historico de verificacoes[/bold cyan]",
        header_style="bold bright_white on blue",
        border_style="bright_blue",
        row_styles=["", "dim"],
    )
    table.add_column("ID", style="bold yellow", justify="right")
    table.add_column("Maquina", style="bright_white")
    table.add_column("Status", justify="center")
    table.add_column("Checked at", style="dim")
    table.add_column("Latencia", justify="right", style="cyan")
    table.add_column("Erro")

    for r in rows:
        status = str(r["status"])
        status_cell = (
            "[bold green]online[/bold green]"
            if status == "online"
            else "[bold red]offline[/bold red]"
        )
        latency = r["latency_ms"]
        latency_cell = f"{latency} ms" if latency is not None else "-"
        table.add_row(
            str(r["id"]),
            f"{r['machine_name']} ({r['ip']})",
            status_cell,
            str(r["checked_at"]),
            latency_cell,
            str(r["error_message"] or "-"),
        )
    console.print(table)


def _do_add_device(service: AuditService) -> None:
    _section("Cadastro de maquina")
    ip = _ask_non_empty("IP ou hostname")

    hostname_found: str | None = None
    with console.status("[cyan]Consultando DNS para o IP informado...[/cyan]", spinner="dots"):
        hostname_found, _ = lookup_hostname(ip)

    if hostname_found:
        console.print(
            f"[dim]Hostname encontrado via DNS:[/dim] [bold yellow]{hostname_found}[/bold yellow]"
        )
        use_hostname = _ask_yes_no(f"Usar '{hostname_found}' como nome da maquina?", default=True)
        machine_name = hostname_found if use_hostname else _ask_non_empty("Nome da maquina")
    else:
        machine_name = _ask_non_empty("Nome da maquina")

    anydesk_code: str | None = None
    if _ask_yes_no("Deseja cadastrar o codigo AnyDesk dessa maquina?", default=False):
        anydesk_code = _ask_non_empty("Codigo AnyDesk")

    device_id = service.register_device(ip=ip, machine_name=machine_name, anydesk_code=anydesk_code)
    _ok(f"Maquina cadastrada com sucesso. ID gerado: [bold yellow]{device_id}[/bold yellow]")


def _do_edit_device(service: AuditService) -> None:
    _section("Editar maquina")
    _print_devices(service.list_devices())
    device_id = _ask_int("ID da maquina a editar", minimum=1, maximum=2147483647)
    device = service.get_device(device_id)

    console.print(
        f"\n[dim]Valores atuais — pressione ENTER para manter:[/dim]\n"
        f"  IP:      [green]{device['ip']}[/green]\n"
        f"  Nome:    [bright_white]{device['machine_name']}[/bright_white]\n"
        f"  AnyDesk: [magenta]{device.get('anydesk_code') or '-'}[/magenta]\n"
    )

    new_ip = _ask_optional(f"Novo IP", default=str(device["ip"])) or str(device["ip"])
    new_name = _ask_optional(f"Novo nome", default=str(device["machine_name"])) or str(device["machine_name"])

    current_anydesk = str(device.get("anydesk_code") or "")
    raw_anydesk = _ask_optional("Novo codigo AnyDesk (vazio para remover)", default=current_anydesk)
    new_anydesk: str | None = raw_anydesk if raw_anydesk else None

    service.update_device(device_id, new_ip, new_name, new_anydesk)
    _ok(f"Maquina [bold yellow]#{device_id}[/bold yellow] atualizada com sucesso.")


def _do_delete_device(service: AuditService) -> None:
    _section("Excluir maquina")
    _print_devices(service.list_devices())
    device_id = _ask_int("ID da maquina a excluir", minimum=1, maximum=2147483647)
    device = service.get_device(device_id)

    console.print(
        f"\n[bold red]Atencao:[/bold red] isso removera a maquina "
        f"[bold]{device['machine_name']} ({device['ip']})[/bold] "
        f"e todo o seu historico de verificacoes."
    )
    if not _ask_yes_no("Confirmar exclusao?", default=False):
        _info("Operacao cancelada.")
        return

    service.delete_device(device_id)
    _ok(f"Maquina [bold yellow]#{device_id}[/bold yellow] excluida com sucesso.")


def _run_manage_devices(service: AuditService) -> None:
    while True:
        console.clear()
        _print_manage_menu()

        sub = Prompt.ask(
            "\n[bold yellow]Opcao[/bold yellow]",
            choices=["0", "1", "2", "3", "4"],
            show_choices=False,
            console=console,
        ).strip()

        if sub == "0":
            return

        try:
            if sub == "1":
                _do_add_device(service)
            elif sub == "2":
                _section("Lista de maquinas")
                _print_devices(service.list_devices())
            elif sub == "3":
                _do_edit_device(service)
            elif sub == "4":
                _do_delete_device(service)
        except ValueError as exc:
            _err(str(exc))

        _pause()


def _show_ping_result(device: dict[str, object], result) -> None:
    status = result.status
    color = "green" if status == "online" else "red"
    panel = Panel.fit(
        Text.from_markup(
            f"[bold {color}]{status.upper()}[/bold {color}]\n"
            f"[dim]Verificado em:[/dim] {result.checked_at}\n"
            f"[dim]Latencia:    [/dim] "
            f"{result.latency_ms if result.latency_ms is not None else '-'} ms\n"
            f"[dim]Detalhe:     [/dim] {result.error_message or '-'}"
        ),
        title=f"[bold cyan]{device['machine_name']} ({device['ip']})[/bold cyan]",
        border_style=color,
        padding=(1, 2),
    )
    console.print(panel)


def _run_check_device(service: AuditService) -> None:
    _section("Verificacao de conectividade (ping)")
    device_id = _ask_int("ID da maquina", minimum=1, maximum=2147483647)
    timeout = _ask_float("Timeout em segundos", minimum=0.0, default=2.0)
    with console.status("[cyan]Executando ping...[/cyan]", spinner="dots"):
        report = service.check_device(device_id=device_id, timeout=timeout)
    _show_ping_result(report["device"], report["result"])


def _run_check_all(service: AuditService) -> None:
    _section("Verificacao de conectividade em todas as maquinas")
    timeout = _ask_float("Timeout em segundos", minimum=0.0, default=2.0)
    with console.status("[cyan]Executando pings em lote...[/cyan]", spinner="dots"):
        reports = service.check_all(timeout=timeout)
    if not reports:
        _info("Nenhuma maquina cadastrada para monitorar.")
        return

    table = Table(
        title="[bold cyan]Resultado da verificacao em lote[/bold cyan]",
        header_style="bold bright_white on blue",
        border_style="bright_blue",
    )
    table.add_column("ID", style="bold yellow", justify="right")
    table.add_column("Maquina", style="bright_white")
    table.add_column("IP", style="green")
    table.add_column("Status", justify="center")
    table.add_column("Latencia", justify="right", style="cyan")
    table.add_column("Erro", style="red")

    online = offline = 0
    for report in reports:
        d = report["device"]
        r = report["result"]
        if r.status == "online":
            online += 1
            status_cell = "[bold green]online[/bold green]"
        else:
            offline += 1
            status_cell = "[bold red]offline[/bold red]"
        latency = f"{r.latency_ms} ms" if r.latency_ms is not None else "-"
        table.add_row(
            str(d["id"]), str(d["machine_name"]), str(d["ip"]),
            status_cell, latency, str(r.error_message or "-"),
        )
    console.print(table)
    console.print(
        f"[bold]Resumo:[/bold] [green]{online} online[/green] | [red]{offline} offline[/red]"
    )


def _run_port_scan(service: AuditService) -> None:
    _section("Varredura de portas inseguras")
    device_id = _ask_int("ID da maquina", minimum=1, maximum=2147483647)
    timeout = _ask_float("Timeout por porta em segundos", minimum=0.0, default=0.5)

    with console.status("[cyan]Escaneando portas inseguras...[/cyan]", spinner="dots"):
        report = service.scan_ports(device_id=device_id, timeout=timeout)
    device = report["device"]
    scan = report["scan"]
    console.print(
        f"\n[bold]Alvo:[/bold] [cyan]{device['machine_name']} ({device['ip']})[/cyan] "
        f"[dim]| em {scan.checked_at}[/dim]"
    )

    if not scan.host_responded:
        console.print(
            Panel.fit(
                f"[bold red]Host inacessivel.[/bold red]\n"
                f"[dim]{scan.error_message or ''}[/dim]",
                border_style="red",
                padding=(1, 2),
            )
        )
        return

    if not scan.open_ports:
        console.print(
            Panel.fit(
                "[bold green]Nenhuma porta insegura conhecida foi detectada como aberta.[/bold green]",
                border_style="green",
                padding=(1, 2),
            )
        )
        return

    table = Table(
        title="[bold red]Portas inseguras ABERTAS[/bold red]",
        header_style="bold bright_white on red",
        border_style="red",
    )
    table.add_column("Porta", style="bold yellow", justify="right")
    table.add_column("Motivo / Risco", style="bright_white")
    for port, reason in scan.open_ports:
        table.add_row(str(port), reason)
    console.print(table)


def _run_local_audit(service: AuditService) -> None:
    _section("Auditoria da maquina local")
    _info("Coletando informacoes da maquina onde o programa esta rodando...")

    with console.status("[cyan]Executando auditoria local...[/cyan]", spinner="dots"):
        report = service.run_local_audit()

    result = report["result"]
    log_path = report["log_path"]
    device = report["device"]

    def _v(val: object, unit: str = "") -> str:
        return f"{val}{unit}" if val is not None else "[dim]-[/dim]"

    console.print(
        Panel(
            Text.from_markup(
                f"[bold green]Auditoria concluida[/bold green] "
                f"[dim](device_id={device['id']})[/dim]\n\n"
                f"[dim]Hostname:     [/dim] [yellow]{result.hostname}[/yellow]\n"
                f"[dim]Sistema:      [/dim] {result.os_info}\n"
                f"[dim]CPUs:         [/dim] {_v(result.cpu_count)}\n"
                f"[dim]Freq. CPU:    [/dim] {_v(result.cpu_freq_mhz, ' MHz')}\n"
                f"[dim]RAM total:    [/dim] {_v(result.ram_total_mb, ' MB')}\n"
                f"[dim]RAM usada:    [/dim] {_v(result.ram_used_mb, ' MB')}\n"
                f"[dim]Disco total:  [/dim] {_v(result.disk_total_gb, ' GB')}\n"
                f"[dim]Disco usado:  [/dim] {_v(result.disk_used_gb, ' GB')}\n"
                f"[dim]Usuarios:     [/dim] "
                f"{', '.join(result.active_users) if result.active_users else '-'}\n"
                f"[dim]Log salvo em: [/dim] [green]{log_path}[/green]"
            ),
            title="[bold cyan]Maquina Local[/bold cyan]",
            border_style="bright_cyan",
            padding=(1, 2),
        )
    )

    if result.network_interfaces:
        table = Table(
            title="[bold cyan]Interfaces de rede (IPv4)[/bold cyan]",
            header_style="bold bright_white on blue",
            border_style="bright_blue",
        )
        table.add_column("Interface", style="yellow")
        table.add_column("IP", style="green")
        for iface in result.network_interfaces:
            table.add_row(str(iface["interface"]), str(iface["ip"]))
        console.print(table)

    if result.top_processes:
        table = Table(
            title="[bold cyan]Top 10 processos por CPU[/bold cyan]",
            header_style="bold bright_white on blue",
            border_style="bright_blue",
        )
        table.add_column("PID", style="bold yellow", justify="right")
        table.add_column("CPU%", justify="right", style="red")
        table.add_column("MEM%", justify="right", style="magenta")
        table.add_column("Nome", style="bright_white")
        for p in result.top_processes:
            table.add_row(
                str(p.get("pid", "-")),
                f"{p.get('cpu_percent', 0):.1f}",
                f"{p.get('memory_percent', 0):.1f}",
                str(p.get("name", "-")),
            )
        console.print(table)


def _run_dns_validate(service: AuditService) -> None:
    _section("Validacao de registros DNS")
    device_id = _ask_int("ID da maquina", minimum=1, maximum=2147483647)

    with console.status("[cyan]Consultando DNS (gethostbyaddr)...[/cyan]", spinner="dots"):
        report = service.dns_validate(device_id=device_id)

    device = report["device"]
    hostname = report["hostname"]
    error = report["error"]

    console.print(
        f"\n[bold]Maquina:[/bold] [cyan]{device['machine_name']} ({device['ip']})[/cyan]"
    )

    if error:
        console.print(
            Panel.fit(
                f"[bold red]Nao foi possivel resolver o hostname.[/bold red]\n"
                f"[dim]{error}[/dim]",
                border_style="red",
                padding=(1, 2),
            )
        )
        return

    console.print(
        Panel.fit(
            Text.from_markup(
                f"[bold green]Hostname encontrado:[/bold green] "
                f"[bold yellow]{hostname}[/bold yellow]\n"
                f"[dim]Nome atual no cadastro:[/dim] {device['machine_name']}"
            ),
            border_style="green",
            padding=(1, 2),
        )
    )

    if hostname != device["machine_name"]:
        if _ask_yes_no(f"Substituir nome cadastrado por '{hostname}'?", default=False):
            service.update_device_name(device_id, hostname)
            _ok(f"Nome atualizado para: [bold yellow]{hostname}[/bold yellow]")
    else:
        _info("O nome cadastrado ja coincide com o hostname encontrado.")


def _run_history(service: AuditService) -> None:
    _section("Consulta de historico de ping")
    raw_id = Prompt.ask(
        "[bright_white]Filtrar por ID da maquina (vazio para todas)[/bright_white]",
        default="",
        console=console,
    ).strip()
    device_id: int | None = None
    if raw_id:
        try:
            device_id = int(raw_id)
        except ValueError as exc:
            raise ValueError("ID do filtro deve ser numerico.") from exc
        if device_id <= 0:
            raise ValueError("ID do filtro deve ser maior que zero.")

    limit = _ask_int("Limite de registros", minimum=1, maximum=1000, default=20)
    _print_history(service.get_history(device_id=device_id, limit=limit))


def run(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    db = Database(Path(args.db_path))
    db.init_db()
    logger = AuditLogger(Path(args.log_dir))
    service = AuditService(db, logger)

    try:
        while True:
            console.clear()
            _print_header(Path(args.db_path), Path(args.log_dir))
            _print_menu()

            option = Prompt.ask(
                "\n[bold yellow]Opcao[/bold yellow]",
                choices=["0", "1", "2", "3", "4", "5", "6", "7"],
                show_choices=False,
                console=console,
            ).strip()

            if option == "0":
                console.print("\n[bold magenta]Encerrando aplicacao...[/bold magenta]")
                return 0

            try:
                if option == "1":
                    _run_manage_devices(service)
                elif option == "2":
                    _run_check_device(service)
                elif option == "3":
                    _run_check_all(service)
                elif option == "4":
                    _run_port_scan(service)
                elif option == "5":
                    _run_local_audit(service)
                elif option == "6":
                    _run_dns_validate(service)
                elif option == "7":
                    _run_history(service)
            except ValueError as exc:
                _err(str(exc))

            _pause()
    except KeyboardInterrupt:
        console.print("\n[bold magenta]Execucao interrompida pelo usuario.[/bold magenta]")
        return 130


if __name__ == "__main__":
    raise SystemExit(run())
