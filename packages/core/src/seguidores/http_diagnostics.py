from __future__ import annotations

import json
import re
from collections import deque
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

REDACTED = "<redacted>"
MAX_BODY_LENGTH = 4_000
SENSITIVE_PARTS = (
    "authorization",
    "cookie",
    "password",
    "passwd",
    "secret",
    "session",
    "token",
    "csrf",
    "verification",
    "two_factor",
    "claim",
)


@dataclass(frozen=True)
class HttpExchange:
    method: str
    url: str
    request_headers: dict[str, str]
    request_body: str
    status_code: int | None
    reason: str
    response_headers: dict[str, str]
    response_body: str


class RequestRecorder:
    def __init__(self, maximum: int = 3):
        self.exchanges: deque[HttpExchange] = deque(maxlen=maximum)

    def attach(self, session: Any) -> None:
        marker_name = "_seguidores_http_recorders"
        attached_recorders = getattr(session, marker_name, set())
        if id(self) in attached_recorders:
            return
        session.hooks.setdefault("response", []).append(self.capture)
        original_send = session.send

        def traced_send(request: Any, *args: Any, **kwargs: Any) -> Any:
            try:
                return original_send(request, *args, **kwargs)
            except Exception:
                self.capture_request(request)
                raise

        session.send = traced_send
        setattr(session, marker_name, {*attached_recorders, id(self)})

    def capture_request(self, request: Any) -> None:
        self.exchanges.append(_exchange_from_request(request))

    def capture(self, response: Any, *_args: Any, **_kwargs: Any) -> Any:
        exchange = _exchange_from_request(response.request)
        self.exchanges.append(
            HttpExchange(
                method=exchange.method,
                url=exchange.url,
                request_headers=exchange.request_headers,
                request_body=exchange.request_body,
                status_code=int(response.status_code),
                reason=str(response.reason or ""),
                response_headers=_sanitize_headers(dict(response.headers)),
                response_body=_sanitize_body(
                    response.content,
                    response.headers.get("Content-Type", ""),
                ),
            )
        )
        return response

    def latest_status(self, status_codes: set[int]) -> int | None:
        for exchange in reversed(self.exchanges):
            if exchange.status_code in status_codes:
                return exchange.status_code
        return None

    def format(self, exception: Exception | None = None) -> str:
        lines = ["Diagnóstico HTTP (datos sensibles ocultos):"]
        if exception is not None:
            lines.append(f"Excepción: {type(exception).__name__}: {_sanitize_text(str(exception))}")
        if not self.exchanges:
            lines.append("No se capturó una respuesta HTTP para esta operación.")
            return "\n".join(lines)
        for index, exchange in enumerate(self.exchanges, start=1):
            lines.extend(
                [
                    "",
                    f"[{index}] REQUEST",
                    f"{exchange.method} {exchange.url}",
                    _format_headers(exchange.request_headers),
                ]
            )
            if exchange.request_body:
                lines.append(f"Body: {exchange.request_body}")
            lines.append("RESPONSE")
            if exchange.status_code is None:
                lines.append("No se recibió una response HTTP.")
            else:
                lines.extend(
                    [
                        f"HTTP {exchange.status_code} {exchange.reason}".rstrip(),
                        _format_headers(exchange.response_headers),
                    ]
                )
                if exchange.response_body:
                    lines.append(f"Body: {exchange.response_body}")
        return "\n".join(lines)


def _exchange_from_request(request: Any) -> HttpExchange:
    headers = dict(request.headers)
    return HttpExchange(
        method=str(request.method or "GET"),
        url=_sanitize_url(str(request.url or "")),
        request_headers=_sanitize_headers(headers),
        request_body=_sanitize_body(request.body, headers.get("Content-Type", "")),
        status_code=None,
        reason="",
        response_headers={},
        response_body="",
    )


def _is_sensitive(name: str) -> bool:
    lowered = name.casefold()
    return any(part in lowered for part in SENSITIVE_PARTS)


def _sanitize_headers(headers: dict[Any, Any]) -> dict[str, str]:
    return {
        str(name): REDACTED if _is_sensitive(str(name)) else _truncate(str(value), 800)
        for name, value in sorted(headers.items(), key=lambda item: str(item[0]).casefold())
    }


def _sanitize_url(url: str) -> str:
    try:
        parts = urlsplit(url)
        query = [
            (name, REDACTED if _is_sensitive(name) else value)
            for name, value in parse_qsl(parts.query, keep_blank_values=True)
        ]
        path = re.sub(r"(?i)(/bot)[^/]+", rf"\1{REDACTED}", parts.path)
        return urlunsplit((parts.scheme, parts.netloc, path, urlencode(query), parts.fragment))
    except ValueError:
        return _sanitize_text(url)


def _sanitize_body(body: Any, content_type: str) -> str:
    if body is None:
        return ""
    text = body.decode("utf-8", errors="replace") if isinstance(body, bytes) else str(body)
    text = text[:MAX_BODY_LENGTH]
    if "json" in content_type.casefold() or text.lstrip().startswith(("{", "[")):
        try:
            sanitized = json.dumps(_sanitize_json(json.loads(text)), ensure_ascii=False)
            return _truncate(sanitized, MAX_BODY_LENGTH)
        except (json.JSONDecodeError, TypeError):
            pass
    if "form" in content_type.casefold():
        try:
            fields = [
                (name, REDACTED if _is_sensitive(name) else value)
                for name, value in parse_qsl(text, keep_blank_values=True)
            ]
            return _truncate(urlencode(fields), MAX_BODY_LENGTH)
        except ValueError:
            pass
    return _truncate(_sanitize_text(text), MAX_BODY_LENGTH)


def _sanitize_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: REDACTED if _is_sensitive(str(key)) else _sanitize_json(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_sanitize_json(item) for item in value]
    return value


def _sanitize_text(value: str) -> str:
    sanitized = re.sub(r"(?i)(/bot)[^/\s]+", rf"\1{REDACTED}", value)
    for name in SENSITIVE_PARTS:
        sanitized = re.sub(
            rf"(?i)({re.escape(name)}[^:=\s]*\s*[:=]\s*)[^&\s,;\"']+",
            rf"\1{REDACTED}",
            sanitized,
        )
    return sanitized


def sanitize_text(value: str) -> str:
    return _sanitize_text(value)


def _format_headers(headers: dict[str, str]) -> str:
    if not headers:
        return "Headers: {}"
    rendered = ", ".join(f"{name}={value}" for name, value in headers.items())
    return f"Headers: {rendered}"


def _truncate(value: str, length: int) -> str:
    return value if len(value) <= length else value[:length] + "…"
