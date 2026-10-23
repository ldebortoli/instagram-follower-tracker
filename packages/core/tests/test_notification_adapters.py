import ctypes
import io
import sys
import urllib.error
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import Mock

import keyring
import pytest
from seguidores import notifier
from seguidores.config import NotificationConfig
from seguidores.models import SocialGraph, compare_graphs

REAL_POPUP = notifier.send_popup


@pytest.fixture(autouse=True)
def no_native_windows_loader(monkeypatch):
    monkeypatch.delattr(ctypes, "windll", raising=False)


def test_unchanged_capture_can_suppress_all_notifications():
    graph = SocialGraph.from_iterables(["fixture"], [])
    comparison = compare_graphs(
        account_name="fixture",
        username="fixture",
        current=graph,
        previous=graph,
        captured_at=datetime.now(UTC),
    )
    assert notifier.notify(comparison, NotificationConfig(notify_without_changes=False)) == []


def test_popup_failure_is_returned_without_hiding_other_channels(monkeypatch):
    graph = SocialGraph.from_iterables(["fixture"], [])
    comparison = compare_graphs(
        account_name="fixture",
        username="fixture",
        current=graph,
        previous=None,
        captured_at=datetime.now(UTC),
    )
    popup = Mock(side_effect=OSError("synthetic popup failure"))
    monkeypatch.setattr(notifier, "send_popup", popup)
    failures = notifier.notify(comparison, NotificationConfig())
    assert [(failure.channel, failure.error) for failure in failures] == [
        ("popup", "synthetic popup failure")
    ]


@pytest.mark.parametrize("fallback,result", [(False, 1), (True, 1), (False, 0)])
def test_windows_popup_calls_only_fake_user32(fallback, result, monkeypatch):
    user32 = SimpleNamespace(MessageBoxW=Mock(return_value=result))
    if not fallback:
        user32.MessageBoxTimeoutW = Mock(return_value=result)
    monkeypatch.setattr(ctypes, "windll", SimpleNamespace(user32=user32), raising=False)
    monkeypatch.setattr(sys, "platform", "win32")
    if result:
        REAL_POPUP("fixture", "synthetic")
    else:
        with pytest.raises(notifier.NotificationError):
            REAL_POPUP("fixture", "synthetic")
    method = user32.MessageBoxW if fallback else user32.MessageBoxTimeoutW
    method.assert_called_once()


@pytest.mark.parametrize("platform,executable", [("darwin", "osascript"), ("linux", "notify-send")])
def test_popup_command_is_quoted_and_never_spawned(platform, executable, monkeypatch):
    run = Mock()
    monkeypatch.setattr(sys, "platform", platform)
    monkeypatch.setattr(notifier.subprocess, "run", run)
    REAL_POPUP('fixture"', 'message\\"')
    assert run.call_args.args[0][0] == executable
    assert run.call_args.kwargs["timeout"] == 15
    run.side_effect = OSError("synthetic command failure")
    with pytest.raises(notifier.NotificationError):
        notifier._run_notification(["synthetic"])


@pytest.mark.parametrize(
    "failure",
    [
        SimpleNamespace(status=503),
        urllib.error.HTTPError(
            "https://offline.invalid", 403, "denied", {}, io.BytesIO(b"fixture")
        ),
        urllib.error.URLError("synthetic unavailable"),
    ],
)
def test_telegram_transport_failures_use_only_fake_responses(failure, monkeypatch):
    response = Mock()
    response.__enter__ = Mock(return_value=failure)
    response.__exit__ = Mock(return_value=False)
    open_url = (
        Mock(side_effect=failure) if isinstance(failure, Exception) else Mock(return_value=response)
    )
    monkeypatch.setattr(notifier.urllib.request, "urlopen", open_url)
    with pytest.raises(notifier.NotificationError):
        notifier.send_telegram("synthetic", "fixture", "message")
    with pytest.raises(notifier.NotificationError, match="chat_id"):
        notifier.send_telegram("synthetic", "", "message")


def test_credential_adapters_use_only_fixture_keyring(monkeypatch):
    with pytest.raises(notifier.NotificationError, match="vacío"):
        notifier.set_telegram_token(" ")
    notifier.set_telegram_token(" synthetic-only ")
    assert notifier.get_telegram_token() == "synthetic-only"
    notifier.delete_telegram_token()
    assert notifier.get_telegram_token() is None
    monkeypatch.setenv(notifier.TOKEN_ENVIRONMENT_VARIABLE, "synthetic-env")
    assert notifier.get_telegram_token() == "synthetic-env"
    monkeypatch.delenv(notifier.TOKEN_ENVIRONMENT_VARIABLE)
    for method, call in (
        ("set_password", lambda: notifier.set_telegram_token("fixture")),
        ("get_password", notifier.get_telegram_token),
        ("get_password", notifier.delete_telegram_token),
    ):
        with monkeypatch.context() as patch:
            patch.setattr(
                keyring, method, Mock(side_effect=RuntimeError("synthetic keyring error"))
            )
            with pytest.raises(notifier.NotificationError):
                call()
