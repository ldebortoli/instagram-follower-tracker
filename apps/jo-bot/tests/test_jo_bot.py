import asyncio
import os
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

from jo_bot.app import (
    ADMIN_USER_ID_ENVIRONMENT_VARIABLE,
    ADMIN_USER_IDS_ENVIRONMENT_VARIABLE,
    JoBot,
    JoBotController,
    _load_local_environment,
    _parse_admin_user_ids,
    _send_text_or_document,
)
from seguidores.app import RunResult
from seguidores.paths import AppPaths
from telegram import Chat, Message, Update, User


def controller(tmp_path, admin_user_ids=(267832653,)):
    return JoBotController(
        AppPaths(tmp_path),
        admin_user_ids,
        ZoneInfo("America/Argentina/Buenos_Aires"),
    )


def test_controller_configures_account_and_primary_telegram_chat(tmp_path):
    jo = controller(tmp_path, (267832653, 123456789))

    message = jo.configure_account("personal", "@target", "@login")
    config = jo.load_config()

    assert "Cuenta personal configurada" in message
    assert config.account("personal").username == "target"
    assert config.account("personal").login_username == "login"
    assert config.notifications.popup is False
    assert config.notifications.telegram.enabled is True
    assert config.notifications.telegram.chat_id == "267832653"


def test_manual_check_routes_full_report_to_requesting_admin(tmp_path, monkeypatch):
    jo = controller(tmp_path, (267832653, 123456789))
    jo.configure_account("personal", "target")
    captured = {}

    class FakeTracker:
        def __init__(self, paths, config):
            captured["chat_id"] = config.notifications.telegram.chat_id

        def run(self, **options):
            captured["options"] = options
            return RunResult((), ())

    monkeypatch.setattr("jo_bot.app.Tracker", FakeTracker)

    jo.run_check("personal", telegram_chat_id=123456789)

    assert captured["chat_id"] == "123456789"
    assert captured["options"]["account_name"] == "personal"


def test_admin_ids_accept_any_quantity_and_remove_duplicates(monkeypatch):
    monkeypatch.setenv(
        ADMIN_USER_IDS_ENVIRONMENT_VARIABLE,
        "267832653,793942836,123456789,793942836",
    )
    assert _parse_admin_user_ids() == (267832653, 793942836, 123456789)


def test_legacy_single_admin_variable_still_works(monkeypatch):
    monkeypatch.delenv(ADMIN_USER_IDS_ENVIRONMENT_VARIABLE, raising=False)
    monkeypatch.setenv(ADMIN_USER_ID_ENVIRONMENT_VARIABLE, "267832653")
    assert _parse_admin_user_ids() == (267832653,)


def test_jobot_loads_local_environment_file(tmp_path, monkeypatch):
    environment_file = tmp_path / ".env.local"
    environment_file.write_text(
        "# configuración local\n"
        "JO_BOT_ADMIN_USER_IDS=267832653,123456789\n"
        "JO_BOT_TIMEZONE=America/Argentina/Buenos_Aires\n",
        encoding="utf-8",
    )
    monkeypatch.delenv(ADMIN_USER_IDS_ENVIRONMENT_VARIABLE, raising=False)
    monkeypatch.chdir(tmp_path)

    loaded = _load_local_environment()

    assert loaded == environment_file
    assert os.environ[ADMIN_USER_IDS_ENVIRONMENT_VARIABLE] == "267832653,123456789"


def test_every_configured_user_is_authorized(tmp_path):
    bot = JoBot(
        "123456:token",
        controller(tmp_path, (267832653, 793942836, 123456789)),
    )
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=123456789),
        effective_chat=SimpleNamespace(type="private"),
        effective_message=SimpleNamespace(reply_text=AsyncMock()),
    )

    assert asyncio.run(bot._authorized(update)) is True


def test_debug_is_public_in_groups_and_does_not_notify_primary(tmp_path):
    bot = JoBot("123456:token", controller(tmp_path))
    telegram_bot = SimpleNamespace(send_message=AsyncMock(), send_document=AsyncMock())
    user = User(id=987654321, first_name="Invitado", is_bot=False, username="guest")
    chat = Chat(id=-100123456789, type="supergroup", title="Pruebas")
    message = Message(
        message_id=5,
        date=datetime(2026, 6, 29, tzinfo=UTC),
        chat=chat,
        from_user=user,
        text="/debug",
    )
    update = Update(update_id=10, message=message)
    context = SimpleNamespace(bot=telegram_bot)

    asyncio.run(bot.debug_command(update, context))

    telegram_bot.send_message.assert_awaited_once()
    call = telegram_bot.send_message.await_args.kwargs
    assert call["chat_id"] == -100123456789
    assert '"id": 987654321' in call["text"]
    telegram_bot.send_document.assert_not_awaited()


def test_large_debug_response_is_sent_as_txt(tmp_path):
    bot = JoBot("123456:token", controller(tmp_path))
    telegram_bot = SimpleNamespace(send_message=AsyncMock(), send_document=AsyncMock())
    user = User(id=987654321, first_name="Invitado", is_bot=False)
    chat = Chat(id=-12345, type="group", title="Pruebas")
    message = Message(
        message_id=5,
        date=datetime(2026, 6, 29, tzinfo=UTC),
        chat=chat,
        from_user=user,
        text="/debug " + ("x" * 5000),
    )
    update = Update(update_id=10, message=message)

    asyncio.run(bot.debug_command(update, SimpleNamespace(bot=telegram_bot)))

    telegram_bot.send_message.assert_not_awaited()
    call = telegram_bot.send_document.await_args.kwargs
    assert call["chat_id"] == -12345
    assert call["document"].name == "jo-bot-debug-update.txt"


def test_help_and_start_are_public(tmp_path):
    bot = JoBot("123456:token", controller(tmp_path))
    bot._reply = AsyncMock()
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=987654321),
        effective_chat=SimpleNamespace(type="group"),
    )

    asyncio.run(bot.help_command(update, SimpleNamespace()))

    bot._reply.assert_awaited_once()


def test_long_bot_message_is_attached_as_text_document():
    telegram_bot = SimpleNamespace(send_message=AsyncMock(), send_document=AsyncMock())

    asyncio.run(
        _send_text_or_document(
            telegram_bot,
            267832653,
            "x" * 4001,
            "reporte.txt",
            caption="Detalle",
        )
    )

    telegram_bot.send_message.assert_not_awaited()
    call = telegram_bot.send_document.await_args.kwargs
    assert call["chat_id"] == 267832653
    assert call["document"].name == "reporte.txt"
    assert call["caption"] == "Detalle"
