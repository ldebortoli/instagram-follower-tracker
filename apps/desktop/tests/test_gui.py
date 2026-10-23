import json
import sys
import tkinter as tk
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from seguidores.config import default_config, load_config
from seguidores.paths import AppPaths
from seguidores_desktop import gui as gui_module
from seguidores_desktop.gui import NEW_PROFILE, SeguidoresApp, main


@pytest.fixture(scope="session")
def tk_root():
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"No se pudo crear Tk en el runner aislado: {exc}")
    root.withdraw()
    yield root
    root.destroy()


@pytest.fixture
def gui(tmp_path, tk_root):
    root = tk.Toplevel(tk_root)
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


@pytest.mark.parametrize("follower_file_count", [1, 2])
def test_gui_imports_selected_json_files(gui, tmp_path, monkeypatch, follower_file_count):
    followers = []
    for index, username in enumerate(("alice", "carol")[:follower_file_count], start=1):
        path = tmp_path / f"followers_{index}.json"
        path.write_text(
            json.dumps([{"string_list_data": [{"value": username}]}]), encoding="utf-8"
        )
        followers.append(path)
    following = tmp_path / "following.json"
    following.write_text(
        json.dumps({"relationships_following": [{"title": "bob", "string_list_data": []}]}),
        encoding="utf-8",
    )
    gui.account_name.set("personal")
    gui.instagram_username.set("owner")
    gui.follower_paths = tuple(followers)
    gui.following_paths = (following,)
    gui.config.notifications.popup = False
    captured = {}

    def run_now(_label, work, success):
        captured["report"] = work()
        success(captured["report"])
        return True

    monkeypatch.setattr(gui, "run_async", run_now)

    gui._import_files()

    assert f"Seguidores: {follower_file_count}" in captured["report"]
    assert "Seguidos: 1" in captured["report"]


def test_gui_version_mode_does_not_open_window(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["seguidores-gui", "--version"])
    monkeypatch.setattr(tk, "Tk", lambda: pytest.fail("Version mode must not create a window"))
    monkeypatch.setattr(
        "seguidores_desktop.gui.app_paths",
        lambda: pytest.fail("Version mode must not read the real application home"),
    )

    assert main() == 0
    assert "seguidores-gui 0.4.1" in capsys.readouterr().out


def test_gui_migration_runs_once_with_synthetic_paths(tmp_path, monkeypatch):
    cleanup = Mock()
    monkeypatch.setattr(gui_module, "cleanup_legacy_state", cleanup)
    app = SimpleNamespace(
        config=default_config(), paths=AppPaths(tmp_path), _set_status=Mock()
    )

    SeguidoresApp._cleanup_legacy_installation(app)
    SeguidoresApp._cleanup_legacy_installation(app)

    cleanup.assert_called_once_with(app.paths)
    assert load_config(app.paths).legacy_cleanup_done


def test_failed_gui_migration_keeps_retry_available(tmp_path, monkeypatch):
    cleanup = Mock(side_effect=gui_module.LegacyCleanupError("synthetic failure"))
    warning = Mock()
    monkeypatch.setattr(gui_module, "cleanup_legacy_state", cleanup)
    monkeypatch.setattr(gui_module.messagebox, "showwarning", warning)
    app = SimpleNamespace(
        config=default_config(), paths=AppPaths(tmp_path), root=object(), _set_status=Mock()
    )

    SeguidoresApp._cleanup_legacy_installation(app)

    assert not app.config.legacy_cleanup_done
    assert not app.paths.config.exists()
    warning.assert_called_once()
