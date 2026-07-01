import json
import sys
import tkinter as tk

import pytest
from seguidores.paths import AppPaths
from seguidores_desktop.gui import NEW_PROFILE, SeguidoresApp, main


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


def test_gui_builds_import_notifications_and_results_tabs(gui):
    assert gui.notebook.index("end") == 3
    assert gui.profile_choice.get() == NEW_PROFILE
    assert not gui.paths.config.exists()


def test_gui_account_form_builds_valid_profile(gui):
    gui.account_name.set("personal")
    gui.instagram_username.set("@Owner.Name")

    account = gui._account_from_form()

    assert account.name == "personal"
    assert account.username == "owner.name"


def test_gui_imports_selected_json_files(gui, tmp_path, monkeypatch):
    followers = tmp_path / "followers_1.json"
    following = tmp_path / "following.json"
    followers.write_text(json.dumps([{"string_list_data": [{"value": "alice"}]}]), encoding="utf-8")
    following.write_text(
        json.dumps({"relationships_following": [{"title": "bob", "string_list_data": []}]}),
        encoding="utf-8",
    )
    gui.account_name.set("personal")
    gui.instagram_username.set("owner")
    gui.follower_paths = (followers,)
    gui.following_paths = (following,)
    gui.config.notifications.popup = False
    captured = {}

    def run_now(_label, work, success):
        captured["report"] = work()
        success(captured["report"])
        return True

    monkeypatch.setattr(gui, "run_async", run_now)

    gui._import_files()

    assert "Seguidores: 1" in captured["report"]
    assert "Seguidos: 1" in captured["report"]


def test_gui_version_mode_does_not_open_window(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["seguidores-gui", "--version"])

    assert main() == 0
    assert "seguidores-gui 0.4.0" in capsys.readouterr().out
