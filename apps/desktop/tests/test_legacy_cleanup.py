import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from seguidores.paths import AppPaths
from seguidores_desktop import legacy_cleanup as legacy


@pytest.mark.parametrize("platform", ["win32", "darwin", "linux"])
def test_cleanup_removes_only_synthetic_sessions_and_lock(platform, tmp_path, monkeypatch):
    paths = AppPaths(tmp_path)
    paths.sessions.mkdir()
    (paths.sessions / "synthetic.session").write_text("fixture, no credentials")
    paths.lock.write_text("fixture")
    tasks = {
        "win32": "_cleanup_windows_task",
        "darwin": "_cleanup_macos_task",
        "linux": "_cleanup_linux_tasks",
    }
    cleanup = Mock()
    monkeypatch.setattr(sys, "platform", platform)
    monkeypatch.setattr(legacy, tasks[platform], cleanup)
    legacy.cleanup_legacy_state(paths)
    cleanup.assert_called_once_with()
    assert not paths.sessions.exists() and not paths.lock.exists()


@pytest.mark.parametrize(
    "code,detail,raises", [(0, "", False), (1, "no existe", False), (1, "synthetic refusal", True)]
)
def test_windows_task_removal_is_only_a_mock(code, detail, raises, monkeypatch):
    run = Mock(return_value=SimpleNamespace(returncode=code, stdout="", stderr=detail))
    monkeypatch.setattr(legacy.subprocess, "run", run)
    if raises:
        with pytest.raises(legacy.LegacyCleanupError, match="synthetic refusal"):
            legacy._cleanup_windows_task()
    else:
        legacy._cleanup_windows_task()
    assert run.call_args.args[0] == ["schtasks", "/Delete", "/TN", legacy.WINDOWS_TASK, "/F"]


def test_macos_cleanup_uses_synthetic_home_and_mock_launchctl(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    plist = tmp_path / "Library/LaunchAgents" / f"{legacy.MAC_LABEL}.plist"
    plist.parent.mkdir(parents=True)
    plist.write_text("synthetic plist")
    run = Mock()
    monkeypatch.setattr(legacy.subprocess, "run", run)
    legacy._cleanup_macos_task()
    assert not plist.exists()
    assert run.call_args.args[0] == ["launchctl", "unload", str(plist)]


def test_linux_cleanup_keeps_unrelated_cron_and_uses_only_fake_commands(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    units = tmp_path / ".config/systemd/user"
    units.mkdir(parents=True)
    for suffix in ("timer", "service"):
        (units / f"{legacy.LINUX_UNIT}.{suffix}").write_text("synthetic unit")
    cron = f"keep before\n{legacy.CRON_MARKER}\nremove synthetic job\nkeep after\n"
    run = Mock(return_value=SimpleNamespace(returncode=0, stdout=cron))
    monkeypatch.setattr(legacy.subprocess, "run", run)
    legacy._cleanup_linux_tasks()
    assert not list(units.iterdir())
    assert [call.args[0][0] for call in run.call_args_list] == [
        "systemctl",
        "systemctl",
        "crontab",
        "crontab",
    ]
    assert run.call_args.kwargs["input"] == "keep before\nkeep after\n"
    run.side_effect = OSError("synthetic missing crontab")
    legacy._cleanup_linux_tasks()
