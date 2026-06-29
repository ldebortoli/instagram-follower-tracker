from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
from datetime import datetime, time
from io import BytesIO
from logging.handlers import RotatingFileHandler
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from seguidores import __version__
from seguidores.app import RunResult, Tracker
from seguidores.collector import InstagramCollector
from seguidores.config import (
    AccountConfig,
    Config,
    ConfigError,
    load_config,
    parse_time,
    save_config,
)
from seguidores.http_diagnostics import sanitize_text
from seguidores.notifier import get_telegram_token
from seguidores.paths import AppPaths, app_paths
from telegram import Bot, BotCommand, Update
from telegram.constants import ChatType
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    Defaults,
    MessageHandler,
    filters,
)

BOT_TOKEN_ENVIRONMENT_VARIABLE = "SEGUIDORES_TELEGRAM_BOT_TOKEN"
ADMIN_USER_ID_ENVIRONMENT_VARIABLE = "JO_BOT_ADMIN_USER_ID"
ADMIN_USER_IDS_ENVIRONMENT_VARIABLE = "JO_BOT_ADMIN_USER_IDS"
TIMEZONE_ENVIRONMENT_VARIABLE = "JO_BOT_TIMEZONE"
DEFAULT_TIMEZONE = "America/Argentina/Buenos_Aires"
DAILY_JOB_NAME = "jo-bot-daily-check"
STARTUP_JOB_NAME = "jo-bot-startup-check"
TELEGRAM_TEXT_LIMIT = 4_000
PENDING_SESSION_KEY = "jo_bot_pending_session_account"
LOCAL_ENV_FILENAME = ".env.local"

HELP_TEXT = """Jo Bot · Seguidores

/account ALIAS USUARIO [LOGIN] — agrega o actualiza una cuenta
/remove ALIAS — elimina una cuenta
/accounts — lista las cuentas configuradas
/session ALIAS — solicita y guarda un sessionid
/check [ALIAS] — ejecuta un chequeo manual
/schedule HH:MM — programa el chequeo diario
/schedule_off — desactiva el chequeo diario
/status — muestra sesiones, cooldown y horario
/cancel — cancela la carga de un sessionid
/debug — muestra el Update JSON y tu user_id de Telegram
/help — muestra esta ayuda

Los comandos de administración aceptan todos los usuarios configurados.
/start, /help y /debug son públicos en chats privados, grupos y canales.
/debug no permite modificar nada."""


