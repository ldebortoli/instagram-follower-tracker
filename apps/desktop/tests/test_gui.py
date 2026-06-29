import sys
import tkinter as tk

import pytest
from seguidores.app import RunResult
from seguidores.config import AccountConfig
from seguidores.paths import AppPaths
from seguidores_desktop.gui import ALL_ACCOUNTS, SeguidoresApp, main


@pytest.fixture
def gui(tmp_path):
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("El runner no tiene una sesión gráfica.")
    root.withdraw()
    app = SeguidoresApp(root, AppPaths(tmp_path))
    root.update_idletasks()
    yield app
    root.destroy()


def test_gui_builds_all_configuration_tabs_without_creating_config(gui):
    assert gui.notebook.index("end") == 4
    assert gui.run_account.get() == ALL_ACCOUNTS
    assert not gui.paths.config.exists()


def test_gui_account_form_builds_valid_account(gui):
    gui.account_name.set("personal")
    gui.instagram_username.set("@Owner.Name")
    gui.login_username.set("")

    account = gui._account_from_form()

    assert account.name == "personal"
    assert account.username == "owner.name"
    assert account.login_username == "owner.name"


def test_gui_can_bypass_cooldown_for_one_manual_check(gui, monkeypatch):
    captured = {}
    gui.config.accounts = [AccountConfig("personal", "target", "owner")]
    gui.bypass_cooldown.set(True)

    class FakeCollector:
        def __init__(self, paths, *, bypass_cooldown=False):
            captured["paths"] = paths
            captured["bypass_cooldown"] = bypass_cooldown

    class FakeTracker:
        def __init__(self, paths, config, collector=None):
            captured["collector"] = collector

        def run(self, *, account_name=None):
            captured["account_name"] = account_name
            return RunResult((), ())

    monkeypatch.setattr("seguidores_desktop.gui.InstagramCollector", FakeCollector)
    monkeypatch.setattr("seguidores_desktop.gui.Tracker", FakeTracker)
    monkeypatch.setattr("seguidores_desktop.gui.messagebox.askyesno", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        gui,
        "run_async",
        lambda _label, work, _success: captured.setdefault("result", work()) is not None,
    )

    gui._run_check()

    assert captured["bypass_cooldown"] is True
    assert captured["account_name"] is None
    assert gui.bypass_cooldown.get() is False


def test_gui_version_mode_does_not_open_window(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["seguidores-gui", "--version"])

    assert main() == 0
    assert "seguidores-gui 0.3.0" in capsys.readouterr().out


def test_gui_scheduled_mode_delegates_to_cli(monkeypatch):
    calls = []
    monkeypatch.setattr(sys, "argv", ["seguidores-gui", "--scheduled-run"])
    monkeypatch.setattr(
        "seguidores_desktop.cli.main", lambda arguments: calls.append(arguments) or 7
    )

    assert main() == 7
    assert calls == [["run", "--if-due"]]
