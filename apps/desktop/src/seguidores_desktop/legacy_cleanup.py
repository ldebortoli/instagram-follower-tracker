from __future__ import annotations

import shutil
import subprocess
import sys
from contextlib import suppress
from pathlib import Path

from seguidores.paths import AppPaths

WINDOWS_TASK = "SeguidoresInstagram"
MAC_LABEL = "com.seguidores.instagram.daily"
LINUX_UNIT = "seguidores-instagram"
CRON_MARKER = "# seguidores-instagram managed"


class LegacyCleanupError(RuntimeError):
    pass


def cleanup_legacy_state(paths: AppPaths) -> None:
    """Retira credenciales y schedulers creados por las versiones con acceso directo."""
    if sys.platform == "win32":
        _cleanup_windows_task()
    elif sys.platform == "darwin":
        _cleanup_macos_task()
    else:
        _cleanup_linux_tasks()
    if paths.sessions.exists():
        shutil.rmtree(paths.sessions)
    paths.lock.unlink(missing_ok=True)


def _cleanup_windows_task() -> None:
    result = subprocess.run(
        ["schtasks", "/Delete", "/TN", WINDOWS_TASK, "/F"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    detail = f"{result.stdout}\n{result.stderr}".casefold()
    missing_markers = (
        "cannot find",
        "does not exist",
        "no se puede encontrar",
        "no puede encontrar",
        "no existe",
    )
    missing = any(marker in detail for marker in missing_markers)
    if result.returncode and not missing:
        raise LegacyCleanupError(
            "No se pudo quitar la tarea diaria antigua de Windows. "
            f"Detalle: {(result.stderr or result.stdout).strip()}"
        )


def _cleanup_macos_task() -> None:
    plist = Path.home() / "Library" / "LaunchAgents" / f"{MAC_LABEL}.plist"
    if plist.exists():
        subprocess.run(
            ["launchctl", "unload", str(plist)], capture_output=True, timeout=30, check=False
        )
        plist.unlink(missing_ok=True)


def _cleanup_linux_tasks() -> None:
    user_units = Path.home() / ".config" / "systemd" / "user"
    timer = user_units / f"{LINUX_UNIT}.timer"
    service = user_units / f"{LINUX_UNIT}.service"
    if timer.exists() or service.exists():
        subprocess.run(
            ["systemctl", "--user", "disable", "--now", f"{LINUX_UNIT}.timer"],
            capture_output=True,
            timeout=30,
            check=False,
        )
        timer.unlink(missing_ok=True)
        service.unlink(missing_ok=True)
        subprocess.run(
            ["systemctl", "--user", "daemon-reload"],
            capture_output=True,
            timeout=30,
            check=False,
        )
    with suppress(OSError, subprocess.SubprocessError):
        current = subprocess.run(
            ["crontab", "-l"], capture_output=True, text=True, timeout=15, check=False
        )
        if current.returncode == 0 and CRON_MARKER in current.stdout:
            lines = current.stdout.splitlines()
            filtered: list[str] = []
            skip_next = False
            for line in lines:
                if line.strip() == CRON_MARKER:
                    skip_next = True
                    continue
                if skip_next:
                    skip_next = False
                    continue
                filtered.append(line)
            subprocess.run(
                ["crontab", "-"],
                input="\n".join(filtered) + "\n",
                text=True,
                capture_output=True,
                timeout=15,
                check=False,
            )
