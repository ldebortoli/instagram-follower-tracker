from __future__ import annotations

import json
from contextlib import suppress
from getpass import getpass
from pathlib import Path
from typing import Protocol

from seguidores.config import AccountConfig
from seguidores.models import SocialGraph
from seguidores.paths import AppPaths


class CollectionError(RuntimeError):
    pass


class Collector(Protocol):
    def collect(self, account: AccountConfig) -> SocialGraph: ...


class InstagramCollector:
    def __init__(self, paths: AppPaths):
        self.paths = paths

    def collect(self, account: AccountConfig) -> SocialGraph:
        instaloader = _instaloader()
        loader = _loader(instaloader)
        session_file = self.session_file(account)
        if not session_file.exists():
            raise CollectionError(
                f"No hay sesión para {account.name}. Ejecutá "
                f"'seguidores auth login {account.name}'."
            )
        try:
            loader.load_session_from_file(account.login_username, str(session_file))
            profile = instaloader.Profile.from_username(loader.context, account.username)
            followers = {profile.username for profile in profile.get_followers()}
            following = {profile.username for profile in profile.get_followees()}
        except Exception as exc:
            raise CollectionError(
                f"Instagram no permitió obtener @{account.username}: {exc}"
            ) from exc
        return SocialGraph.from_iterables(followers, following)

    def login(self, account: AccountConfig) -> Path:
        instaloader = _instaloader()
        loader = _loader(instaloader)
        password = getpass(f"Contraseña de @{account.login_username} (no se guarda): ")
        try:
            loader.login(account.login_username, password)
        except instaloader.exceptions.TwoFactorAuthRequiredException:
            code = input("Código de autenticación de dos factores: ").strip()
            loader.two_factor_login(code)
        except Exception as exc:
            raise CollectionError(f"No se pudo iniciar sesión en Instagram: {exc}") from exc
        self.paths.ensure()
        session_file = self.session_file(account)
        loader.save_session_to_file(str(session_file))
        with suppress(OSError):
            session_file.chmod(0o600)
        return session_file

    def session_file(self, account: AccountConfig) -> Path:
        return self.paths.sessions / f"instagram-{account.name}.session"


class ExportCollector:
    """Reads the JSON files produced by Instagram's account export."""

    FOLLOWER_PATTERN = "followers_*.json"
    FOLLOWING_NAMES = ("following.json", "following_1.json")

    def collect_directory(self, directory: Path) -> SocialGraph:
        directory = directory.expanduser().resolve()
        if not directory.is_dir():
            raise CollectionError(f"No existe el directorio de exportación: {directory}")

        follower_files = sorted(directory.rglob(self.FOLLOWER_PATTERN))
        following_files = [
            candidate
            for name in self.FOLLOWING_NAMES
            for candidate in directory.rglob(name)
            if "hashtag" not in str(candidate).lower()
        ]
        if not follower_files or not following_files:
            raise CollectionError(
                "No encontré followers_*.json y following.json en la exportación. "
                "Pedí la descarga en formato JSON."
            )

        followers: set[str] = set()
        for path in follower_files:
            followers.update(_relationship_values(_load_json(path), "relationships_followers"))

        following: set[str] = set()
        for path in following_files:
            following.update(_relationship_values(_load_json(path), "relationships_following"))
        return SocialGraph.from_iterables(followers, following)


def _relationship_values(payload: object, preferred_key: str) -> set[str]:
    if isinstance(payload, dict):
        entries = payload.get(preferred_key, [])
    elif isinstance(payload, list):
        entries = payload
    else:
        entries = []
    result: set[str] = set()
    for item in entries:
        if not isinstance(item, dict):
            continue
        data = item.get("string_list_data", [])
        for value in data:
            if isinstance(value, dict) and value.get("value"):
                result.add(str(value["value"]))
    return result


def _load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CollectionError(f"No se pudo leer {path}: {exc}") from exc


def _instaloader():
    try:
        import instaloader
    except ImportError as exc:
        raise CollectionError(
            "Falta Instaloader. Reinstalá el proyecto con 'pip install -e .'."
        ) from exc
    return instaloader


def _loader(instaloader):
    return instaloader.Instaloader(
        download_pictures=False,
        download_videos=False,
        download_video_thumbnails=False,
        save_metadata=False,
        compress_json=False,
        quiet=True,
    )
