import queue
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from seguidores.config import AccountConfig, ConfigError, default_config
from seguidores.notifier import NotificationError
from seguidores.paths import AppPaths
from seguidores_desktop import gui


class Value:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


@pytest.fixture
def app(tmp_path):
    instance = gui.SeguidoresApp.__new__(gui.SeguidoresApp)
    instance.paths = AppPaths(tmp_path)
    instance.config = default_config()
    instance.root = Mock()
    instance.root.winfo_exists.return_value = False
    instance.busy = False
    instance.events = queue.Queue()
    for name in (
        "profile_choice",
        "account_name",
        "instagram_username",
        "telegram_chat_id",
        "telegram_token",
        "followers_label",
        "following_label",
        "status",
    ):
        setattr(instance, name, Value())
    instance.profile_choice.set(gui.NEW_PROFILE)
    for name in ("popup_enabled", "notify_without_changes", "telegram_enabled"):
        setattr(instance, name, Value(False))
    for name in ("profile_combo", "results_text", "notebook", "results_tab"):
        setattr(instance, name, Mock())
    instance.follower_paths = ()
    instance.following_paths = ()
    return instance


def test_profiles_selection_validation_and_updates(app):
    app.config.accounts = [AccountConfig("fixture", "first")]
    app._refresh_profiles("fixture")
    assert app.instagram_username.get() == "first"
    app.instagram_username.set("@SECOND")
    app._save_account()
    assert app.config.accounts == [AccountConfig("fixture", "second")]
    app.account_name.set("renamed")
    with pytest.raises(ConfigError, match="renombrar"):
        app._account_from_form()


def test_file_choosers_use_only_returned_synthetic_paths(app, tmp_path, monkeypatch):
    selected = (str(tmp_path / "fixture.json"),)
    choose = Mock(side_effect=[selected, selected, (), ()])
    monkeypatch.setattr(gui.filedialog, "askopenfilenames", choose)
    app._choose_followers()
    app._choose_following()
    app._choose_followers()
    app._choose_following()
    assert app.follower_paths == app.following_paths == (tmp_path / "fixture.json",)
    assert app.followers_label.get() == app.following_label.get() == "fixture.json"


def test_import_validation_and_warning_report_use_synthetic_json(app, tmp_path, monkeypatch):
    error = Mock()
    monkeypatch.setattr(gui.messagebox, "showerror", error)
    app.account_name.set("fixture")
    app.instagram_username.set("fixture")
    app._import_files()
    error.assert_called_once()
    follower = tmp_path / "followers.json"
    following = tmp_path / "following.json"
    follower.write_text('[{"title":"alice"}]')
    following.write_text('[{"title":"bob"}]')
    app.follower_paths, app.following_paths = (follower,), (following,)
    monkeypatch.setattr(
        gui, "notify", lambda *_args: [SimpleNamespace(channel="popup", error="fixture")]
    )
    monkeypatch.setattr(app, "run_async", lambda _label, work, success: success(work()))
    app._import_files()
    text = app.results_text.insert.call_args.args[1]
    assert "Avisos:" in text and "popup: fixture" in text
    assert app.status.get() == "Archivos importados y captura guardada."


def test_notification_form_validation_and_memory_keyring(app, monkeypatch):
    error = Mock()
    monkeypatch.setattr(gui.messagebox, "showerror", error)
    app.telegram_enabled.set(True)
    app._save_notifications()
    assert "chat ID" in error.call_args.args[1]
    app.telegram_chat_id.set("synthetic-chat")
    app._save_notifications()
    assert "token" in error.call_args.args[1]
    app.telegram_token.set("synthetic-token")
    app._save_notifications()
    assert app.config.notifications.telegram.enabled
    assert app.config.notifications.telegram.chat_id == "synthetic-chat"
    assert app.telegram_token.get() == ""
    app._save_notifications()
    assert "guardada" in app.status.get()


def test_telegram_test_action_uses_only_fake_transport(app, monkeypatch):
    captured = {}

    def run(_label, work, success):
        captured.update(work=work, success=success)

    monkeypatch.setattr(app, "run_async", run)
    monkeypatch.setattr(gui, "get_telegram_token", lambda: None)
    app._test_telegram()
    with pytest.raises(NotificationError, match="token"):
        captured["work"]()
    app.telegram_token.set("synthetic-token")
    app.telegram_chat_id.set("synthetic-chat")
    send = Mock()
    monkeypatch.setattr(gui, "send_telegram", send)
    app._test_telegram()
    captured["work"]()
    captured["success"](None)
    assert send.call_args.args[:2] == ("synthetic-token", "synthetic-chat")
    assert "Mensaje de prueba" in app.status.get()


