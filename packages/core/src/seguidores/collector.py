from __future__ import annotations

import json
import sys
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from functools import partial
from getpass import getpass
from pathlib import Path
from typing import Protocol

import requests

from seguidores.config import AccountConfig
from seguidores.http_diagnostics import RequestRecorder
from seguidores.models import SocialGraph
from seguidores.paths import AppPaths
from seguidores.storage import RequestCooldown, Store

PROTECTED_HTTP_STATUSES = {401, 403, 429}


class CollectionError(RuntimeError):
    pass


class TwoFactorRequired(CollectionError):
    pass


@dataclass(frozen=True)
class SessionState:
    code: str
    label: str


class Collector(Protocol):
    def collect(self, account: AccountConfig) -> SocialGraph: ...


class InstagramCollector:
    def __init__(self, paths: AppPaths, *, bypass_cooldown: bool = False):
        self.paths = paths
        self.store = Store(paths.database)
        self.bypass_cooldown = bypass_cooldown

    def collect(self, account: AccountConfig) -> SocialGraph:
        if not self.bypass_cooldown:
            self._raise_if_cooling_down(account)
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
            _attach_recorder(loader)
            _require_session_cookie(loader)
            with _capture_created_sessions(loader):
                profile = _profile_from_web_info(instaloader, loader, account.username)
                followers = {profile.username for profile in profile.get_followers()}
                following = {profile.username for profile in profile.get_followees()}
        except Exception as exc:
            raise self._diagnostic_error(
                f"Instagram no permitió obtener @{account.username}", exc, loader, account
            ) from exc
        self.store.clear_cooldown(account.login_username)
        return SocialGraph.from_iterables(followers, following)

    def login(self, account: AccountConfig) -> Path:
        password = getpass(f"Contraseña de @{account.login_username} (no se guarda): ")
        try:
            return self.login_with_credentials(account, password)
        except TwoFactorRequired:
            code = input("Código de autenticación de dos factores: ").strip()
            return self.login_with_credentials(account, password, code)

    def login_with_credentials(
        self,
        account: AccountConfig,
        password: str,
        two_factor_code: str | None = None,
    ) -> Path:
        if not password:
            raise CollectionError("La contraseña no puede estar vacía.")
        instaloader = _instaloader()
        loader = _loader(instaloader)
        try:
            with _capture_created_sessions(loader):
                loader.login(account.login_username, password)
        except instaloader.exceptions.TwoFactorAuthRequiredException as exc:
            if not two_factor_code:
                raise TwoFactorRequired(
                    "Instagram solicitó el código de autenticación de dos factores."
                ) from exc
            try:
                with _capture_created_sessions(loader):
                    loader.two_factor_login(two_factor_code.strip())
            except Exception as login_exc:
                raise self._diagnostic_error(
                    "El código de autenticación no fue aceptado",
                    login_exc,
                    loader,
                    account,
                ) from login_exc
        except Exception as exc:
            raise self._diagnostic_error(
                "No se pudo iniciar sesión en Instagram", exc, loader, account
            ) from exc
        _attach_recorder(loader)
        self._validate_session(account, loader)
        return self._save_session(account, loader)

    def import_browser_session(self, account: AccountConfig, browser: str) -> Path:
        loader = _loader(_instaloader())
        try:
            cookies = _browser_cookies(browser)
            instagram_cookies = {
                cookie.name: cookie.value
                for cookie in cookies
                if "instagram" in cookie.domain.casefold()
            }
            if not instagram_cookies:
                raise CollectionError(
                    f"No encontré cookies de Instagram en {browser}. "
                    "Iniciá sesión en instagram.com desde ese navegador."
                )
            loader.context.update_cookies(instagram_cookies)
            loader.context.username = account.login_username
            _attach_recorder(loader)
            self._validate_session(account, loader)
        except CollectionError:
            raise
        except Exception as exc:
            raise self._diagnostic_error(
                f"No se pudo importar la sesión desde {browser}", exc, loader, account
            ) from exc
        return self._save_session(account, loader)

    def import_session_id(self, account: AccountConfig, session_id: str) -> Path:
        value = _normalize_session_id(session_id)
        loader = _loader(_instaloader())
        try:
            loader.context.update_cookies({"sessionid": value})
            loader.context.username = account.login_username
            _attach_recorder(loader)
            self._validate_session(account, loader)
        except CollectionError:
            raise
        except Exception as exc:
            raise self._diagnostic_error(
                "No se pudo validar el sessionid ingresado", exc, loader, account
            ) from exc
        return self._save_session(account, loader)

    def session_state(self, account: AccountConfig) -> SessionState:
        if cooldown := self.store.active_cooldown(account.login_username):
            return SessionState("cooldown", _cooldown_label(cooldown))
        session_file = self.session_file(account)
        if not session_file.exists():
            return SessionState("missing", "Falta iniciar sesión")
        loader = _loader(_instaloader())
        try:
            loader.load_session_from_file(account.login_username, str(session_file))
        except Exception:
            return SessionState("invalid", "Sesión dañada")
        if not _session_cookie(loader):
            return SessionState("invalid", "Sesión inválida: falta sessionid")
        return SessionState("saved", "Sesión guardada")

    def _validate_session(self, account: AccountConfig, loader: object) -> None:
        try:
            _require_session_cookie(loader)
            with _capture_created_sessions(loader):
                authenticated_username = loader.test_login()
        except Exception as exc:
            raise self._diagnostic_error(
                "Instagram rechazó la sesión", exc, loader, account
            ) from exc
        if not authenticated_username:
            raise self._diagnostic_error(
                "Instagram no reconoció la sesión. Probá importarla desde el navegador",
                CollectionError("La validación de sesión no devolvió un usuario autenticado."),
                loader,
                account,
            )
        if authenticated_username.casefold() != account.login_username.casefold():
            raise self._diagnostic_error(
                f"El navegador tiene abierta la cuenta @{authenticated_username}, pero esta "
                f"configuración espera @{account.login_username}",
                CollectionError("La sesión corresponde a otra cuenta."),
                loader,
                account,
            )
        loader.context.username = authenticated_username
        self.store.clear_cooldown(account.login_username)

    def _raise_if_cooling_down(self, account: AccountConfig) -> None:
        cooldown = self.store.active_cooldown(account.login_username)
        if cooldown is None:
            return
        raise CollectionError(
            f"Protección activa para @{account.login_username}: no se envió ninguna request. "
            f"{_cooldown_label(cooldown)}. Podés importar una sesión válida del navegador "
            "para levantar el cooldown."
        )

    def _diagnostic_error(
        self,
        message: str,
        exception: Exception,
        loader: object,
        account: AccountConfig | None = None,
    ) -> CollectionError:
        recorder = _attach_recorder(loader)
        cooldown_message = ""
        status_code = recorder.latest_status(PROTECTED_HTTP_STATUSES)
        if status_code is not None and account is not None:
            cooldown = self.store.register_cooldown(account.login_username, status_code)
            cooldown_message = f"\n\nProtección activada. {_cooldown_label(cooldown)}."
        return CollectionError(f"{message}{cooldown_message}\n\n{recorder.format(exception)}")

    def _save_session(self, account: AccountConfig, loader: object) -> Path:
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
    loader = instaloader.Instaloader(
        download_pictures=False,
        download_videos=False,
        download_video_thumbnails=False,
        save_metadata=False,
        compress_json=False,
        quiet=True,
        max_connection_attempts=1,
    )
    recorder = RequestRecorder()
    loader._seguidores_http_recorder = recorder
    _attach_recorder(loader)
    return loader


