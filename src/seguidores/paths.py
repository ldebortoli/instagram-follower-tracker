from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppPaths:
    root: Path

    @property
    def config(self) -> Path:
        return self.root / "config.json"

    @property
    def database(self) -> Path:
        return self.root / "seguidores.sqlite3"

    @property
    def sessions(self) -> Path:
        return self.root / "sessions"

    @property
    def logs(self) -> Path:
        return self.root / "logs"

    @property
    def lock(self) -> Path:
        return self.root / "run.lock"

    def ensure(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.sessions.mkdir(parents=True, exist_ok=True)
        self.logs.mkdir(parents=True, exist_ok=True)


def app_paths() -> AppPaths:
    override = os.environ.get("SEGUIDORES_HOME")
    if override:
        return AppPaths(Path(override).expanduser().resolve())

    home = Path.home()
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", home / "AppData" / "Roaming"))
        root = base / "Seguidores"
    elif sys.platform == "darwin":
        root = home / "Library" / "Application Support" / "Seguidores"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", home / ".config"))
        root = base / "seguidores"
    return AppPaths(root)
