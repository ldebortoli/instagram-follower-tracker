from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ScheduledInvocation:
    executable: Path
    arguments: tuple[str, ...]


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def scheduled_invocation(*, graphical: bool = False) -> ScheduledInvocation:
    """Return the command that survives after the current process exits."""
    executable = Path(sys.executable).resolve()
    if is_frozen():
        arguments = ("--scheduled-run",) if graphical else ("run", "--if-due")
    else:
        arguments = ("-m", "seguidores_desktop", "run", "--if-due")
    return ScheduledInvocation(executable, arguments)
