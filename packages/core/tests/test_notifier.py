import urllib.parse
from datetime import UTC, datetime

from seguidores.config import NotificationConfig, TelegramConfig
from seguidores.models import SocialGraph, compare_graphs
from seguidores.notifier import (
    TELEGRAM_TEXT_LIMIT,
    NotificationFailure,
    notify,
    notify_automatic_failure,
    send_telegram,
)


class FakeTelegramResponse:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def test_short_telegram_report_is_sent_as_text(monkeypatch):
    requests = []

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return FakeTelegramResponse()

    monkeypatch.setattr("seguidores.notifier.urllib.request.urlopen", fake_urlopen)

    send_telegram("bot-token", "@alerts", "reporte breve")

    request, timeout = requests[0]
    assert request.full_url.endswith("/sendMessage")
    assert urllib.parse.parse_qs(request.data.decode()) == {
        "chat_id": ["@alerts"],
        "text": ["reporte breve"],
    }
    assert timeout == 30


def test_long_telegram_report_is_sent_as_complete_text_document(monkeypatch):
    requests = []
    message = "á" * (TELEGRAM_TEXT_LIMIT + 1)

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return FakeTelegramResponse()

    monkeypatch.setattr("seguidores.notifier.urllib.request.urlopen", fake_urlopen)

    send_telegram(
        "bot-token",
        "@alerts",
        message,
        document_caption="Reporte de seguidores de @owner",
    )

    request, timeout = requests[0]
    body = request.data.decode("utf-8")
    assert request.full_url.endswith("/sendDocument")
    assert request.headers["Content-type"].startswith("multipart/form-data; boundary=")
    assert 'name="document"; filename="seguidores-reporte.txt"' in body
    assert "Reporte de seguidores de @owner" in body
    assert message in body
    assert timeout == 30


def test_telegram_notification_includes_every_account_in_document_report(monkeypatch):
    sent = []
    config = NotificationConfig(
        popup=False,
        telegram=TelegramConfig(enabled=True, chat_id="@alerts"),
    )
    comparison = compare_graphs(
        account_name="personal",
        username="owner",
        current=SocialGraph.from_iterables([], [f"account{index:03d}" for index in range(75)]),
        previous=None,
        captured_at=datetime(2026, 6, 29, 12, tzinfo=UTC),
    )
    monkeypatch.setattr("seguidores.notifier.get_telegram_token", lambda: "bot-token")
    monkeypatch.setattr(
        "seguidores.notifier.send_telegram",
        lambda token, chat_id, message, **options: sent.append((token, chat_id, message, options)),
    )

    failures = notify(comparison, config)

    assert failures == []
    assert "@account074" in sent[0][2]
    assert "… y 25 más" not in sent[0][2]
    assert "Reporte de seguidores de @owner" in sent[0][3]["document_caption"]
    assert "Incluye seguidores, seguidos" in sent[0][3]["document_caption"]


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
