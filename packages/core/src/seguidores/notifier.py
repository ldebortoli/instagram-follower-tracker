from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import datetime

from seguidores.config import NotificationConfig
from seguidores.http_diagnostics import sanitize_text
from seguidores.models import Comparison
from seguidores.report import format_popup, format_report

KEYRING_SERVICE = "seguidores-instagram"
KEYRING_USERNAME = "telegram-bot-token"
TOKEN_ENVIRONMENT_VARIABLE = "SEGUIDORES_TELEGRAM_BOT_TOKEN"
AUTOMATIC_ERROR_MESSAGE_LIMIT = 3_800
TELEGRAM_TEXT_LIMIT = 4_000
TELEGRAM_REPORT_FILENAME = "seguidores-reporte.txt"


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
            send_telegram(
                token,
                config.telegram.chat_id,
                format_report(comparison, max_names_per_section=None),
                document_caption=(
                    f"Reporte de seguidores de @{comparison.username}\n"
                    f"Chequeo: {comparison.captured_at.astimezone():%Y-%m-%d %H:%M %Z}\n"
                    "Incluye seguidores, seguidos y diferencias entre ambas listas."
                ),
            )
        except Exception as exc:
            failures.append(NotificationFailure("telegram", str(exc)))
    return failures


def notify_automatic_failure(
    errors: list[tuple[str, str]],
    config: NotificationConfig,
    occurred_at: datetime,
) -> NotificationFailure | None:
    if not config.telegram.enabled:
        return None
    try:
        token = get_telegram_token()
        if not token:
            raise NotificationError("No hay token para avisar el error de la ejecución automática.")
        send_telegram(
            token,
            config.telegram.chat_id,
            _format_automatic_failure(errors, occurred_at),
        )
    except Exception as exc:
        return NotificationFailure("telegram", str(exc))
    return None


def _format_automatic_failure(errors: list[tuple[str, str]], occurred_at: datetime) -> str:
    parts = [
        "🚨 Seguidores: ejecución automática fallida",
        f"Hora: {occurred_at.astimezone():%Y-%m-%d %H:%M %Z}",
    ]
    for account_name, error in errors:
        parts.append(f"\nCuenta/etapa: {account_name}\n{sanitize_text(error.strip())}")
    message = "\n".join(parts)
    suffix = "\n\nDetalle completo disponible en el log local."
    if len(message) + len(suffix) > AUTOMATIC_ERROR_MESSAGE_LIMIT:
        message = message[: AUTOMATIC_ERROR_MESSAGE_LIMIT - len(suffix) - 1] + "…"
    return message + suffix


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


def send_telegram(
    token: str,
    chat_id: str,
    message: str,
    *,
    document_caption: str | None = None,
) -> None:
    if not chat_id:
        raise NotificationError("Falta el chat_id o @alias del canal de Telegram.")
    if len(message) <= TELEGRAM_TEXT_LIMIT:
        payload = urllib.parse.urlencode({"chat_id": chat_id, "text": message}).encode()
        request = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
    else:
        boundary = f"seguidores-{uuid.uuid4().hex}"
        payload = _telegram_document_payload(
            boundary,
            chat_id,
            message,
            document_caption or "Seguidores: reporte completo adjunto.",
        )
        request = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendDocument",
            data=payload,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )
    _send_telegram_request(request)


def _telegram_document_payload(
    boundary: str,
    chat_id: str,
    message: str,
    caption: str,
) -> bytes:
    prefix = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="chat_id"\r\n\r\n'
        f"{chat_id}\r\n"
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="caption"\r\n\r\n'
        f"{caption[:1000]}\r\n"
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="document"; '
        f'filename="{TELEGRAM_REPORT_FILENAME}"\r\n'
        "Content-Type: text/plain; charset=utf-8\r\n\r\n"
    ).encode()
    suffix = f"\r\n--{boundary}--\r\n".encode()
    return prefix + message.encode("utf-8") + suffix


def _send_telegram_request(request: urllib.request.Request) -> None:
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            if response.status != 200:
                raise NotificationError(f"Telegram respondió HTTP {response.status}.")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise NotificationError(f"Telegram respondió HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise NotificationError(f"No se pudo contactar Telegram: {exc.reason}") from exc


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
