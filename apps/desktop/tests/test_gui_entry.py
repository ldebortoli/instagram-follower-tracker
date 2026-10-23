import runpy
import sqlite3
import sys
import tkinter
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import keyring
import pytest
from seguidores_desktop import gui

ENTRY = Path(__file__).resolve().parents[1] / "packaging" / "gui_entry.py"


@pytest.fixture
def self_test_dependencies(monkeypatch):
    checks = []

    def connect(name):
        assert name == ":memory:"
        checks.append("sqlite")
        return SimpleNamespace(close=lambda: checks.append("closed"))

    monkeypatch.setattr(sqlite3, "connect", connect)
    monkeypatch.setattr(tkinter, "Tcl", lambda: checks.append("tcl"))
    monkeypatch.setattr(keyring, "get_keyring", lambda: checks.append("keyring"))
    return checks


def test_packaging_self_test_checks_dependencies_without_starting_gui(
    self_test_dependencies, monkeypatch
):
    main = Mock(side_effect=AssertionError("GUI must not start during self-test"))
    monkeypatch.setattr(gui, "main", main)
    monkeypatch.setattr(sys, "argv", ["seguidores-gui", "--packaging-self-test"])

    with pytest.raises(SystemExit) as stopped:
        runpy.run_path(str(ENTRY), run_name="__main__")

    assert stopped.value.code == 0
    assert self_test_dependencies == ["sqlite", "closed", "tcl", "keyring"]
    main.assert_not_called()


@pytest.mark.parametrize("dependency", ["sqlite", "tcl", "keyring"])
def test_packaging_self_test_propagates_missing_dependencies(
    dependency, self_test_dependencies, monkeypatch
):
    def unavailable(*_args):
        raise RuntimeError("missing dependency")

    target, name = {
        "sqlite": (sqlite3, "connect"),
        "tcl": (tkinter, "Tcl"),
        "keyring": (keyring, "get_keyring"),
    }[dependency]
    monkeypatch.setattr(target, name, unavailable)
    monkeypatch.setattr(sys, "argv", ["seguidores-gui", "--packaging-self-test"])

    with pytest.raises(RuntimeError, match="missing dependency"):
        runpy.run_path(str(ENTRY), run_name="__main__")


def test_gui_packaging_entry_preserves_gui_exit_code(monkeypatch):
    main = Mock(return_value=17)
    monkeypatch.setattr(gui, "main", main)
    monkeypatch.setattr(sys, "argv", ["seguidores-gui"])

    with pytest.raises(SystemExit) as stopped:
        runpy.run_path(str(ENTRY), run_name="__main__")

    assert stopped.value.code == 17
    main.assert_called_once_with()
