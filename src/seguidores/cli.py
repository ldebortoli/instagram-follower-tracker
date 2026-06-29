from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import asdict
from datetime import datetime
from getpass import getpass
from logging.handlers import RotatingFileHandler
from pathlib import Path

from seguidores import __version__, scheduler
from seguidores.app import Tracker
from seguidores.collector import CollectionError, ExportCollector, InstagramCollector
from seguidores.config import (
    AccountConfig,
    ConfigError,
    load_config,
    parse_time,
    save_config,
)
from seguidores.locking import AlreadyRunningError
from seguidores.notifier import (
    NotificationError,
    delete_telegram_token,
    get_telegram_token,
    notify,
    notify_automatic_failure,
    send_telegram,
    set_telegram_token,
)
from seguidores.paths import AppPaths, app_paths
from seguidores.report import format_report
from seguidores.scheduler import SchedulerError


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        prog="seguidores",
        description="Monitor local de seguidores de Instagram.",
    )
    root.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = root.add_subparsers(dest="command", required=True)

    commands.add_parser("init", help="Crea una configuración vacía.")
    setup = commands.add_parser("setup", help="Abre la configuración inicial.")
    setup.add_argument(
        "--terminal", action="store_true", help="Usa el asistente de texto en vez de la ventana."
    )
    commands.add_parser("gui", help="Abre la interfaz gráfica.")

    account = commands.add_parser("account", help="Administra cuentas.")
    account_commands = account.add_subparsers(dest="account_command", required=True)
    add = account_commands.add_parser("add", help="Agrega o actualiza una cuenta.")
    add.add_argument("name", help="Nombre local, por ejemplo 'personal'.")
    add.add_argument("--username", required=True, help="Usuario de Instagram a observar.")
    add.add_argument(
        "--login-username",
        help="Usuario usado para iniciar sesión (por defecto, el observado).",
    )
    account_commands.add_parser("list", help="Lista las cuentas.")
    remove = account_commands.add_parser("remove", help="Elimina una cuenta de la configuración.")
    remove.add_argument("name")
    toggle = account_commands.add_parser("enable", help="Activa una cuenta.")
    toggle.add_argument("name")
    toggle = account_commands.add_parser("disable", help="Desactiva una cuenta.")
    toggle.add_argument("name")

    auth = commands.add_parser("auth", help="Administra sesiones de Instagram.")
    auth_commands = auth.add_subparsers(dest="auth_command", required=True)
    login = auth_commands.add_parser("login", help="Inicia sesión y guarda sólo la cookie local.")
    login.add_argument("account")
    browser_login = auth_commands.add_parser(
        "import-browser", help="Importa y valida la sesión activa de un navegador."
    )
    browser_login.add_argument("account")
    browser_login.add_argument(
        "--browser",
        required=True,
        choices=(
            "brave",
            "chrome",
            "chromium",
            "edge",
            "firefox",
            "librewolf",
            "opera",
            "opera_gx",
            "safari",
            "vivaldi",
        ),
    )
    session_id_login = auth_commands.add_parser(
        "import-sessionid",
        help="Solicita un sessionid de forma oculta, lo valida y guarda la sesión.",
    )
    session_id_login.add_argument("account")
    auth_status = auth_commands.add_parser("status", help="Indica si existe una sesión local.")
    auth_status.add_argument("account")

    run = commands.add_parser("run", help="Ejecuta un chequeo.")
    run.add_argument("--account", help="Limita el chequeo a una cuenta local.")
    run.add_argument(
        "--if-due",
        action="store_true",
        help="Sólo ejecuta si pasó la hora configurada y hoy no hubo éxito.",
    )

    import_export = commands.add_parser(
        "import-export", help="Importa una descarga oficial de Instagram en JSON."
    )
    import_export.add_argument("account")
    import_export.add_argument("directory", type=Path)

    history = commands.add_parser("history", help="Muestra el historial de cantidades.")
    history.add_argument("account")
    history.add_argument("--limit", type=int, default=10)

    popup = commands.add_parser("popup", help="Configura notificaciones de escritorio.")
    popup.add_argument("state", choices=("enable", "disable"))

    telegram = commands.add_parser("telegram", help="Configura las notificaciones de Telegram.")
    telegram_commands = telegram.add_subparsers(dest="telegram_command", required=True)
    telegram_configure = telegram_commands.add_parser(
        "configure", help="Guarda el destino y el token en el almacén seguro."
    )
    telegram_configure.add_argument("--chat-id", required=True)
    telegram_disable = telegram_commands.add_parser("disable", help="Desactiva Telegram.")
    telegram_disable.add_argument("--forget-token", action="store_true")
    telegram_commands.add_parser("test", help="Envía un mensaje de prueba.")

    schedule = commands.add_parser("schedule", help="Administra la tarea diaria nativa.")
    schedule_commands = schedule.add_subparsers(dest="schedule_command", required=True)
    schedule_install = schedule_commands.add_parser("install", help="Instala o actualiza la tarea.")
    schedule_install.add_argument("--time", default="09:00", help="Hora local HH:MM.")
    schedule_install.add_argument("--backend", choices=("windows", "launchd", "systemd", "cron"))
    schedule_commands.add_parser("status", help="Muestra el estado de la tarea.")
    schedule_commands.add_parser("uninstall", help="Quita la tarea nativa.")

    config = commands.add_parser("config", help="Muestra configuración y rutas.")
    config.add_argument("view", choices=("show", "path"), nargs="?", default="show")
    return root


