from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
from io import BytesIO
from logging.handlers import RotatingFileHandler
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from seguidores import __version__
from seguidores.config import AccountConfig, Config, load_config, save_config
from seguidores.notifier import get_telegram_token
from seguidores.paths import AppPaths, app_paths
from telegram import Bot, BotCommand, Update
from telegram.constants import ChatType
from telegram.error import TelegramError
from telegram.ext import Application, ApplicationBuilder, CommandHandler, ContextTypes, Defaults

BOT_TOKEN_ENVIRONMENT_VARIABLE = "SEGUIDORES_TELEGRAM_BOT_TOKEN"
ADMIN_USER_ID_ENVIRONMENT_VARIABLE = "JO_BOT_ADMIN_USER_ID"
ADMIN_USER_IDS_ENVIRONMENT_VARIABLE = "JO_BOT_ADMIN_USER_IDS"
TIMEZONE_ENVIRONMENT_VARIABLE = "JO_BOT_TIMEZONE"
DEFAULT_TIMEZONE = "America/Argentina/Buenos_Aires"
TELEGRAM_TEXT_LIMIT = 4_000
LOCAL_ENV_FILENAME = ".env.local"

HELP_TEXT = """Jo Bot · Seguidores

/account ALIAS USUARIO — agrega o actualiza un perfil local
/remove ALIAS — elimina un perfil
/accounts — lista los perfiles configurados
/status — muestra el estado del bot
/debug — muestra el Update JSON y tu user_id de Telegram
/help — muestra esta ayuda

Instagram ya no se consulta desde el bot. Los seguidores y seguidos se comparan cargando los
archivos JSON oficiales en la aplicación de escritorio.

Los comandos de administración aceptan todos los usuarios configurados.
/start, /help y /debug son públicos en chats privados, grupos y canales.
"""


class JoBotController:
    def __init__(self, paths: AppPaths, admin_user_ids: tuple[int, ...], timezone: ZoneInfo):
        self.paths = paths
        self.admin_user_ids = admin_user_ids
        self.admin_user_id = admin_user_ids[0]
        self.timezone = timezone

    def load_config(self) -> Config:
        return load_config(self.paths, create=True)

    def configure_account(self, name: str, username: str) -> str:
        config = self.load_config()
        candidate = AccountConfig(name.strip(), username.strip().lstrip("@"))
        candidate.validate()
        config.accounts = [
            account
            for account in config.accounts
            if account.name.casefold() != candidate.name.casefold()
        ]
        config.accounts.append(candidate)
        save_config(self.paths, config)
        return f"Perfil {candidate.name} configurado para @{candidate.username}."

    def remove_account(self, name: str) -> str:
        config = self.load_config()
        account = config.account(name)
        config.accounts.remove(account)
        save_config(self.paths, config)
        return f"Perfil {account.name} eliminado de la configuración."

    def accounts_text(self) -> str:
        config = self.load_config()
        if not config.accounts:
            return "No hay perfiles configurados. Usá /account ALIAS USUARIO."
        return "\n".join(
            [
                "Perfiles configurados:",
                *(f"• {item.name}: @{item.username}" for item in config.accounts),
            ]
        )

    def status_text(self) -> str:
        config = self.load_config()
        return "\n".join(
            (
                f"Jo Bot {__version__}",
                f"Zona horaria: {self.timezone.key}",
                "Acceso directo a Instagram: desactivado",
                "Chequeos diarios: desactivados",
                f"Perfiles locales: {len(config.accounts)}",
                f"Datos: {self.paths.root}",
            )
        )


