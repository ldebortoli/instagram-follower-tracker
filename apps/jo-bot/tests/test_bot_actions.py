import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from zoneinfo import ZoneInfo

import pytest
from jo_bot import app
from seguidores.paths import AppPaths
from telegram.error import TelegramError


def run_pure(coroutine):
    """All awaited collaborators complete immediately; suspension is a test failure."""
    try:
        with pytest.raises(StopIteration) as completed:
            coroutine.send(None)
        return completed.value.value
    finally:
        coroutine.close()


@pytest.fixture
def bot(tmp_path, monkeypatch):
    controller = app.JoBotController(AppPaths(tmp_path), (1,), ZoneInfo("UTC"))
    instance = app.JoBot("synthetic-token", controller)
    instance.log = Mock()

    async def inline(function, *args):
        return function(*args)

    monkeypatch.setattr(app.asyncio, "to_thread", inline)
    return instance


def update(user=1, chat="private"):
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=user),
        effective_chat=SimpleNamespace(id=1, type=chat),
        effective_message=SimpleNamespace(reply_text=AsyncMock()),
        get_bot=lambda: SimpleNamespace(send_message=AsyncMock()),
    )


def test_controller_lists_and_removes_only_synthetic_profiles(bot):
    controller = bot.controller
    assert "No hay perfiles" in controller.accounts_text()
    controller.configure_account("fixture", "synthetic")
    assert "fixture" in controller.accounts_text()
    assert "eliminado" in controller.remove_account("fixture")
    assert controller.load_config().accounts == []


def test_application_builder_wires_handlers_without_starting_any_bot(bot, monkeypatch):
    application = Mock()
    builder = Mock()
    for name in ("token", "defaults", "concurrent_updates", "post_init"):
        getattr(builder, name).return_value = builder
    builder.build.return_value = application
    monkeypatch.setattr(app, "ApplicationBuilder", lambda: builder)
    assert bot.build_application() is application
    assert application.add_handler.call_count == 7
    application.add_error_handler.assert_called_once_with(bot.error_handler)
    telegram = SimpleNamespace(set_my_commands=AsyncMock())
    run_pure(bot.post_init(SimpleNamespace(bot=telegram)))
    assert [command.command for command in telegram.set_my_commands.call_args.args[0]] == [
        "start",
        "status",
        "accounts",
        "account",
        "debug",
        "help",
    ]


@pytest.mark.parametrize("chat", ["private", "group"])
def test_unauthorized_commands_never_modify_config(bot, chat):
    event = update(user=2, chat=chat)
    assert run_pure(bot._authorized(event)) is False
    assert event.effective_message.reply_text.await_count == (chat == "private")
    for command in (bot.account_command, bot.remove_command):
        run_pure(command(event, SimpleNamespace(args=[])))
    assert not bot.controller.paths.config.exists()


def test_admin_commands_and_errors_use_only_async_doubles(bot, monkeypatch):
    event = update()
    reply = AsyncMock()
    monkeypatch.setattr(bot, "_reply", reply)
    context = SimpleNamespace(args=[])
    run_pure(bot.account_command(event, context))
    assert "Uso: /account" in reply.call_args.args[1]
    context.args = ["fixture", "synthetic"]
    run_pure(bot.account_command(event, context))
    assert "configurado" in reply.call_args.args[1]
    run_pure(bot.accounts_command(event, None))
    assert "fixture" in reply.call_args.args[1]
    run_pure(bot.status_command(event, None))
    assert "desactivado" in reply.call_args.args[1]
    context.args = []
    run_pure(bot.remove_command(event, context))
    assert "Uso: /remove" in reply.call_args.args[1]
    context.args = ["fixture"]
    run_pure(bot.remove_command(event, context))
    assert "eliminado" in reply.call_args.args[1]
    run_pure(bot.remove_command(event, context))
    assert reply.call_args.args[1].startswith("Error:")
    context.args = ["invalid!", "synthetic"]
    run_pure(bot.account_command(event, context))
    assert reply.call_args.args[1].startswith("Error:")
    run_pure(bot.help_command(event, None))
    assert reply.call_args.args[1] == app.HELP_TEXT


def test_debug_and_reply_handle_absent_chat_and_unknown_user(bot, monkeypatch):
    empty = SimpleNamespace(effective_user=None, effective_chat=None)
    run_pure(bot.debug_command(empty, None))
    run_pure(bot._reply(empty, "fixture"))
    send = AsyncMock()
    monkeypatch.setattr(app, "_send_text_or_document", send)
    event = SimpleNamespace(
        effective_user=None, effective_chat=SimpleNamespace(id=1), to_dict=lambda: {"fixture": True}
    )
    run_pure(bot.debug_command(event, SimpleNamespace(bot=Mock())))
    assert "no disponible" in send.call_args.args[2]
    run_pure(bot._reply(update(), "fixture"))
    assert send.call_args.args[2] == "fixture"


def test_error_handler_uses_fake_transport_including_telegram_failure(bot):
    telegram = SimpleNamespace(send_message=AsyncMock())
    context = SimpleNamespace(bot=telegram, error=RuntimeError("synthetic failure"))
    run_pure(bot.error_handler(None, context))
    assert telegram.send_message.call_args.kwargs["chat_id"] == 1
    telegram.send_message.side_effect = TelegramError("synthetic transport failure")
    run_pure(bot.error_handler(None, context))
    bot.log.exception.assert_called_once()


