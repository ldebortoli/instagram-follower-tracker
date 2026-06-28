import plistlib
from pathlib import Path

from seguidores.paths import AppPaths
from seguidores.scheduler import cron_lines, launchd_plist, systemd_units, windows_task_xml


def test_windows_task_has_daily_and_catch_up_triggers(tmp_path):
    paths = AppPaths(tmp_path / "Seguidores")

    xml = windows_task_xml(Path("C:/Python/python.exe"), paths, "09:15", "S-1-5-21-123")

    assert "<DaysInterval>1</DaysInterval>" in xml
    assert "<LogonTrigger>" in xml
    assert "<StartWhenAvailable>true</StartWhenAvailable>" in xml
    assert "S-1-5-21-123" in xml
    assert "--if-due" in xml


def test_launchd_runs_at_load_and_calendar_time(tmp_path):
    payload = plistlib.loads(launchd_plist(Path("/usr/bin/python3"), AppPaths(tmp_path), "08:05"))

    assert payload["RunAtLoad"] is True
    assert payload["StartCalendarInterval"] == {"Hour": 8, "Minute": 5}
    assert payload["ProgramArguments"][-1] == "--if-due"


def test_systemd_timer_is_persistent(tmp_path):
    executable = Path("/opt/my env/bin/python")
    service, timer = systemd_units(executable, AppPaths(tmp_path / "app data"), "21:45")

    assert "Persistent=true" in timer
    assert "OnCalendar=*-*-* 21:45:00" in timer
    assert "ExecStart=" in service
    assert "my env" in service


def test_cron_has_daily_and_reboot_entries(tmp_path):
    lines = cron_lines(Path("/usr/bin/python3"), AppPaths(tmp_path), "06:07")

    assert lines[1].startswith("7 6 * * *")
    assert lines[2].startswith("@reboot")
    assert all("--if-due" in line for line in lines[1:3])