class JoBot:
    def __init__(self, token: str, controller: JoBotController):
        self.token = token
        self.controller = controller
        self.admin_user_id = controller.admin_user_id
        self.admin_user_ids = frozenset(controller.admin_user_ids)
        self.operation_lock = asyncio.Lock()
        self.log = logging.getLogger("jo_bot")

    def build_application(self) -> Application:
        application = (
            ApplicationBuilder()
            .token(self.token)
            .defaults(Defaults(tzinfo=self.controller.timezone))
            .concurrent_updates(False)
            .post_init(self.post_init)
            .build()
        )
        application.add_handler(CommandHandler("start", self.help_command))
        application.add_handler(CommandHandler("help", self.help_command))
        application.add_handler(CommandHandler("debug", self.debug_command))
        application.add_handler(CommandHandler("account", self.account_command))
        application.add_handler(CommandHandler("remove", self.remove_command))
        application.add_handler(CommandHandler("accounts", self.accounts_command))
        application.add_handler(CommandHandler("status", self.status_command))
        application.add_error_handler(self.error_handler)
        return application

    async def post_init(self, application: Application) -> None:
        await application.bot.set_my_commands(
            [
                BotCommand("start", "Iniciar y mostrar la ayuda"),
                BotCommand("status", "Mostrar el estado"),
                BotCommand("accounts", "Listar perfiles"),
                BotCommand("account", "Agregar o actualizar un perfil"),
                BotCommand("debug", "Mostrar el Update JSON y tu user_id"),
                BotCommand("help", "Mostrar ayuda"),
            ]
        )
        self.log.info("Jo Bot iniciado para %s administradores", len(self.admin_user_ids))

    async def _authorized(self, update: Update) -> bool:
        user = update.effective_user
        chat = update.effective_chat
        authorized = bool(
            user and chat and user.id in self.admin_user_ids and chat.type == ChatType.PRIVATE
        )
        if authorized:
            return True
        if chat and chat.type == ChatType.PRIVATE and update.effective_message:
            await update.effective_message.reply_text("Usuario no autorizado.")
        return False

    async def help_command(self, update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._reply(update, HELP_TEXT)

    async def debug_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        chat = update.effective_chat
        if not chat:
            return
        payload = json.dumps(update.to_dict(), ensure_ascii=False, indent=2, default=str)
        user_id = user.id if user else "no disponible"
        await _send_text_or_document(
            context.bot,
            chat.id,
            f"Telegram recibió este Update. El user_id es {user_id}.\n\n{payload}",
            "jo-bot-debug-update.txt",
            caption="Jo Bot: Update JSON de Telegram.",
        )

    async def account_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._authorized(update):
            return
        if len(context.args) != 2:
            await self._reply(update, "Uso: /account ALIAS USUARIO")
            return
        async with self.operation_lock:
            try:
                result = await asyncio.to_thread(
                    self.controller.configure_account, context.args[0], context.args[1]
                )
            except Exception as exc:
                await self._reply_error(update, exc)
                return
        await self._reply(update, result)

    async def remove_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._authorized(update):
            return
        if len(context.args) != 1:
            await self._reply(update, "Uso: /remove ALIAS")
            return
        try:
            result = await asyncio.to_thread(self.controller.remove_account, context.args[0])
        except Exception as exc:
            await self._reply_error(update, exc)
            return
        await self._reply(update, result)

    async def accounts_command(self, update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
        if await self._authorized(update):
            await self._reply(update, await asyncio.to_thread(self.controller.accounts_text))

    async def status_command(self, update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
        if await self._authorized(update):
            await self._reply(update, await asyncio.to_thread(self.controller.status_text))

    async def _reply_error(self, update: Update, exception: Exception) -> None:
        await self._reply(update, f"Error: {str(exception)[:3900]}")

    async def _reply(self, update: Update, text_value: str) -> None:
        if update.effective_chat:
            await _send_text_or_document(
                update.get_bot(), update.effective_chat.id, text_value, "jo-bot-respuesta.txt"
            )

    async def error_handler(self, _update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        self.log.error("Error no controlado en Jo Bot", exc_info=context.error)
        try:
            await context.bot.send_message(
                chat_id=self.admin_user_id,
                text=f"Jo Bot: error interno: {str(context.error)[:3500]}",
            )
        except TelegramError:
            self.log.exception("No se pudo avisar el error interno por Telegram")


async def _send_text_or_document(
    bot: object,
    chat_id: int,
    text_value: str,
    filename: str,
    *,
    caption: str = "Jo Bot: detalle completo adjunto.",
) -> None:
    if len(text_value) <= TELEGRAM_TEXT_LIMIT:
        await bot.send_message(chat_id=chat_id, text=text_value)
        return
    document = BytesIO(text_value.encode("utf-8"))
    document.name = filename
    await bot.send_document(chat_id=chat_id, document=document, caption=caption)


async def _discover_admin(token: str) -> int:
    print("Enviá /start al bot desde tu chat privado. Esperando el mensaje…")
    offset: int | None = None
    async with Bot(token) as bot:
        await bot.delete_webhook(drop_pending_updates=False)
        while True:
            updates = await bot.get_updates(offset=offset, timeout=30, allowed_updates=["message"])
            for update in updates:
                offset = update.update_id + 1
                if (
                    update.effective_user
                    and update.effective_chat
                    and update.effective_chat.type == ChatType.PRIVATE
                ):
                    print(f"JO_BOT_ADMIN_USER_ID={update.effective_user.id}")
                    return update.effective_user.id


def _configure_logging(paths: AppPaths) -> None:
    paths.ensure()
    handler = RotatingFileHandler(
        paths.logs / "jo-bot.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logger = logging.getLogger("seguidores")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        logger.addHandler(handler)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Jo Bot · Seguidores por Telegram")
    parser.add_argument("--version", action="version", version=f"jo-bot {__version__}")
    parser.add_argument("--discover-admin", action="store_true")
    return parser


def _parse_admin_user_ids() -> tuple[int, ...]:
    raw_value = os.environ.get(ADMIN_USER_IDS_ENVIRONMENT_VARIABLE, "").strip()
    if not raw_value:
        raw_value = os.environ.get(ADMIN_USER_ID_ENVIRONMENT_VARIABLE, "").strip()
    try:
        values = tuple(dict.fromkeys(int(part.strip()) for part in raw_value.split(",")))
    except ValueError as exc:
        raise ValueError("los user_id deben ser números separados por comas") from exc
    if not values or any(value <= 0 for value in values):
        raise ValueError("se requiere al menos un user_id positivo")
    return values


def _load_local_environment(path: Path | None = None) -> Path:
    if path is None:
        candidates = (
            Path.cwd() / "apps" / "jo-bot" / LOCAL_ENV_FILENAME,
            Path.cwd() / LOCAL_ENV_FILENAME,
        )
        environment_path = next((item for item in candidates if item.is_file()), candidates[0])
    else:
        environment_path = path
    if not environment_path.is_file():
        raise FileNotFoundError(
            f"No se encontró {environment_path}. Copiá apps/jo-bot/.env.example como "
            "apps/jo-bot/.env.local y configurá tus IDs."
        )
    for line_number, raw_line in enumerate(
        environment_path.read_text(encoding="utf-8-sig").splitlines(), start=1
    ):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if not separator or not key.strip():
            raise ValueError(f"Línea {line_number} inválida en {environment_path}.")
        os.environ.setdefault(key.strip(), value.strip())
    return environment_path


def local_main() -> int:
    try:
        _load_local_environment()
    except (FileNotFoundError, OSError, ValueError) as exc:
        print(f"No se pudo iniciar jobot: {exc}")
        return 2
    return main()


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    token = (get_telegram_token() or "").strip()
    if not token:
        print(f"Falta la variable {BOT_TOKEN_ENVIRONMENT_VARIABLE}.")
        return 2
    if arguments.discover_admin:
        asyncio.run(_discover_admin(token))
        return 0
    try:
        admin_user_ids = _parse_admin_user_ids()
    except ValueError as exc:
        print(f"Falta un {ADMIN_USER_IDS_ENVIRONMENT_VARIABLE} válido: {exc}.")
        return 2
    timezone_name = os.environ.get(TIMEZONE_ENVIRONMENT_VARIABLE, DEFAULT_TIMEZONE)
    try:
        timezone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        print(f"Zona horaria inválida en {TIMEZONE_ENVIRONMENT_VARIABLE}: {timezone_name}")
        return 2
    paths = app_paths()
    _configure_logging(paths)
    application = JoBot(token, JoBotController(paths, admin_user_ids, timezone)).build_application()
    application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