def main(argv: list[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    paths = app_paths()
    _configure_logging(paths)
    try:
        return _dispatch(arguments, paths)
    except (
        ConfigError,
        SchedulerError,
        NotificationError,
        CollectionError,
        AlreadyRunningError,
    ) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        _alert_automatic_exception(arguments, paths, exc)
        return 2
    except Exception as exc:
        logging.getLogger("seguidores").exception("Fallo inesperado de la aplicación")
        print(f"Error inesperado: {exc}", file=sys.stderr)
        _alert_automatic_exception(arguments, paths, exc)
        return 1
    except KeyboardInterrupt:
        print("Cancelado.", file=sys.stderr)
        return 130


def _dispatch(arguments: argparse.Namespace, paths: AppPaths) -> int:
    if arguments.command == "init":
        created = not paths.config.exists()
        load_config(paths, create=True)
        message = "Configuración creada" if created else "La configuración ya existe"
        print(f"{message}: {paths.config}")
        return 0
    if arguments.command in {"setup", "gui"}:
        if arguments.command == "setup" and arguments.terminal:
            return _setup_terminal(paths)
        from seguidores.gui import main as gui_main

        return gui_main(paths)

    config = load_config(paths)
    if arguments.command == "account":
        return _account_command(arguments, paths, config)
    if arguments.command == "auth":
        account = config.account(arguments.account)
        collector = InstagramCollector(paths)
        if arguments.auth_command == "login":
            session = collector.login(account)
            print(f"Sesión guardada localmente: {session}")
        elif arguments.auth_command == "import-browser":
            session = collector.import_browser_session(account, arguments.browser)
            print(f"Sesión importada y validada: {session}")
        elif arguments.auth_command == "import-sessionid":
            session_id = getpass("sessionid de Instagram (entrada oculta): ")
            session = collector.import_session_id(account, session_id)
            print(f"sessionid validado y sesión guardada: {session}")
        else:
            state = collector.session_state(account)
            print(f"{account.name}: {state.label}")
        return 0
    if arguments.command == "run":
        if not config.accounts:
            raise ConfigError("No hay cuentas. Usá 'seguidores account add ...'.")
        result = Tracker(paths, config).run(account_name=arguments.account, if_due=arguments.if_due)
        if result.skipped:
            print("No hay chequeos pendientes para hoy.")
        for completed in result.completed:
            print(format_report(completed.comparison))
            for failure in completed.notification_failures:
                print(f"Aviso: falló {failure.channel}: {failure.error}", file=sys.stderr)
        for failed in result.failed:
            print(f"Error en {failed.account_name}: {failed.error}", file=sys.stderr)
        if result.automatic_notification_failure:
            print(
                "Aviso: no se pudo notificar por Telegram el error automático: "
                f"{result.automatic_notification_failure.error}",
                file=sys.stderr,
            )
        return 1 if result.failed else 0
    if arguments.command == "import-export":
        account = config.account(arguments.account)
        graph = ExportCollector().collect_directory(arguments.directory)
        comparison = Tracker(paths, config).record_graph(
            account, graph, datetime.now().astimezone()
        )
        failures = notify(comparison, config.notifications)
        print(format_report(comparison))
        for failure in failures:
            print(f"Aviso: falló {failure.channel}: {failure.error}", file=sys.stderr)
        return 0
    if arguments.command == "history":
        config.account(arguments.account)
        if arguments.limit < 1:
            raise ConfigError("--limit debe ser mayor que cero.")
        rows = Tracker(paths, config).store.history(arguments.account, arguments.limit)
        if not rows:
            print("Todavía no hay capturas.")
        for captured_at, followers, following in rows:
            local_time = datetime.fromisoformat(captured_at).astimezone()
            print(f"{local_time:%Y-%m-%d %H:%M} · seguidores {followers} · seguidos {following}")
        return 0
    if arguments.command == "popup":
        config.notifications.popup = arguments.state == "enable"
        save_config(paths, config)
        print(f"Popups {'activados' if config.notifications.popup else 'desactivados'}.")
        return 0
    if arguments.command == "telegram":
        return _telegram_command(arguments, paths, config)
    if arguments.command == "schedule":
        return _schedule_command(arguments, paths, config)
    if arguments.command == "config":
        if arguments.view == "path":
            print(paths.config)
        else:
            print(json.dumps(asdict(config), indent=2, ensure_ascii=False))
            print(f"# datos: {paths.root}")
        return 0
    raise AssertionError(f"Comando no implementado: {arguments.command}")


def _account_command(arguments: argparse.Namespace, paths: AppPaths, config) -> int:
    if arguments.account_command == "add":
        candidate = AccountConfig(
            name=arguments.name,
            username=arguments.username,
            login_username=arguments.login_username or arguments.username,
        )
        candidate.validate()
        config.accounts = [
            account for account in config.accounts if account.name.lower() != candidate.name.lower()
        ]
        config.accounts.append(candidate)
        save_config(paths, config)
        print(f"Cuenta {candidate.name} configurada para @{candidate.username}.")
        return 0
    if arguments.account_command == "list":
        if not config.accounts:
            print("No hay cuentas configuradas.")
        for account in config.accounts:
            state = "activa" if account.enabled else "desactivada"
            print(
                f"{account.name}: @{account.username} (sesión @{account.login_username}, {state})"
            )
        return 0
    account = config.account(arguments.name)
    if arguments.account_command == "remove":
        config.accounts.remove(account)
        print(f"Cuenta {account.name} eliminada de la configuración.")
    else:
        account.enabled = arguments.account_command == "enable"
        print(f"Cuenta {account.name} {'activada' if account.enabled else 'desactivada'}.")
    save_config(paths, config)
    return 0


def _telegram_command(arguments: argparse.Namespace, paths: AppPaths, config) -> int:
    if arguments.telegram_command == "configure":
        token = getpass("Token del bot de Telegram (se guardará en el almacén seguro): ")
        set_telegram_token(token)
        config.notifications.telegram.chat_id = arguments.chat_id
        config.notifications.telegram.enabled = True
        save_config(paths, config)
        print("Telegram configurado. Usá 'seguidores telegram test' para verificarlo.")
        return 0
    if arguments.telegram_command == "disable":
        config.notifications.telegram.enabled = False
        save_config(paths, config)
        if arguments.forget_token:
            delete_telegram_token()
        print("Telegram desactivado.")
        return 0
    token = get_telegram_token()
    if not token:
        raise NotificationError("No hay un token de Telegram guardado.")
    send_telegram(token, config.notifications.telegram.chat_id, "Seguidores: prueba correcta ✅")
    print("Mensaje de prueba enviado.")
    return 0


def _schedule_command(arguments: argparse.Namespace, paths: AppPaths, config) -> int:
    if arguments.schedule_command == "install":
        parse_time(arguments.time)
        backend = scheduler.install(paths, arguments.time, backend=arguments.backend)
        config.schedule.enabled = True
        config.schedule.time = arguments.time
        config.schedule.backend = backend
        save_config(paths, config)
        print(f"Tarea diaria instalada con {backend} a las {arguments.time}.")
        return 0
    backend = config.schedule.backend or None
    if arguments.schedule_command == "status":
        current = scheduler.status(backend)
        state = "instalada" if current.installed else "no instalada"
        print(f"{current.backend}: {state}. {current.detail}".strip())
        return 0
    if backend:
        scheduler.uninstall(backend)
    config.schedule.enabled = False
    config.schedule.backend = ""
    save_config(paths, config)
    print("Tarea diaria eliminada.")
    return 0


def _setup_terminal(paths: AppPaths) -> int:
    config = load_config(paths, create=True)
    print(f"Configuración: {paths.config}")
    name = input("Nombre local de la cuenta [personal]: ").strip() or "personal"
    username = input("Usuario de Instagram (sin @): ").strip().lstrip("@")
    login_username = (
        input(f"Usuario para iniciar sesión [{username}]: ").strip().lstrip("@") or username
    )
    account = AccountConfig(name, username, login_username)
    account.validate()
    config.accounts = [item for item in config.accounts if item.name.lower() != name.lower()]
    config.accounts.append(account)
    popup_answer = input("¿Activar popup? [S/n]: ").strip().lower()
    config.notifications.popup = popup_answer not in {"n", "no"}
    save_config(paths, config)

    if _yes("¿Iniciar sesión en Instagram ahora? [S/n]: ", default=True):
        InstagramCollector(paths).login(account)
    if _yes("¿Configurar Telegram? [s/N]: ", default=False):
        chat_id = input("ID del chat o @alias del canal: ").strip()
        token = getpass("Token del bot: ")
        set_telegram_token(token)
        config.notifications.telegram.chat_id = chat_id
        config.notifications.telegram.enabled = True
        save_config(paths, config)
    if _yes("¿Instalar el chequeo diario? [S/n]: ", default=True):
        time = input("Hora local [09:00]: ").strip() or "09:00"
        backend = scheduler.install(paths, time)
        config.schedule.enabled = True
        config.schedule.time = time
        config.schedule.backend = backend
        save_config(paths, config)
    print("Configuración inicial terminada.")
    return 0


def _yes(prompt: str, *, default: bool) -> bool:
    answer = input(prompt).strip().lower()
    if not answer:
        return default
    return answer in {"s", "si", "sí", "y", "yes"}


def _alert_automatic_exception(
    arguments: argparse.Namespace, paths: AppPaths, exception: Exception
) -> None:
    if arguments.command != "run" or not getattr(arguments, "if_due", False):
        return
    logger = logging.getLogger("seguidores")
    logger.exception("La ejecución automática terminó con un error")
    try:
        config = load_config(paths)
    except Exception:
        logger.exception(
            "No se pudo leer la configuración para avisar el error automático por Telegram"
        )
        return
    notification_failure = notify_automatic_failure(
        [("ejecución", str(exception))],
        config.notifications,
        datetime.now().astimezone(),
    )
    if notification_failure:
        logger.error(
            "No se pudo avisar por Telegram el error automático: %s",
            notification_failure.error,
        )
    elif config.notifications.telegram.enabled:
        logger.info("Se avisó por Telegram el error de la ejecución automática.")


def _configure_logging(paths: AppPaths) -> None:
    paths.ensure()
    handler = RotatingFileHandler(
        paths.logs / "seguidores.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger = logging.getLogger("seguidores")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        logger.addHandler(handler)


if __name__ == "__main__":
    raise SystemExit(main())