def _attach_recorder(loader: object) -> RequestRecorder:
    recorder = getattr(loader, "_seguidores_http_recorder", None)
    if recorder is None:
        recorder = RequestRecorder()
        loader._seguidores_http_recorder = recorder
    recorder.attach(loader.context._session)
    return recorder


def _profile_from_web_info(instaloader: object, loader: object, username: str) -> object:
    """Resolve a profile without Instagram's retired GraphQL profile-search query."""
    normalized_username = username.strip().lstrip("@").casefold()
    with _web_profile_session(loader, normalized_username) as session:
        payload = loader.context.get_json(
            "api/v1/users/web_profile_info/",
            params={"username": normalized_username},
            session=session,
        )
    data = payload.get("data") if isinstance(payload, dict) else None
    user = data.get("user") if isinstance(data, dict) else None
    if not isinstance(user, dict):
        raise instaloader.exceptions.ProfileNotExistsException(
            f"Profile {normalized_username} does not exist."
        )
    profile = instaloader.Profile(loader.context, user)
    profile._has_full_metadata = True
    return profile


@contextmanager
def _web_profile_session(loader: object, username: str):
    """Copy the authenticated session and configure Instagram's web profile endpoint."""
    source = loader.context._session
    session = requests.Session()
    session.cookies = requests.utils.cookiejar_from_dict(
        requests.utils.dict_from_cookiejar(source.cookies)
    )
    session.headers = source.headers.copy()
    session.headers.pop("Connection", None)
    session.headers.pop("Content-Length", None)
    session.headers.update(
        {
            "accept": "*/*",
            "referer": f"https://www.instagram.com/{username}/",
            "x-ig-app-id": "936619743392459",
        }
    )
    request_timeout = getattr(loader.context, "request_timeout", None)
    session.request = partial(session.request, timeout=request_timeout)
    _attach_recorder(loader).attach(session)
    try:
        yield session
    finally:
        session.close()


