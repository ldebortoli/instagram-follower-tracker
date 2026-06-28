from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from seguidores.config import NotificationConfig
from seguidores.models import Comparison
from seguidores.report import format_popup, format_report

KEYRING_SERVICE = "seguidores-instagram"
KEYRING_USERNAME = "telegram-bot-token"
TOKEN_ENVIRONMENT_VARIABLE = "SEGUIDORES_TELEGRAM_BOT_TOKEN"


class NotificationError(RuntimeError):
    pass


@dataclass(frozen=True)
class NotificationFailure:
    channel: str
    error: str


def notify(comparison: Comparison, config: NotificationConfig) -> list[NotificationFailure]:
    if (
        not comparison.is_baseline
        and not comparison.has_changes
        and not config.notify_without_changes
    ):
        return []

    failures: list[NotificationFailure] = []
    if config.popup:
        try:
            send_popup("Seguidores de Instagram", format_popup(comparison))
        except Exception as exc:
            failures.append(NotificationFailure("popup", str(exc)))
    if config.telegram.enabled:
        try:
            token = get_telegram_token()
            if not token:
                raise NotificationError(
                    "No hay token. Ejecutá 'seguidores telegram configure --chat-id ...'."
                )
            send_telegram(token, config.telegram.chat_id, format_report(comparison))
        except Exception as exc:
            failures.append(NotificationFailure("telegram", str(exc)))
    return failures


def send_popup(title: str, message: str) -> None:
    if sys.platform == "win32":
        try:
            result = ctypes.windll.user32.MessageBoxTimeoutW(None, message, title, 0x40, 0, 30_000)
        except AttributeError:
            result = ctypes.windll.user32.MessageBoxW(None, message, title, 0x40)
        if result == 0:
            raise NotificationError("Windows no pudo mostrar la notificación.")
        return
    if sys.platform == "darwin":
        script = (
            "display notification " + _apple_quote(message) + " with title " + _apple_quote(title)
        )
        _run_notification(["osascript", "-e", script])
        return
    _run_notification(["notify-send", title, message])


def _apple_quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _run_notification(command: list[str]) -> None:
    try:
        subprocess.run(command, check=True, capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError) as exc:
        raise NotificationError(f"No se pudo mostrar el popup: {exc}") from exc


def send_telegram(token: str, chat_id: str, message: str) -> None:
    if not chat_id:
        raise NotificationError("Falta el chat_id o @alias del canal de Telegram.")
    for chunk in _telegram_chunks(message):
        payload = urllib.parse.urlencode({"chat_id": chat_id, "text": chunk}).encode()
        request = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                if response.status != 200:
                    raise NotificationError(f"Telegram respondió HTTP {response.status}.")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise NotificationError(f"Telegram respondió HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise NotificationError(f"No se pudo contactar Telegram: {exc.reason}") from exc


def _telegram_chunks(message: str, limit: int = 4000) -> list[str]:
    chunks: list[str] = []
    current = ""
    for line in message.splitlines():
        line_chunks = [line[index : index + limit] for index in range(0, len(line), limit)] or [""]
        for part in line_chunks:
            candidate = f"{current}\n{part}" if current else part
            if len(candidate) > limit:
                chunks.append(current)
                current = part
            else:
                current = candidate
    if current or not chunks:
        chunks.append(current)
    return chunks


def set_telegram_token(token: str) -> None:
    if not token.strip():
        raise NotificationError("El token no puede estar vacío.")
    try:
        import keyring

        keyring.set_password(KEYRING_SERVICE, KEYRING_USERNAME, token.strip())
    except Exception as exc:
        raise NotificationError(
            "El almacén seguro del sistema no aceptó el token. "
            f"Podés usar {TOKEN_ENVIRONMENT_VARIABLE}. Detalle: {exc}"
        ) from exc


def get_telegram_token() -> str | None:
    if value := os.environ.get(TOKEN_ENVIRONMENT_VARIABLE):
        return value
    try:
        import keyring

        return keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME)
    except Exception as exc:
        raise NotificationError(f"No se pudo leer el token del almacén seguro: {exc}") from exc


def delete_telegram_token() -> None:
    try:
        import keyring

        if keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME):
            keyring.delete_password(KEYRING_SERVICE, KEYRING_USERNAME)
    except Exception as exc:
        raise NotificationError(f"No se pudo borrar el token: {exc}") from exc
