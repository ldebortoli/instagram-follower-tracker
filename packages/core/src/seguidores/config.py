from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from seguidores.paths import AppPaths

SCHEMA_VERSION = 2
_ACCOUNT_NAME = re.compile(r"^[A-Za-z0-9_-]{1,40}$")
_INSTAGRAM_USERNAME = re.compile(r"^[A-Za-z0-9._]{1,30}$")


class ConfigError(ValueError):
    pass


@dataclass
class AccountConfig:
    name: str
    username: str

    def validate(self) -> None:
        if not _ACCOUNT_NAME.fullmatch(self.name):
            raise ConfigError(
                "El nombre local debe tener 1-40 letras, números, guiones o guiones bajos."
            )
        if not _INSTAGRAM_USERNAME.fullmatch(self.username):
            raise ConfigError(
                f"El usuario de Instagram no tiene un formato válido: {self.username!r}"
            )
        self.username = self.username.casefold()


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
class Config:
    schema_version: int = SCHEMA_VERSION
    accounts: list[AccountConfig] = field(default_factory=list)
    notifications: NotificationConfig = field(default_factory=NotificationConfig)
    legacy_cleanup_done: bool = False

    def validate(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ConfigError(
                f"Versión de configuración {self.schema_version} no soportada "
                f"(esperada: {SCHEMA_VERSION})."
            )
        seen: set[str] = set()
        for account in self.accounts:
            account.validate()
            if account.name.casefold() in seen:
                raise ConfigError(f"El nombre de cuenta está repetido: {account.name}")
            seen.add(account.name.casefold())

    def account(self, name: str) -> AccountConfig:
        for account in self.accounts:
            if account.name.casefold() == name.casefold():
                return account
        raise ConfigError(f"No existe la cuenta local {name!r}.")


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
        source_schema = raw.get("schema_version", 1)
        if source_schema not in {1, SCHEMA_VERSION}:
            raise ConfigError(
                f"Versión de configuración {source_schema} no soportada "
                f"(esperadas: 1 o {SCHEMA_VERSION})."
            )
        notifications_raw = raw.get("notifications", {})
        notifications = NotificationConfig(
            popup=notifications_raw.get("popup", True),
            telegram=TelegramConfig(**notifications_raw.get("telegram", {})),
            notify_without_changes=notifications_raw.get("notify_without_changes", True),
        )
        accounts = [
            AccountConfig(name=str(item["name"]), username=str(item["username"]))
            for item in raw.get("accounts", [])
        ]
        config = Config(
            accounts=accounts,
            notifications=notifications,
            legacy_cleanup_done=bool(raw.get("legacy_cleanup_done", False)),
        )
    except ConfigError:
        raise
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ConfigError(f"No se pudo leer {paths.config}: {exc}") from exc
    config.validate()
    return config


def save_config(paths: AppPaths, config: Config) -> None:
    config.schema_version = SCHEMA_VERSION
    config.validate()
    paths.ensure()
    payload = json.dumps(asdict(config), indent=2, ensure_ascii=False) + "\n"
    _atomic_write(paths.config, payload)


def _atomic_write(path: Path, content: str) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)
