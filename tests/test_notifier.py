from datetime import UTC, datetime

from seguidores.config import NotificationConfig, TelegramConfig
from seguidores.notifier import NotificationFailure, notify_automatic_failure


def test_automatic_failure_is_sent_to_telegram_without_secrets(monkeypatch):
    config = NotificationConfig(
        popup=False,
        telegram=TelegramConfig(enabled=True, chat_id="@alerts"),
    )
    sent = []
    monkeypatch.setattr("seguidores.notifier.get_telegram_token", lambda: "bot-secret")
    monkeypatch.setattr(
        "seguidores.notifier.send_telegram",
        lambda token, chat_id, message: sent.append((token, chat_id, message)),
    )

    failure = notify_automatic_failure(
        [("personal", "HTTP 401 sessionid=account-secret")],
        config,
        datetime(2026, 6, 29, 12, tzinfo=UTC),
    )

    assert failure is None
    assert sent[0][0:2] == ("bot-secret", "@alerts")
    assert "ejecución automática fallida" in sent[0][2]
    assert "HTTP 401" in sent[0][2]
    assert "account-secret" not in sent[0][2]


def test_automatic_failure_records_a_telegram_delivery_error(monkeypatch):
    config = NotificationConfig(
        popup=False,
        telegram=TelegramConfig(enabled=True, chat_id="@alerts"),
    )
    monkeypatch.setattr("seguidores.notifier.get_telegram_token", lambda: "bot-secret")

    def fail(*_args):
        raise RuntimeError("Telegram offline")

    monkeypatch.setattr("seguidores.notifier.send_telegram", fail)

    failure = notify_automatic_failure(
        [("personal", "Instagram unavailable")],
        config,
        datetime(2026, 6, 29, 12, tzinfo=UTC),
    )

    assert failure == NotificationFailure("telegram", "Telegram offline")