def test_async_events_use_synchronous_fake_worker_and_preserve_callbacks(app, monkeypatch):
    thread = Mock(side_effect=lambda *, target, daemon: SimpleNamespace(start=target))
    monkeypatch.setattr(gui.threading, "Thread", thread)
    success = Mock()
    assert app.run_async("fixture", lambda: 7, success)
    assert not app.run_async("busy", lambda: None, success)
    app._drain_events()
    success.assert_called_once_with(7)
    error = Mock()
    fail = Mock(side_effect=RuntimeError("synthetic worker failure"))
    assert app.run_async("fixture", fail, success, error)
    app._drain_events()
    assert isinstance(error.call_args.args[0], RuntimeError)
    assert app.run_async("fixture", fail, success)
    app.root.winfo_exists.return_value = True
    app._drain_events()
    assert app.status.get() == "La operación falló."
    app.root.after.assert_called_once_with(100, app._drain_events)


def test_close_respects_busy_confirmation_without_real_dialog(app, monkeypatch):
    app.busy = True
    confirm = Mock(return_value=False)
    monkeypatch.setattr(gui.messagebox, "askyesno", confirm)
    app._close()
    app.root.destroy.assert_not_called()
    confirm.return_value = True
    app._close()
    app.root.destroy.assert_called_once()


def test_main_paths_logging_and_tk_errors_use_only_fakes(tmp_path, monkeypatch, capsys):
    paths = AppPaths(tmp_path)
    monkeypatch.setattr(sys, "argv", ["gui-fixture"])
    monkeypatch.setattr(gui, "app_paths", lambda: paths)
    monkeypatch.setattr(
        gui.ctypes, "windll", SimpleNamespace(shcore=SimpleNamespace(SetProcessDpiAwareness=Mock()))
    )
    logger = Mock(handlers=[])
    handler = Mock()
    real_get_logger = gui.logging.getLogger
    monkeypatch.setattr(
        gui.logging,
        "getLogger",
        lambda name=None: logger if name == "seguidores" else real_get_logger(name),
    )
    monkeypatch.setattr(gui, "RotatingFileHandler", Mock(return_value=handler))
    monkeypatch.setattr(gui.tk, "Tk", Mock(side_effect=gui.tk.TclError("synthetic Tk failure")))
    assert gui.main() == 2
    assert "synthetic Tk failure" in capsys.readouterr().err
    logger.addHandler.assert_called_once_with(handler)
    logger.handlers = [handler]
    gui._configure_logging(paths)
    root = Mock()
    monkeypatch.setattr(gui.tk, "Tk", lambda: root)
    construct = Mock()
    monkeypatch.setattr(gui, "SeguidoresApp", construct)
    assert gui.main(paths) == 0
    construct.assert_called_once_with(root, paths)
    root.mainloop.assert_called_once()


def test_direct_gui_module_version_entry_does_not_open_window(monkeypatch):
    path = Path(gui.__file__)
    monkeypatch.setattr(sys, "argv", ["gui-fixture", "--version"])
    monkeypatch.setattr(gui.tk, "Tk", Mock(side_effect=AssertionError("must not open")))
    with pytest.raises(SystemExit) as stopped:
        exec(
            compile(path.read_bytes(), str(path), "exec"),
            {"__name__": "__main__", "__file__": str(path)},
        )
    assert stopped.value.code == 0


def test_all_tabs_construct_with_widget_doubles_and_schedule_only_callbacks(tmp_path, monkeypatch):
    widgets = []

    def widget(*args, **kwargs):
        value = Mock()
        widgets.append((value, kwargs))
        return value

    for name in (
        "Frame",
        "Label",
        "Notebook",
        "LabelFrame",
        "Combobox",
        "Entry",
        "Button",
        "Checkbutton",
        "Separator",
    ):
        monkeypatch.setattr(gui.ttk, name, widget)
    monkeypatch.setattr(gui.tk, "Text", widget)
    monkeypatch.setattr(gui.tk, "StringVar", lambda value="": Value(value))
    monkeypatch.setattr(gui.tk, "BooleanVar", lambda value=False: Value(value))
    style = Mock()
    style.theme_names.return_value = ["vista", "aqua", "clam"]
    monkeypatch.setattr(gui.ttk, "Style", lambda _root: style)
    root = Mock()
    paths = AppPaths(tmp_path)
    instance = gui.SeguidoresApp(root, paths)
    assert instance.profile_choice.get() == gui.NEW_PROFILE
    assert instance.notebook.add.call_count == 3
    assert [call.kwargs["text"] for call in instance.notebook.add.call_args_list] == [
        "1. Importar JSON",
        "2. Notificaciones",
        "Resultados",
    ]
    assert [call.args[0] for call in root.after.call_args_list] == [100, 150]
    assert not paths.config.exists()
    assert any(options.get("text") == "Comparar y guardar captura" for _value, options in widgets)
    assert style.theme_use.call_count == 1
    instance.config.accounts = [AccountConfig("fixture", "synthetic")]
    gui.save_config(paths, instance.config)
    restored = gui.SeguidoresApp(Mock(), paths)
    assert restored.instagram_username.get() == "synthetic"
