from __future__ import annotations

import csv
import html
import io
import os
import plistlib
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from seguidores.config import parse_time
from seguidores.launcher import ScheduledInvocation, scheduled_invocation
from seguidores.paths import AppPaths

WINDOWS_TASK_NAME = "SeguidoresInstagram"
MAC_LABEL = "com.seguidores.instagram.daily"
LINUX_UNIT = "seguidores-instagram"
CRON_MARKER = "# seguidores-instagram managed"


class SchedulerError(RuntimeError):
    pass


@dataclass(frozen=True)
class SchedulerStatus:
    backend: str
    installed: bool
    detail: str


def install(
    paths: AppPaths,
    time: str,
    *,
    backend: str | None = None,
    invocation: ScheduledInvocation | None = None,
) -> str:
    parse_time(time)
    paths.ensure()
    invocation = invocation or scheduled_invocation()
    selected = backend or default_backend()
    if selected == "windows":
        _install_windows(paths, time, invocation)
    elif selected == "launchd":
        _install_launchd(paths, time, invocation)
    elif selected == "systemd":
        try:
            _install_systemd(paths, time, invocation)
        except SchedulerError:
            if backend is not None or not shutil.which("crontab"):
                raise
            selected = "cron"
            _install_cron(paths, time, invocation)
    elif selected == "cron":
        _install_cron(paths, time, invocation)
    else:
        raise SchedulerError(f"Backend de scheduler no soportado: {selected}")
    return selected


def uninstall(backend: str) -> None:
    if backend == "windows":
        _run(["schtasks", "/Delete", "/TN", WINDOWS_TASK_NAME, "/F"])
    elif backend == "launchd":
        path = _launchd_path()
        subprocess.run(
            ["launchctl", "bootout", f"gui/{os.getuid()}", str(path)],
            check=False,
            capture_output=True,
            text=True,
        )
        path.unlink(missing_ok=True)
    elif backend == "systemd":
        subprocess.run(
            ["systemctl", "--user", "disable", "--now", f"{LINUX_UNIT}.timer"],
            check=False,
            capture_output=True,
            text=True,
        )
        _systemd_service_path().unlink(missing_ok=True)
        _systemd_timer_path().unlink(missing_ok=True)
        _run(["systemctl", "--user", "daemon-reload"])
    elif backend == "cron":
        _write_crontab(_without_managed_cron(_read_crontab()))
    elif backend:
        raise SchedulerError(f"Backend de scheduler no soportado: {backend}")


def status(backend: str | None = None) -> SchedulerStatus:
    selected = backend or default_backend()
    if selected == "windows":
        result = subprocess.run(
            ["schtasks", "/Query", "/TN", WINDOWS_TASK_NAME],
            check=False,
            capture_output=True,
            text=True,
        )
        return SchedulerStatus(selected, result.returncode == 0, result.stdout.strip())
    if selected == "launchd":
        path = _launchd_path()
        return SchedulerStatus(selected, path.exists(), str(path))
    if selected == "systemd":
        path = _systemd_timer_path()
        return SchedulerStatus(selected, path.exists(), str(path))
    if selected == "cron":
        installed = CRON_MARKER in _read_crontab()
        return SchedulerStatus(selected, installed, "crontab del usuario")
    raise SchedulerError(f"Backend de scheduler no soportado: {selected}")


def default_backend() -> str:
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "darwin":
        return "launchd"
    return "systemd" if shutil.which("systemctl") else "cron"


def windows_task_xml(
    executable: Path,
    paths: AppPaths,
    time: str,
    user_id: str = "S-1-5-21-test",
    arguments: tuple[str, ...] | None = None,
) -> str:
    hour, minute = parse_time(time)
    start = datetime.now().astimezone().replace(hour=hour, minute=minute, second=0, microsecond=0)
    command = html.escape(str(executable), quote=True)
    argument_text = subprocess.list2cmdline(arguments or ("-m", "seguidores", "run", "--if-due"))
    escaped_arguments = html.escape(argument_text, quote=True)
    working_directory = html.escape(str(paths.root), quote=True)
    principal = html.escape(user_id, quote=True)
    return f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>Chequeo diario de seguidores de Instagram</Description>
  </RegistrationInfo>
  <Triggers>
    <CalendarTrigger>
      <StartBoundary>{start.strftime("%Y-%m-%dT%H:%M:%S")}</StartBoundary>
      <Enabled>true</Enabled>
      <ScheduleByDay><DaysInterval>1</DaysInterval></ScheduleByDay>
    </CalendarTrigger>
    <LogonTrigger><Enabled>true</Enabled></LogonTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>{principal}</UserId>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>true</RunOnlyIfNetworkAvailable>
    <Enabled>true</Enabled>
    <ExecutionTimeLimit>PT2H</ExecutionTimeLimit>
    <Priority>7</Priority>
    <RestartOnFailure><Interval>PT15M</Interval><Count>3</Count></RestartOnFailure>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{command}</Command>
      <Arguments>{escaped_arguments}</Arguments>
      <WorkingDirectory>{working_directory}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"""


def launchd_plist(
    executable: Path,
    paths: AppPaths,
    time: str,
    arguments: tuple[str, ...] | None = None,
) -> bytes:
    hour, minute = parse_time(time)
    payload = {
        "Label": MAC_LABEL,
        "ProgramArguments": [
            str(executable),
            *(arguments or ("-m", "seguidores", "run", "--if-due")),
        ],
        "StartCalendarInterval": {"Hour": hour, "Minute": minute},
        "RunAtLoad": True,
        "ProcessType": "Background",
        "StandardOutPath": str(paths.logs / "scheduled.log"),
        "StandardErrorPath": str(paths.logs / "scheduled-error.log"),
    }
    return plistlib.dumps(payload, fmt=plistlib.FMT_XML, sort_keys=True)


def systemd_units(
    executable: Path,
    paths: AppPaths,
    time: str,
    arguments: tuple[str, ...] | None = None,
) -> tuple[str, str]:
    hour, minute = parse_time(time)
    command = " ".join(
        _systemd_quote(value)
        for value in (str(executable), *(arguments or ("-m", "seguidores", "run", "--if-due")))
    )
    service = f"""[Unit]
