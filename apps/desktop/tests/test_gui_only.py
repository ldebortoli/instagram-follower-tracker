import importlib.metadata
import importlib.util
import runpy
import socket
import subprocess
import sysconfig
import tomllib
import urllib.request
from pathlib import Path
from unittest.mock import Mock

import httpx
import keyring
import pytest
from seguidores import __version__, notifier
from seguidores.paths import AppPaths
from seguidores_desktop import gui
from telegram.ext import Application

ROOT = Path(__file__).resolve().parents[3]


def test_product_metadata_versions_and_entrypoints_are_gui_only():
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    installed = importlib.metadata.distribution("seguidores-instagram")

    assert config["project"]["version"] == __version__ == installed.version == "0.4.1"
    scripts = {
        (entry.group, entry.name): entry.value
        for entry in installed.entry_points
        if entry.group in {"console_scripts", "gui_scripts"}
    }
    assert scripts == {
        ("console_scripts", "jo-bot"): "jo_bot.app:main",
        ("console_scripts", "jobot"): "jo_bot.app:local_main",
        ("gui_scripts", "seguidores-gui"): "seguidores_desktop.gui:main",
    }
    assert config["project"]["scripts"] == {
        "jo-bot": "jo_bot.app:main",
        "jobot": "jo_bot.app:local_main",
    }
    assert config["project"]["gui-scripts"] == {
        "seguidores-gui": "seguidores_desktop.gui:main"
    }


def test_module_entrypoint_calls_gui_without_starting_it(monkeypatch):
    main = Mock(return_value=37)
    monkeypatch.setattr(gui, "main", main)

    with pytest.raises(SystemExit) as stopped:
        runpy.run_module("seguidores_desktop", run_name="__main__")

    assert stopped.value.code == 37
    main.assert_called_once_with()


def test_removed_console_sources_are_absent():
    assert not (ROOT / "apps/desktop/src/seguidores_desktop/cli.py").exists()
    assert not (ROOT / "apps/desktop/packaging/console_entry.py").exists()
    assert importlib.util.find_spec("seguidores_desktop.cli") is None
    scripts = Path(sysconfig.get_path("scripts"))
    assert not (scripts / "seguidores.exe").exists()
    assert not (scripts / "seguidores").exists()


def test_credential_and_notification_fixtures_stay_in_memory(isolated_external_effects, tmp_path):
    assert keyring.get_password("fixture", "user") is None
    keyring.set_password("fixture", "user", "synthetic-only")
    assert keyring.get_password("fixture", "user") == "synthetic-only"
    assert isolated_external_effects == {("fixture", "user"): "synthetic-only"}
    keyring.delete_password("fixture", "user")
    assert isolated_external_effects == {}
    assert keyring.get_keyring().priority == 1
    assert gui.messagebox.showinfo("fixture", "synthetic notification") is None
    assert notifier.send_popup("fixture", "synthetic popup") is None
    assert gui.cleanup_legacy_state(AppPaths(tmp_path)) is None


@pytest.mark.parametrize(
    "effect",
    [
        lambda: urllib.request.urlopen("https://offline.example.invalid"),
        lambda: subprocess.run(["__seguidores_test_must_not_spawn__"]),
        lambda: httpx.HTTPTransport.handle_request(None, None),
        lambda: httpx.AsyncHTTPTransport.handle_async_request(None, None),
        lambda: Application.run_polling(None),
        lambda: Application.run_webhook(None),
        lambda: socket.getaddrinfo("offline.example.invalid", 443),
    ],
    ids=["urlopen", "process", "httpx", "httpx-async", "polling", "webhook", "dns"],
)
def test_external_effects_require_test_doubles(effect):
    with pytest.raises(AssertionError, match="External effects"):
        effect()


def test_loopback_address_lookup_supports_asyncio_without_external_dns():
    assert socket.getaddrinfo("127.0.0.1", 0)
