"""Keep all tests away from real accounts, credentials and system tasks."""

import socket
import subprocess
import urllib.request
from types import SimpleNamespace

import httpx
import keyring
import pytest
from seguidores import notifier
from seguidores_desktop import gui
from telegram.ext import Application


@pytest.fixture(autouse=True)
def isolated_external_effects(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("SEGUIDORES_HOME", str(home / "seguidores"))
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.delenv(notifier.TOKEN_ENVIRONMENT_VARIABLE, raising=False)
    passwords = {}

    def set_password(service, user, value):
        passwords[service, user] = value

    def delete_password(service, user):
        passwords.pop((service, user), None)

    monkeypatch.setattr(
        keyring, "get_password", lambda service, user: passwords.get((service, user))
    )
    monkeypatch.setattr(keyring, "set_password", set_password)
    monkeypatch.setattr(keyring, "delete_password", delete_password)
    monkeypatch.setattr(keyring, "get_keyring", lambda: SimpleNamespace(priority=1))
    monkeypatch.setattr(notifier, "send_popup", lambda *_args: None)
    monkeypatch.setattr(gui, "cleanup_legacy_state", lambda _paths: None)
    for name in ("showinfo", "showwarning", "showerror"):
        monkeypatch.setattr(gui.messagebox, name, lambda *_args, **_kwargs: None)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("External effects must be replaced by a test double.")

    monkeypatch.setattr(urllib.request, "urlopen", forbidden)
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", forbidden)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", forbidden)
    for name in ("run", "Popen", "check_output", "check_call"):
        monkeypatch.setattr(subprocess, name, forbidden)
    monkeypatch.setattr(Application, "run_polling", forbidden)
    monkeypatch.setattr(Application, "run_webhook", forbidden)
    real_getaddrinfo = socket.getaddrinfo

    def local_addresses_only(host, *args, **kwargs):
        if host not in {"127.0.0.1", "::1", None}:
            forbidden()
        return real_getaddrinfo(host, *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", local_addresses_only)
    return passwords