Description=Chequeo de seguidores de Instagram
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart={command}
StandardOutput={_systemd_quote("append:" + str(paths.logs / "scheduled.log"))}
StandardError={_systemd_quote("append:" + str(paths.logs / "scheduled-error.log"))}
"""
    timer = f"""[Unit]
Description=Chequeo diario de seguidores de Instagram

[Timer]
OnCalendar=*-*-* {hour:02d}:{minute:02d}:00
Persistent=true
AccuracySec=1min
Unit={LINUX_UNIT}.service

[Install]
WantedBy=timers.target
"""
    return service, timer


def cron_lines(
    executable: Path,
    paths: AppPaths,
    time: str,
    arguments: tuple[str, ...] | None = None,
) -> list[str]:
    hour, minute = parse_time(time)
    command = shlex.join([str(executable), *(arguments or ("-m", "seguidores", "run", "--if-due"))])
    log = shlex.quote(str(paths.logs / "scheduled.log"))
    return [
        CRON_MARKER,
        f"{minute} {hour} * * * {command} >> {log} 2>&1",
        f"@reboot {command} >> {log} 2>&1",
        f"{CRON_MARKER} end",
    ]


def _install_windows(paths: AppPaths, time: str, invocation: ScheduledInvocation) -> None:
    xml_path = paths.root / "windows-task.xml"
    xml_path.write_text(
        windows_task_xml(
            invocation.executable,
            paths,
            time,
            _current_windows_sid(),
            invocation.arguments,
        ),
        encoding="utf-16",
    )
    try:
        _run(["schtasks", "/Create", "/TN", WINDOWS_TASK_NAME, "/XML", str(xml_path), "/F"])
    finally:
        xml_path.unlink(missing_ok=True)


def _install_launchd(paths: AppPaths, time: str, invocation: ScheduledInvocation) -> None:
    path = _launchd_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(launchd_plist(invocation.executable, paths, time, invocation.arguments))
    subprocess.run(
        ["launchctl", "bootout", f"gui/{os.getuid()}", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )
    _run(["launchctl", "bootstrap", f"gui/{os.getuid()}", str(path)])


def _install_systemd(paths: AppPaths, time: str, invocation: ScheduledInvocation) -> None:
    service, timer = systemd_units(invocation.executable, paths, time, invocation.arguments)
    service_path = _systemd_service_path()
    timer_path = _systemd_timer_path()
    service_path.parent.mkdir(parents=True, exist_ok=True)
    service_path.write_text(service, encoding="utf-8")
    timer_path.write_text(timer, encoding="utf-8")
    try:
        _run(["systemctl", "--user", "daemon-reload"])
        _run(["systemctl", "--user", "enable", "--now", f"{LINUX_UNIT}.timer"])
    except SchedulerError:
        service_path.unlink(missing_ok=True)
        timer_path.unlink(missing_ok=True)
        raise


def _install_cron(paths: AppPaths, time: str, invocation: ScheduledInvocation) -> None:
    current = _without_managed_cron(_read_crontab())
    managed = "\n".join(cron_lines(invocation.executable, paths, time, invocation.arguments))
    _write_crontab((current.rstrip() + "\n" + managed + "\n").lstrip())


def _launchd_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{MAC_LABEL}.plist"


def _systemd_service_path() -> Path:
    return Path.home() / ".config" / "systemd" / "user" / f"{LINUX_UNIT}.service"


def _systemd_timer_path() -> Path:
    return Path.home() / ".config" / "systemd" / "user" / f"{LINUX_UNIT}.timer"


def _systemd_quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _current_windows_sid() -> str:
    try:
        result = subprocess.run(
            ["whoami", "/user", "/fo", "csv", "/nh"],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
        row = next(csv.reader(io.StringIO(result.stdout)))
        return row[1]
    except (OSError, subprocess.SubprocessError, StopIteration, IndexError) as exc:
        raise SchedulerError(f"No se pudo determinar el SID del usuario actual: {exc}") from exc


def _read_crontab() -> str:
    result = subprocess.run(["crontab", "-l"], check=False, capture_output=True, text=True)
    if result.returncode not in (0, 1):
        raise SchedulerError(result.stderr.strip() or "No se pudo leer crontab.")
    return result.stdout


def _without_managed_cron(content: str) -> str:
    kept: list[str] = []
    managed = False
    for line in content.splitlines():
        if line == CRON_MARKER:
            managed = True
            continue
        if line == f"{CRON_MARKER} end":
            managed = False
            continue
        if not managed:
            kept.append(line)
    return "\n".join(kept).strip() + ("\n" if kept else "")


def _write_crontab(content: str) -> None:
    try:
        subprocess.run(
            ["crontab", "-"],
            input=content,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SchedulerError(f"No se pudo actualizar crontab: {exc}") from exc


def _run(command: list[str]) -> None:
    try:
        subprocess.run(command, check=True, capture_output=True, text=True, timeout=60)
    except FileNotFoundError as exc:
        raise SchedulerError(f"No se encontró el comando {command[0]!r}.") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        raise SchedulerError(detail) from exc
    except subprocess.TimeoutExpired as exc:
        raise SchedulerError(f"El comando {command[0]!r} excedió 60 segundos.") from exc
