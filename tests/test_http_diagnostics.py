import pytest
import requests

from seguidores.http_diagnostics import REDACTED, RequestRecorder


def test_http_diagnostic_includes_exchange_and_redacts_secrets():
    prepared = requests.Request(
        "POST",
        "https://example.test/profile?username=owner&access_token=query-secret",
        headers={
            "Authorization": "Bearer header-secret",
            "Cookie": "sessionid=cookie-secret",
            "User-Agent": "Seguidores-Test",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={"username": "owner", "password": "body-secret"},
    ).prepare()
    response = requests.Response()
    response.status_code = 401
    response.reason = "Unauthorized"
    response.headers["Content-Type"] = "application/json"
    response.headers["Set-Cookie"] = "sessionid=response-cookie"
    response._content = b'{"status":"fail","message":"wait","sessionid":"response-secret"}'
    response.request = prepared
    recorder = RequestRecorder()

    recorder.capture(response)
    rendered = recorder.format(RuntimeError("request failed"))

    assert "POST https://example.test/profile" in rendered
    assert "HTTP 401 Unauthorized" in rendered
    assert "Seguidores-Test" in rendered
    assert "wait" in rendered
    assert REDACTED in rendered
    for secret in (
        "query-secret",
        "header-secret",
        "cookie-secret",
        "body-secret",
        "response-cookie",
        "response-secret",
    ):
        assert secret not in rendered


def test_http_diagnostic_explains_when_no_response_was_captured():
    rendered = RequestRecorder().format(ValueError("offline failure"))

    assert "ValueError: offline failure" in rendered
    assert "No se capturó una respuesta HTTP" in rendered


def test_http_diagnostic_keeps_request_when_connection_fails(monkeypatch):
    session = requests.Session()

    def fail(_request, *_args, **_kwargs):
        raise requests.ConnectionError("offline")

    monkeypatch.setattr(session, "send", fail)
    recorder = RequestRecorder()
    recorder.attach(session)
    with pytest.raises(requests.ConnectionError):
        session.get("https://example.test/profile?access_token=secret")

    rendered = recorder.format(requests.ConnectionError("offline"))
    assert "GET https://example.test/profile" in rendered
    assert "No se recibió una response HTTP" in rendered
    assert "secret" not in rendered
