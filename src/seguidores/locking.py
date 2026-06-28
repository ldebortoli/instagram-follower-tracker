from __future__ import annotations

import json
import os
import time
from pathlib import Path


class AlreadyRunningError(RuntimeError):
    pass


class RunLock:
    def __init__(self, path: Path, stale_after_seconds: int = 6 * 60 * 60):
        self.path = path
        self.stale_after_seconds = stale_after_seconds
        self.acquired = False

    def __enter__(self) -> RunLock:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._clear_stale()
        try:
            descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            raise AlreadyRunningError("Ya hay un chequeo de Seguidores en ejecución.") from exc
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump({"pid": os.getpid(), "created_at": time.time()}, stream)
        self.acquired = True
        return self

    def __exit__(self, *_: object) -> None:
        if self.acquired:
            self.path.unlink(missing_ok=True)
            self.acquired = False

    def _clear_stale(self) -> None:
        try:
            age = time.time() - self.path.stat().st_mtime
        except FileNotFoundError:
            return
        if age > self.stale_after_seconds:
            self.path.unlink(missing_ok=True)
