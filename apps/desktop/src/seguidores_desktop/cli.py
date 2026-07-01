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

from seguidores import __version__
from seguidores.app import Tracker
from seguidores.collector import CollectionError, ExportCollector
from seguidores.config import AccountConfig, ConfigError, load_config, save_config
from seguidores.notifier import (
    NotificationError,
    delete_telegram_token,
    get_telegram_token,
    notify,
    send_telegram,
    set_telegram_token,
)
from seguidores.paths import AppPaths, app_paths
from seguidores.report import format_report

from seguidores_desktop.legacy_cleanup import LegacyCleanupError, cleanup_legacy_state


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        prog="seguidores",
        description="Compara exportaciones JSON oficiales de Instagram.",
    )
    root.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = root.add_subparsers(dest="command", required=True)

    commands.add_parser("init", help="Crea una configuración vacía.")
    setup = commands.add_parser("setup", help="Abre la configuración inicial.")
    setup.add_argument(
        "--terminal", action="store_true", help="Usa el asistente de texto en vez de la ventana."
    )
    commands.add_parser("gui", help="Abre la interfaz gráfica.")

    account = commands.add_parser("account", help="Administra perfiles locales.")
    account_commands = account.add_subparsers(dest="account_command", required=True)
    add = account_commands.add_parser("add", help="Agrega o actualiza un perfil.")
    add.add_argument("name", help="Nombre local, por ejemplo 'personal'.")
    add.add_argument("--username", required=True, help="Usuario de Instagram del reporte.")
    account_commands.add_parser("list", help="Lista los perfiles.")
    remove = account_commands.add_parser("remove", help="Elimina un perfil de la configuración.")
    remove.add_argument("name")

    import_json = commands.add_parser(
        "import-json", help="Compara archivos JSON oficiales y guarda una captura."
    )
    import_json.add_argument("account", help="Nombre del perfil local.")
    import_json.add_argument(
        "--followers", type=Path, nargs="+", required=True, help="Uno o más followers_*.json."
    )
    import_json.add_argument(
        "--following", type=Path, nargs="+", required=True, help="Uno o más following*.json."
    )

    history = commands.add_parser("history", help="Muestra el historial de cantidades.")
    history.add_argument("account")
    history.add_argument("--limit", type=int, default=10)

    popup = commands.add_parser("popup", help="Configura notificaciones de escritorio.")
    popup.add_argument("state", choices=("enable", "disable"))

    telegram = commands.add_parser("telegram", help="Configura las notificaciones de Telegram.")
    telegram_commands = telegram.add_subparsers(dest="telegram_command", required=True)
    configure = telegram_commands.add_parser(
        "configure", help="Guarda el destino y el token en el almacén seguro."
    )
    configure.add_argument("--chat-id", required=True)
    disable = telegram_commands.add_parser("disable", help="Desactiva Telegram.")
    disable.add_argument("--forget-token", action="store_true")
    telegram_commands.add_parser("test", help="Envía un mensaje de prueba.")

    config = commands.add_parser("config", help="Muestra configuración y rutas.")
    config.add_argument("view", choices=("show", "path"), nargs="?", default="show")
    commands.add_parser("cleanup-legacy", help=argparse.SUPPRESS)
    return root


def main(argv: list[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    paths = app_paths()
    _configure_logging(paths)
    try:
        return _dispatch(arguments, paths)
    except (ConfigError, NotificationError, CollectionError, LegacyCleanupError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        logging.getLogger("seguidores").exception("Fallo inesperado de la aplicación")
        print(f"Error inesperado: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Cancelado.", file=sys.stderr)
        return 130


def _dispatch(arguments: argparse.Namespace, paths: AppPaths) -> int:
    if arguments.command == "init":
        created = not paths.config.exists()
        load_config(paths, create=True)
        print(
            f"{'Configuración creada' if created else 'La configuración ya existe'}: {paths.config}"
        )
        return 0
    if arguments.command in {"setup", "gui"}:
        if arguments.command == "setup" and arguments.terminal:
            return _setup_terminal(paths)
        from seguidores_desktop.gui import main as gui_main

        return gui_main(paths)
    if arguments.command == "cleanup-legacy":
        cleanup_legacy_state(paths)
        print("Automatización y sesiones antiguas eliminadas.")
        return 0

    config = load_config(paths)
    if arguments.command == "account":
        return _account_command(arguments, paths, config)
    if arguments.command == "import-json":
        account = config.account(arguments.account)
        graph = ExportCollector().collect_files(arguments.followers, arguments.following)
        comparison = Tracker(paths).record_graph(account, graph, datetime.now().astimezone())
        failures = notify(comparison, config.notifications)
        print(format_report(comparison))
        for failure in failures:
            print(f"Aviso: falló {failure.channel}: {failure.error}", file=sys.stderr)
        return 0
    if arguments.command == "history":
        config.account(arguments.account)
        if arguments.limit < 1:
            raise ConfigError("--limit debe ser mayor que cero.")
        rows = Tracker(paths).store.history(arguments.account, arguments.limit)
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
        candidate = AccountConfig(arguments.name, arguments.username)
        candidate.validate()
        config.accounts = [
            account
            for account in config.accounts
            if account.name.casefold() != candidate.name.casefold()
        ]
        config.accounts.append(candidate)
        save_config(paths, config)
        print(f"Perfil {candidate.name} configurado para @{candidate.username}.")
        return 0
    if arguments.account_command == "list":
        if not config.accounts:
            print("No hay perfiles configurados.")
        for account in config.accounts:
            print(f"{account.name}: @{account.username}")
        return 0
    account = config.account(arguments.name)
    config.accounts.remove(account)
    save_config(paths, config)
    print(f"Perfil {account.name} eliminado de la configuración.")
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


def _setup_terminal(paths: AppPaths) -> int:
    config = load_config(paths, create=True)
    print(f"Configuración: {paths.config}")
    name = input("Nombre local del perfil [personal]: ").strip() or "personal"
    username = input("Usuario de Instagram (sin @): ").strip().lstrip("@")
    account = AccountConfig(name, username)
    account.validate()
    config.accounts = [item for item in config.accounts if item.name.casefold() != name.casefold()]
    config.accounts.append(account)
    popup_answer = input("¿Activar popup al importar? [S/n]: ").strip().casefold()
    config.notifications.popup = popup_answer not in {"n", "no"}
    save_config(paths, config)
    print("Configuración terminada. Usá 'seguidores import-json --help' para importar archivos.")
    return 0


def _configure_logging(paths: AppPaths) -> None:
    paths.ensure()
    logger = logging.getLogger("seguidores")
    logger.setLevel(logging.INFO)
    if logger.handlers:
        return
    handler = RotatingFileHandler(
        paths.logs / "seguidores.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)


if __name__ == "__main__":
    raise SystemExit(main())