@contextmanager
def _capture_created_sessions(loader: object):
    """Attach diagnostics to every temporary Session created by Instaloader."""
    module = sys.modules.get(loader.context.__class__.__module__)
    requests_module = getattr(module, "requests", None)
    session_factory = getattr(requests_module, "Session", None)
    if module is None or session_factory is None:
        yield
        return

    recorder = _attach_recorder(loader)

    class RequestsProxy:
        def Session(self, *args: object, **kwargs: object) -> object:  # noqa: N802
            session = session_factory(*args, **kwargs)
            recorder.attach(session)
            return session

        def __getattr__(self, name: str) -> object:
            return getattr(requests_module, name)

    proxy = RequestsProxy()
    module.requests = proxy
    try:
        yield
    finally:
        if module.requests is proxy:
            module.requests = requests_module


def _session_cookie(loader: object) -> str:
    return str(loader.context._session.cookies.get_dict().get("sessionid") or "")


def _require_session_cookie(loader: object) -> None:
    if not _session_cookie(loader):
        raise CollectionError(
            "La sesión no contiene un sessionid válido. Importá una sesión activa desde "
            "Chrome, Edge o Firefox."
        )


def _normalize_session_id(value: str) -> str:
    normalized = value.strip()
    if normalized.casefold().startswith("sessionid="):
        normalized = normalized.split("=", maxsplit=1)[1].split(";", maxsplit=1)[0].strip()
    if len(normalized) >= 2 and normalized[0] == normalized[-1] == '"':
        normalized = normalized[1:-1]
    if not normalized:
        raise CollectionError("El sessionid no puede estar vacío.")
    if len(normalized) > 4096 or any(character in normalized for character in ";\r\n\t "):
        raise CollectionError(
            "El sessionid no tiene un formato válido. Pegá sólo el valor de esa cookie."
        )
    return normalized


def _cooldown_label(cooldown: RequestCooldown) -> str:
    until = cooldown.blocked_until.astimezone()
    return (
        f"Cooldown por HTTP {cooldown.status_code} hasta "
        f"{until:%Y-%m-%d %H:%M %Z} "
        f"(rechazo consecutivo {cooldown.failure_count})"
    )


def _browser_cookies(browser: str) -> list[object]:
    try:
        import browser_cookie3
    except ImportError as exc:
        raise CollectionError(
            "Falta browser-cookie3. Reinstalá la aplicación para importar cookies."
        ) from exc
    supported = {
        "brave": browser_cookie3.brave,
        "chrome": browser_cookie3.chrome,
        "chromium": browser_cookie3.chromium,
        "edge": browser_cookie3.edge,
        "firefox": browser_cookie3.firefox,
        "librewolf": browser_cookie3.librewolf,
        "opera": browser_cookie3.opera,
        "opera_gx": browser_cookie3.opera_gx,
        "safari": browser_cookie3.safari,
        "vivaldi": browser_cookie3.vivaldi,
    }
    normalized = browser.casefold()
    if normalized not in supported:
        raise CollectionError(f"Navegador no soportado: {browser}")
    return list(supported[normalized]())
