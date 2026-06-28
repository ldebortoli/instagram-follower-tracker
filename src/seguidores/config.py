from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from seguidores.paths import AppPaths

SCHEMA_VERSION = 1
_ACCOUNT_NAME = re.compile(r"^[A-Za-z0-9_-]{1,40}$")
_INSTAGRAM_USERNAME = re.compile(r"^[A-Za-z0-9._]{1,30}$")


class ConfigError(ValueError):
    pass


@dataclass
class AccountConfig:
    name: str
    username: str
    login_username: str
    enabled: bool = True

    def validate(self) -> None:
        if not _ACCOUNT_NAME.fullmatch(self.name):
            raise ConfigError(
                "El nombre local debe tener 1-40 letras, números, guiones o guiones bajos."
            )
        for label, value in (
            ("usuario de Instagram", self.username),
            ("usuario de inicio de sesión", self.login_username),
        ):
            if not _INSTAGRAM_USERNAME.fullmatch(value):
                raise ConfigError(f"El {label} no tiene un formato válido: {value!r}")
        self.username = self.username.lower()
        self.login_username = self.login_username.lower()


@dataclass
class TelegramConfig:
    enabled: bool = False
    chat_id: str = ""


@dataclass
class NotificationConfig:
    popup: bool = True
    telegram: TelegramConfig = field(default_factory=TelegramConfig)
    notify_without_changes: bool = True


@dataclass
class ScheduleConfig:
    enabled: bool = False
    time: str = "09:00"
    backend: str = ""

    def validate(self) -> None:
        parse_time(self.time)


@dataclass
class Config:
    schema_version: int = SCHEMA_VERSION
    accounts: list[AccountConfig] = field(default_factory=list)
    notifications: NotificationConfig = field(default_factory=NotificationConfig)
    schedule: ScheduleConfig = field(default_factory=ScheduleConfig)

    def validate(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ConfigError(
                f"Versión de configuración {self.schema_version} no soportada "
                f"(esperada: {SCHEMA_VERSION})."
            )
        seen: set[str] = set()
        for account in self.accounts:
            account.validate()
            if account.name.lower() in seen:
                raise ConfigError(f"El nombre de cuenta está repetido: {account.name}")
            seen.add(account.name.lower())
        self.schedule.validate()

    def account(self, name: str) -> AccountConfig:
        for account in self.accounts:
            if account.name.lower() == name.lower():
                return account
        raise ConfigError(f"No existe la cuenta local {name!r}.")


def parse_time(value: str) -> tuple[int, int]:
    try:
        hour_text, minute_text = value.split(":", maxsplit=1)
        hour, minute = int(hour_text), int(minute_text)
    except (ValueError, AttributeError) as exc:
        raise ConfigError("La hora debe tener formato HH:MM.") from exc
    if len(value) != 5 or not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ConfigError("La hora debe tener formato HH:MM y ser válida.")
    return hour, minute


def default_config() -> Config:
    return Config()


def load_config(paths: AppPaths, *, create: bool = False) -> Config:
    if not paths.config.exists():
        if not create:
            raise ConfigError(
                f"No existe la configuración. Ejecutá 'seguidores init'. Ruta: {paths.config}"
            )
        config = default_config()
        save_config(paths, config)
        return config

    try:
        raw = json.loads(paths.config.read_text(encoding="utf-8"))
        telegram = TelegramConfig(**raw.get("notifications", {}).get("telegram", {}))
        notifications_raw = raw.get("notifications", {})
        notifications = NotificationConfig(
            popup=notifications_raw.get("popup", True),
            telegram=telegram,
            notify_without_changes=notifications_raw.get("notify_without_changes", True),
        )
        config = Config(
            schema_version=raw.get("schema_version", 0),
            accounts=[AccountConfig(**item) for item in raw.get("accounts", [])],
            notifications=notifications,
            schedule=ScheduleConfig(**raw.get("schedule", {})),
        )
    except (OSError, json.JSONDecodeError, TypeError) as exc:
        raise ConfigError(f"No se pudo leer {paths.config}: {exc}") from exc
    config.validate()
    return config


def save_config(paths: AppPaths, config: Config) -> None:
    config.validate()
    paths.ensure()
    payload = json.dumps(asdict(config), indent=2, ensure_ascii=False) + "\n"
    _atomic_write(paths.config, payload)


def _atomic_write(path: Path, content: str) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)