def test_admin_discovery_uses_only_fake_updates(monkeypatch, capsys):
    telegram = SimpleNamespace(
        delete_webhook=AsyncMock(),
        get_updates=AsyncMock(
            side_effect=[
                [SimpleNamespace(update_id=1, effective_user=None, effective_chat=None)],
                [
                    SimpleNamespace(
                        update_id=2,
                        effective_user=SimpleNamespace(id=1),
                        effective_chat=SimpleNamespace(type="private"),
                    )
                ],
            ]
        ),
    )
    manager = Mock()
    manager.__aenter__ = AsyncMock(return_value=telegram)
    manager.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr(app, "Bot", lambda _token: manager)
    assert run_pure(app._discover_admin("synthetic-token")) == 1
    assert telegram.get_updates.call_args.kwargs["offset"] == 2
    assert "JO_BOT_ADMIN_USER_ID=1" in capsys.readouterr().out


@pytest.mark.parametrize("value", ["invalid", "0", "-1"])
def test_admin_ids_reject_non_numeric_and_non_positive_values(value, monkeypatch):
    monkeypatch.setenv(app.ADMIN_USER_IDS_ENVIRONMENT_VARIABLE, value)
    with pytest.raises(ValueError):
        app._parse_admin_user_ids()


def test_environment_loader_stays_in_synthetic_workdir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(FileNotFoundError):
        app._load_local_environment()
    path = tmp_path / ".env.local"
    path.write_text("\n# fixture\nSEGUIDORES_TEST_ONLY=value\n")
    monkeypatch.delenv("SEGUIDORES_TEST_ONLY", raising=False)
    assert app._load_local_environment() == path
    monkeypatch.delenv("SEGUIDORES_TEST_ONLY")
    for invalid in ("missing separator", "=value"):
        path.write_text(invalid)
        with pytest.raises(ValueError, match="inválida"):
            app._load_local_environment()
    monkeypatch.delenv("SEGUIDORES_TEST_ONLY", raising=False)


def test_local_launcher_reports_invalid_env_without_starting_bot(monkeypatch):
    monkeypatch.setattr(app, "_load_local_environment", Mock(side_effect=ValueError("fixture")))
    assert app.local_main() == 2
    monkeypatch.setattr(app, "_load_local_environment", Mock())
    monkeypatch.setattr(app, "main", lambda: 37)
    assert app.local_main() == 37


def test_main_validation_and_polling_configuration_use_only_fakes(tmp_path, monkeypatch):
    monkeypatch.setattr(app, "get_telegram_token", lambda: None)
    assert app.main([]) == 2
    monkeypatch.setattr(app, "get_telegram_token", lambda: "synthetic-token")
    monkeypatch.setenv(app.ADMIN_USER_IDS_ENVIRONMENT_VARIABLE, "invalid")
    assert app.main([]) == 2
    monkeypatch.setenv(app.ADMIN_USER_IDS_ENVIRONMENT_VARIABLE, "1")
    monkeypatch.setenv(app.TIMEZONE_ENVIRONMENT_VARIABLE, "Not/A_Real_Zone")
    assert app.main([]) == 2
    monkeypatch.setenv(app.TIMEZONE_ENVIRONMENT_VARIABLE, "UTC")
    monkeypatch.setattr(app, "app_paths", lambda: AppPaths(tmp_path))
    monkeypatch.setattr(app, "_configure_logging", Mock())
    application = Mock()
    monkeypatch.setattr(
        app, "JoBot", lambda *_args: SimpleNamespace(build_application=lambda: application)
    )
    assert app.main([]) == 0
    application.run_polling.assert_called_once_with(
        allowed_updates=app.Update.ALL_TYPES, drop_pending_updates=False
    )
    discover = Mock(return_value=1)

    def fake_run(coroutine):
        coroutine.close()
        return discover()

    monkeypatch.setattr(app.asyncio, "run", fake_run)
    assert app.main(["--discover-admin"]) == 0
    discover.assert_called_once()


def test_logging_uses_fake_handler_and_main_guards_use_version_only(tmp_path, monkeypatch):
    handler, logger = Mock(), Mock(handlers=[])
    monkeypatch.setattr(app, "RotatingFileHandler", lambda *_args, **_kwargs: handler)
    real_get_logger = app.logging.getLogger
    monkeypatch.setattr(
        app.logging,
        "getLogger",
        lambda name=None: logger if name in {"seguidores", "httpx"} else real_get_logger(name),
    )
    app._configure_logging(AppPaths(tmp_path))
    logger.addHandler.assert_called_once_with(handler)
    logger.handlers = [handler]
    app._configure_logging(AppPaths(tmp_path))
    monkeypatch.setattr(sys, "argv", ["jo-bot-fixture", "--version"])
    source = Path(app.__file__)
    with pytest.raises(SystemExit) as stopped:
        exec(
            compile(source.read_bytes(), str(source), "exec"),
            {"__name__": "__main__", "__file__": str(source)},
        )
    assert stopped.value.code == 0


def test_bot_module_entry_preserves_exit_code_without_starting_bot(monkeypatch):
    import runpy

    main = Mock(return_value=37)
    monkeypatch.setattr(app, "main", main)
    with pytest.raises(SystemExit) as stopped:
        runpy.run_module("jo_bot", run_name="__main__")
    assert stopped.value.code == 37
