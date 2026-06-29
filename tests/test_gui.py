import sys
import tkinter as tk

import pytest

from seguidores.gui import ALL_ACCOUNTS, SeguidoresApp, main
from seguidores.paths import AppPaths


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


def test_gui_version_mode_does_not_open_window(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["seguidores-gui", "--version"])

    assert main() == 0
    assert "seguidores-gui 0.2.1" in capsys.readouterr().out


def test_gui_scheduled_mode_delegates_to_cli(monkeypatch):
    calls = []
    monkeypatch.setattr(sys, "argv", ["seguidores-gui", "--scheduled-run"])
    monkeypatch.setattr("seguidores.cli.main", lambda arguments: calls.append(arguments) or 7)

    assert main() == 7
    assert calls == [["run", "--if-due"]]
