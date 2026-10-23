import os
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest
from jo_bot.app import (
    ADMIN_USER_ID_ENVIRONMENT_VARIABLE,
    ADMIN_USER_IDS_ENVIRONMENT_VARIABLE,
    JoBot,
    JoBotController,
    _load_local_environment,
    _parse_admin_user_ids,
    _send_text_or_document,
)
from seguidores.paths import AppPaths
from telegram import Chat, Message, Update, User


def run_without_io(coroutine):
    """Evaluate pure coroutine units; fail if they require an event loop or IO."""
    try:
        try:
            coroutine.send(None)
        except StopIteration as completed:
            return completed.value
        raise AssertionError(
            "Unit coroutine unexpectedly suspended; replace IO with a test double."
        )
    finally:
        coroutine.close()


def test_pure_coroutine_runner_rejects_unmocked_suspension():
    class Suspends:
        def __await__(self):
            yield "unexpected IO"

    async def unexpected_io():
        await Suspends()

    with pytest.raises(AssertionError, match="unexpectedly suspended"):
        run_without_io(unexpected_io())


def controller(tmp_path, admin_user_ids=(267832653,)):
    return JoBotController(
        AppPaths(tmp_path), admin_user_ids, ZoneInfo("America/Argentina/Buenos_Aires")
    )


def test_controller_configures_profile_without_session(tmp_path):
    jo = controller(tmp_path)

    message = jo.configure_account("personal", "@target")
    config = jo.load_config()

    assert "Perfil personal configurado" in message
    assert config.account("personal").username == "target"


def test_status_confirms_direct_access_and_schedule_are_disabled(tmp_path):
    status = controller(tmp_path).status_text()

    assert "Acceso directo a Instagram: desactivado" in status
    assert "Chequeos diarios: desactivados" in status


def test_admin_ids_accept_any_quantity_and_remove_duplicates(monkeypatch):
    monkeypatch.setenv(
        ADMIN_USER_IDS_ENVIRONMENT_VARIABLE, "267832653,793942836,123456789,793942836"
    )
    assert _parse_admin_user_ids() == (267832653, 793942836, 123456789)


def test_legacy_single_admin_variable_still_works(monkeypatch):
    monkeypatch.delenv(ADMIN_USER_IDS_ENVIRONMENT_VARIABLE, raising=False)
    monkeypatch.setenv(ADMIN_USER_ID_ENVIRONMENT_VARIABLE, "267832653")
    assert _parse_admin_user_ids() == (267832653,)


def test_jobot_loads_local_environment_file(tmp_path, monkeypatch):
    environment_file = tmp_path / ".env.local"
    environment_file.write_text("JO_BOT_ADMIN_USER_IDS=267832653,123456789\n", encoding="utf-8")
    monkeypatch.delenv(ADMIN_USER_IDS_ENVIRONMENT_VARIABLE, raising=False)

    loaded = _load_local_environment(environment_file)

    assert loaded == environment_file
    assert os.environ[ADMIN_USER_IDS_ENVIRONMENT_VARIABLE] == "267832653,123456789"


def test_every_configured_user_is_authorized(tmp_path):
    bot = JoBot("123456:token", controller(tmp_path, (267832653, 793942836)))
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=793942836),
        effective_chat=SimpleNamespace(type="private"),
        effective_message=SimpleNamespace(reply_text=AsyncMock()),
    )

    assert run_without_io(bot._authorized(update)) is True


def test_debug_is_public_in_groups(tmp_path):
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

    run_without_io(bot.debug_command(update, SimpleNamespace(bot=telegram_bot)))

    call = telegram_bot.send_message.await_args.kwargs
    assert call["chat_id"] == -100123456789
    assert '"id": 987654321' in call["text"]


def test_long_bot_message_is_attached_as_text_document():
    telegram_bot = SimpleNamespace(send_message=AsyncMock(), send_document=AsyncMock())

    run_without_io(
        _send_text_or_document(
            telegram_bot, 267832653, "x" * 4001, "reporte.txt", caption="Detalle"
        )
    )

    call = telegram_bot.send_document.await_args.kwargs
    assert call["document"].name == "reporte.txt"
    assert call["caption"] == "Detalle"