class JoBotController:
    """Synchronous application layer shared by Telegram handlers and tests."""

    def __init__(
        self,
        paths: AppPaths,
        admin_user_ids: tuple[int, ...],
        timezone: ZoneInfo,
    ):
        self.paths = paths
        self.admin_user_ids = admin_user_ids
        self.admin_user_id = admin_user_ids[0]
        self.timezone = timezone

    def load_config(self) -> Config:
        config = load_config(self.paths, create=True)
        changed = False
        if config.notifications.popup:
            config.notifications.popup = False
            changed = True
        if not config.notifications.telegram.enabled:
            config.notifications.telegram.enabled = True
            changed = True
        chat_id = str(self.admin_user_id)
        if config.notifications.telegram.chat_id != chat_id:
            config.notifications.telegram.chat_id = chat_id
            changed = True
        if changed:
            save_config(self.paths, config)
        return config

    def configure_account(
        self,
        name: str,
        username: str,
        login_username: str | None = None,
    ) -> str:
        config = self.load_config()
        target = username.strip().lstrip("@")
        login = (login_username or target).strip().lstrip("@")
        candidate = AccountConfig(name.strip(), target, login)
        candidate.validate()
        config.accounts = [
            account
            for account in config.accounts
            if account.name.casefold() != candidate.name.casefold()
        ]
        config.accounts.append(candidate)
        save_config(self.paths, config)
        return (
            f"Cuenta {candidate.name} configurada: objetivo @{candidate.username}, "
            f"sesión @{candidate.login_username}. Ahora usá /session {candidate.name}."
        )

    def remove_account(self, name: str) -> str:
        config = self.load_config()
        account = config.account(name)
        config.accounts.remove(account)
        save_config(self.paths, config)
        return f"Cuenta {account.name} eliminada de la configuración."

    def require_account(self, name: str) -> AccountConfig:
        return self.load_config().account(name)

    def import_session_id(self, account_name: str, session_id: str) -> str:
        config = self.load_config()
        account = config.account(account_name)
        InstagramCollector(self.paths).import_session_id(account, session_id)
        return f"Sesión de @{account.login_username} validada y guardada para {account.name}."

    def accounts_text(self) -> str:
        config = self.load_config()
        if not config.accounts:
            return "No hay cuentas configuradas. Usá /account ALIAS USUARIO [LOGIN]."
        lines = ["Cuentas configuradas:"]
        for account in config.accounts:
            state = "activa" if account.enabled else "desactivada"
            lines.append(
                f"• {account.name}: objetivo @{account.username}, "
                f"sesión @{account.login_username}, {state}"
            )
        return "\n".join(lines)

    def status_text(self) -> str:
        config = self.load_config()
        schedule = (
            f"todos los días a las {config.schedule.time}"
            if config.schedule.enabled
            else "desactivado"
        )
        lines = [
            f"Jo Bot {__version__}",
            f"Zona horaria: {self.timezone.key}",
            f"Chequeo automático: {schedule}",
            f"Datos: {self.paths.root}",
        ]
        if not config.accounts:
            lines.append("Cuentas: ninguna")
            return "\n".join(lines)
        collector = InstagramCollector(self.paths)
        lines.append("Cuentas:")
        for account in config.accounts:
            session = collector.session_state(account)
            lines.append(f"• {account.name} (@{account.username}): {session.label}")
        return "\n".join(lines)

    def set_schedule(self, value: str) -> str:
        parse_time(value)
        config = self.load_config()
        config.schedule.enabled = True
        config.schedule.time = value
        config.schedule.backend = "jo-bot"
        save_config(self.paths, config)
        return f"Chequeo diario programado a las {value} ({self.timezone.key})."

    def disable_schedule(self) -> str:
        config = self.load_config()
        config.schedule.enabled = False
        config.schedule.backend = ""
        save_config(self.paths, config)
        return "Chequeo diario desactivado. El comando /check sigue disponible."

    def run_check(
        self,
        account_name: str | None = None,
        *,
        if_due: bool = False,
        telegram_chat_id: int | None = None,
    ) -> RunResult:
        config = self.load_config()
        if not config.accounts:
            raise ConfigError("No hay cuentas configuradas.")
        if telegram_chat_id is not None:
            config.notifications.telegram.chat_id = str(telegram_chat_id)
        now = datetime.now(self.timezone)
        return Tracker(self.paths, config).run(
            account_name=account_name,
            if_due=if_due,
            now=now,
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
        defaults = Defaults(tzinfo=self.controller.timezone)
        application = (
            ApplicationBuilder()
            .token(self.token)
            .defaults(defaults)
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
        application.add_handler(CommandHandler("session", self.session_command))
        application.add_handler(CommandHandler("check", self.check_command))
        application.add_handler(CommandHandler("schedule", self.schedule_command))
        application.add_handler(CommandHandler("schedule_off", self.schedule_off_command))
        application.add_handler(CommandHandler("status", self.status_command))
        application.add_handler(CommandHandler("cancel", self.cancel_command))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.text_message))
        application.add_error_handler(self.error_handler)
        return application

    async def post_init(self, application: Application) -> None:
        await application.bot.set_my_commands(
            [
                BotCommand("start", "Iniciar y mostrar la ayuda"),
                BotCommand("status", "Estado de cuentas, sesiones y horario"),
                BotCommand("accounts", "Listar cuentas"),
                BotCommand("account", "Agregar o actualizar una cuenta"),
                BotCommand("session", "Cargar un sessionid"),
                BotCommand("check", "Comprobar seguidores ahora"),
                BotCommand("schedule", "Configurar horario diario"),
                BotCommand("schedule_off", "Desactivar horario diario"),
                BotCommand("debug", "Mostrar el Update JSON y tu user_id"),
                BotCommand("help", "Mostrar ayuda"),
            ]
        )
        self._configure_daily_job(application, include_startup_check=True)
        self.log.info("Jo Bot iniciado para el usuario %s", self.admin_user_id)

    async def _authorized(self, update: Update) -> bool:
        user = update.effective_user
        chat = update.effective_chat
        authorized = bool(
            user and chat and user.id in self.admin_user_ids and chat.type == ChatType.PRIVATE
        )
        if authorized:
            return True
        self.log.warning(
            "Comando rechazado de user_id=%s chat_type=%s",
            getattr(user, "id", None),
            getattr(chat, "type", None),
        )
        if chat and chat.type == ChatType.PRIVATE and update.effective_message:
            await update.effective_message.reply_text("Usuario no autorizado.")
        return False

    async def help_command(self, update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._reply(update, HELP_TEXT)

    async def debug_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Return Telegram's Update JSON without granting administrative access."""
        user = update.effective_user
        chat = update.effective_chat
        if not chat:
            return
        user_id = user.id if user else "no disponible"
        payload = json.dumps(update.to_dict(), ensure_ascii=False, indent=2, default=str)
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
        if len(context.args) not in (2, 3):
            await self._reply(update, "Uso: /account ALIAS USUARIO [LOGIN]")
            return
        async with self.operation_lock:
            try:
                result = await asyncio.to_thread(
                    self.controller.configure_account,
                    context.args[0],
                    context.args[1],
                    context.args[2] if len(context.args) == 3 else None,
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
        async with self.operation_lock:
            try:
                result = await asyncio.to_thread(self.controller.remove_account, context.args[0])
            except Exception as exc:
                await self._reply_error(update, exc)
                return
        await self._reply(update, result)

    async def accounts_command(self, update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._authorized(update):
            return
        await self._reply(update, await asyncio.to_thread(self.controller.accounts_text))

    async def session_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._authorized(update):
            return
        if len(context.args) != 1:
            if len(context.args) > 1 and update.effective_message:
                await self._delete_sensitive_message(update)
            await self._reply(
                update,
                "Uso: /session ALIAS. No pegues el sessionid dentro del comando.",
            )
            return
        try:
            account = await asyncio.to_thread(self.controller.require_account, context.args[0])
        except Exception as exc:
            await self._reply_error(update, exc)
            return
        context.user_data[PENDING_SESSION_KEY] = account.name
        await self._reply(
            update,
            f"Enviá ahora únicamente el valor del sessionid para {account.name}. "
            "Jo Bot intentará borrar ese mensaje apenas lo reciba. /cancel para cancelar.",
        )

    async def text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._authorized(update):
            return
        account_name = context.user_data.pop(PENDING_SESSION_KEY, None)
        if not account_name:
            return
        message = update.effective_message
        session_id = message.text if message else ""
        deleted = await self._delete_sensitive_message(update)
        await context.bot.send_message(
            chat_id=self.admin_user_id,
            text="Validando la sesión con Instagram…",
        )
        async with self.operation_lock:
            try:
                result = await asyncio.to_thread(
                    self.controller.import_session_id,
                    account_name,
                    session_id,
                )
            except Exception as exc:
                await self._send_error(context, exc)
                return
        suffix = "" if deleted else " No pude borrar el mensaje original de Telegram."
        await context.bot.send_message(chat_id=self.admin_user_id, text=result + suffix)

    async def cancel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._authorized(update):
            return
        pending = context.user_data.pop(PENDING_SESSION_KEY, None)
        await self._reply(
            update,
            "Carga de sessionid cancelada." if pending else "No había ninguna operación pendiente.",
        )

    async def check_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._authorized(update):
            return
        if len(context.args) > 1:
            await self._reply(update, "Uso: /check [ALIAS]")
            return
        account_name = context.args[0] if context.args else None
        await self._reply(update, "Iniciando chequeo. El reporte llegará por este chat…")
        async with self.operation_lock:
            try:
                result = await asyncio.to_thread(
                    self.controller.run_check,
                    account_name,
                    if_due=False,
                    telegram_chat_id=(
                        update.effective_chat.id if update.effective_chat else self.admin_user_id
                    ),
                )
            except Exception as exc:
                await self._reply_error(update, exc)
                return
        await self._reply(update, _format_run_result(result))

    async def schedule_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._authorized(update):
            return
        if len(context.args) != 1:
            await self._reply(update, "Uso: /schedule HH:MM")
            return
        try:
            result = await asyncio.to_thread(self.controller.set_schedule, context.args[0])
            self._configure_daily_job(context.application)
        except Exception as exc:
            await self._reply_error(update, exc)
            return
        await self._reply(update, result)

    async def schedule_off_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if not await self._authorized(update):
            return
        result = await asyncio.to_thread(self.controller.disable_schedule)
        self._remove_daily_jobs(context.application)
        await self._reply(update, result)

    async def status_command(self, update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._authorized(update):
            return
        await self._reply(update, await asyncio.to_thread(self.controller.status_text))

    async def scheduled_job(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        async with self.operation_lock:
            try:
                result = await asyncio.to_thread(
                    self.controller.run_check,
                    None,
                    if_due=True,
                )
                self.log.info(
                    "Chequeo automático: completed=%d failed=%d skipped=%s",
                    len(result.completed),
                    len(result.failed),
                    result.skipped,
                )
            except Exception:
                self.log.exception("Falló el trabajo automático de Jo Bot")
                await context.bot.send_message(
                    chat_id=self.admin_user_id,
                    text="Jo Bot: falló el trabajo automático antes de completar el chequeo.",
                )

    def _configure_daily_job(
        self,
        application: Application,
        *,
        include_startup_check: bool = False,
    ) -> None:
        self._remove_daily_jobs(application)
        config = self.controller.load_config()
        if not config.schedule.enabled:
            return
        if application.job_queue is None:
            raise RuntimeError('Instalá el extra "python-telegram-bot[job-queue]".')
        hour, minute = parse_time(config.schedule.time)
        application.job_queue.run_daily(
            self.scheduled_job,
            time(hour, minute, tzinfo=self.controller.timezone),
            name=DAILY_JOB_NAME,
            job_kwargs={"coalesce": True, "max_instances": 1, "misfire_grace_time": 7_200},
        )
        if include_startup_check:
            application.job_queue.run_once(
                self.scheduled_job,
                10,
                name=STARTUP_JOB_NAME,
            )

    @staticmethod
    def _remove_daily_jobs(application: Application) -> None:
        if application.job_queue is None:
            return
        for name in (DAILY_JOB_NAME, STARTUP_JOB_NAME):
            for job in application.job_queue.get_jobs_by_name(name):
                job.schedule_removal()

    async def _delete_sensitive_message(self, update: Update) -> bool:
        if not update.effective_message:
            return False
        try:
            await update.effective_message.delete()
            return True
        except TelegramError:
            self.log.warning("Telegram no permitió borrar un mensaje sensible", exc_info=True)
            return False

    async def _reply_error(self, update: Update, exception: Exception) -> None:
        await self._reply(update, f"Error: {sanitize_text(str(exception))}")

    async def _send_error(self, context: ContextTypes.DEFAULT_TYPE, exception: Exception) -> None:
        await _send_text_or_document(
            context.bot,
            self.admin_user_id,
            f"Error: {sanitize_text(str(exception))}",
            "jo-bot-error.txt",
        )

    async def _reply(self, update: Update, text_value: str) -> None:
        if update.effective_chat:
            await _send_text_or_document(
                update.get_bot(),
                update.effective_chat.id,
                text_value,
                "jo-bot-respuesta.txt",
            )

    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        self.log.error("Error no controlado en Jo Bot", exc_info=context.error)
        try:
            await context.bot.send_message(
                chat_id=self.admin_user_id,
                text=f"Jo Bot: error interno: {sanitize_text(str(context.error))[:3500]}",
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
    await bot.send_document(
        chat_id=chat_id,
        document=document,
        caption=caption,
    )


def _format_run_result(result: RunResult) -> str:
    if result.skipped:
        return "No había chequeos pendientes para hoy."
    lines: list[str] = []
    for completed in result.completed:
        comparison = completed.comparison
        lines.append(
            f"✅ @{comparison.username}: {len(comparison.followers)} seguidores, "
            f"{len(comparison.following)} seguidos."
        )
        for failure in completed.notification_failures:
            lines.append(f"⚠️ Falló {failure.channel}: {sanitize_text(failure.error)}")
    for failure in result.failed:
        lines.append(f"❌ {failure.account_name}: {sanitize_text(failure.error)}")
    return "\n".join(lines) or "El chequeo no produjo resultados."


async def _discover_admin(token: str) -> int:
    print("Enviá /start al bot desde tu chat privado. Esperando el mensaje…")
    offset: int | None = None
    async with Bot(token) as bot:
        await bot.delete_webhook(drop_pending_updates=False)
        while True:
            updates = await bot.get_updates(
                offset=offset,
                timeout=30,
                allowed_updates=["message"],
            )
            for update in updates:
                offset = update.update_id + 1
                if (
                    update.effective_user
                    and update.effective_chat
                    and update.effective_chat.type == ChatType.PRIVATE
                ):
                    user = update.effective_user
                    print(f"JO_BOT_ADMIN_USER_ID={user.id}")
                    return user.id


def _configure_logging(paths: AppPaths) -> None:
    paths.ensure()
    handler = RotatingFileHandler(
        paths.logs / "jo-bot.log",
        maxBytes=2_000_000,
        backupCount=3,
        encoding="utf-8",
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
    parser.add_argument(
        "--discover-admin",
        action="store_true",
        help="Espera un mensaje privado y muestra el user_id que debe autorizarse.",
    )
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
        environment_path = next(
            (candidate for candidate in candidates if candidate.is_file()),
            candidates[0],
        )
    else:
        environment_path = path
    if not environment_path.is_file():
        raise FileNotFoundError(
            f"No se encontró {environment_path}. "
            "Copiá apps/jo-bot/.env.example como apps/jo-bot/.env.local "
            "y configurá tus IDs."
        )
    for line_number, raw_line in enumerate(
        environment_path.read_text(encoding="utf-8-sig").splitlines(),
        start=1,
    ):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        key = key.strip()
        if not separator or not key:
            raise ValueError(f"Línea {line_number} inválida en {environment_path}.")
        os.environ.setdefault(key, value.strip())
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
        print(
            f"Falta un {ADMIN_USER_IDS_ENVIRONMENT_VARIABLE} válido: {exc}. "
            "Usá /debug o jo-bot --discover-admin para conocer cada ID."
        )
        return 2
    timezone_name = os.environ.get(TIMEZONE_ENVIRONMENT_VARIABLE, DEFAULT_TIMEZONE)
    try:
        timezone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        print(f"Zona horaria inválida en {TIMEZONE_ENVIRONMENT_VARIABLE}: {timezone_name}")
        return 2
    paths = app_paths()
    _configure_logging(paths)
    controller = JoBotController(paths, admin_user_ids, timezone)
    application = JoBot(token, controller).build_application()
    application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
