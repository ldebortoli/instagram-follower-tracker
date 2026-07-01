from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlparse

from seguidores.models import SocialGraph

_USERNAME = re.compile(r"^[A-Za-z0-9._]{1,30}$")
_THREADS_KEYS = {
    "text_post_app_text_post_app_followers",
    "text_post_app_text_post_app_following",
}


class CollectionError(RuntimeError):
    pass


class ExportCollector:
    """Lee los JSON descargados desde el Centro de cuentas de Instagram."""

    FOLLOWER_PATTERN = "followers*.json"
    FOLLOWING_NAMES = ("following.json", "following_1.json")

    def collect_files(
        self,
        follower_files: list[Path] | tuple[Path, ...],
        following_files: list[Path] | tuple[Path, ...],
    ) -> SocialGraph:
        if not follower_files:
            raise CollectionError("Elegí al menos un archivo JSON de seguidores.")
        if not following_files:
            raise CollectionError("Elegí al menos un archivo JSON de seguidos.")

        followers: set[str] = set()
        for path in follower_files:
            followers.update(self._read_relationship_file(Path(path), "followers"))

        following: set[str] = set()
        for path in following_files:
            following.update(self._read_relationship_file(Path(path), "following"))

        if not followers:
            raise CollectionError(
                "El archivo de seguidores no contiene usuarios de Instagram. "
                "Comprobá que elegiste followers_1.json y no el reporte de Threads."
            )
        if not following:
            raise CollectionError(
                "El archivo de seguidos no contiene usuarios de Instagram. "
                "Comprobá que elegiste following.json."
            )
        return SocialGraph.from_iterables(followers, following)

    def collect_directory(self, directory: Path) -> SocialGraph:
        directory = directory.expanduser().resolve()
        if not directory.is_dir():
            raise CollectionError(f"No existe el directorio de exportación: {directory}")
        follower_files = sorted(directory.rglob(self.FOLLOWER_PATTERN))
        following_files = sorted(
            candidate
            for name in self.FOLLOWING_NAMES
            for candidate in directory.rglob(name)
            if "hashtag" not in str(candidate).casefold()
        )
        return self.collect_files(follower_files, following_files)

    def _read_relationship_file(self, path: Path, relationship: str) -> set[str]:
        payload = _load_json(path)
        if isinstance(payload, dict) and _THREADS_KEYS.intersection(payload):
            raise CollectionError(
                f"{path.name} corresponde a Threads, no a Instagram. "
                "En la descarga elegí la sección de seguidores y seguidos de Instagram."
            )

        preferred_key = (
            "relationships_followers" if relationship == "followers" else "relationships_following"
        )
        if isinstance(payload, dict):
            if preferred_key not in payload:
                keys = ", ".join(sorted(payload)) or "sin claves"
                raise CollectionError(
                    f"{path.name} no parece ser un archivo de {relationship} de Instagram "
                    f"(claves encontradas: {keys})."
                )
            entries = payload[preferred_key]
        elif isinstance(payload, list):
            entries = payload
        else:
            raise CollectionError(f"{path.name} no tiene una estructura JSON compatible.")

        if not isinstance(entries, list):
            raise CollectionError(f"{path.name} no contiene una lista de relaciones.")

        usernames: set[str] = set()
        saw_threads_link = False
        for item in entries:
            if not isinstance(item, dict):
                continue
            data = item.get("string_list_data")
            data = data if isinstance(data, list) else []
            item_usernames: set[str] = set()
            for value in data:
                if not isinstance(value, dict):
                    continue
                href = str(value.get("href") or "")
                saw_threads_link = saw_threads_link or _is_threads_url(href)
                username = value.get("value") or _username_from_url(href)
                if username := _normalize_username(username):
                    item_usernames.add(username)
            if not item_usernames and (username := _normalize_username(item.get("title"))):
                item_usernames.add(username)
            usernames.update(item_usernames)

        if saw_threads_link:
            raise CollectionError(
                f"{path.name} contiene enlaces de Threads, no de Instagram. "
                "Seleccioná el JSON de seguidores de Instagram."
            )
        return usernames


def _load_json(path: Path) -> object:
    try:
        return json.loads(path.expanduser().read_text(encoding="utf-8-sig"))
    except FileNotFoundError as exc:
        raise CollectionError(f"No existe el archivo: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise CollectionError(f"No se pudo leer {path}: {exc}") from exc


def _normalize_username(value: object) -> str | None:
    username = str(value or "").strip().lstrip("@").casefold()
    return username if _USERNAME.fullmatch(username) else None


def _username_from_url(value: str) -> str:
    if not value:
        return ""
    parts = [part for part in urlparse(value).path.split("/") if part]
    if parts and parts[-1] == "_u":
        return ""
    return parts[-1] if parts else ""


def _is_threads_url(value: str) -> bool:
    return urlparse(value).netloc.casefold() in {
        "threads.net",
        "www.threads.net",
        "threads.com",
        "www.threads.com",
    }
