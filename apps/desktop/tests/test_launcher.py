import sys
from pathlib import Path

from seguidores_desktop.launcher import scheduled_invocation


def test_source_invocation_uses_python_module(monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.setattr(sys, "executable", "/opt/python/bin/python")

    invocation = scheduled_invocation(graphical=True)

    assert invocation.executable == Path("/opt/python/bin/python").resolve()
    assert invocation.arguments == ("-m", "seguidores_desktop", "run", "--if-due")


def test_frozen_console_invocation_uses_cli_arguments(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", "/opt/Seguidores/seguidores")

    invocation = scheduled_invocation()

    assert invocation.arguments == ("run", "--if-due")


def test_frozen_graphical_invocation_uses_hidden_scheduled_mode(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", "/Applications/Seguidores.app/Contents/MacOS/Seguidores")

    invocation = scheduled_invocation(graphical=True)

    assert invocation.arguments == ("--scheduled-run",)
