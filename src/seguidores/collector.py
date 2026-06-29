from __future__ import annotations

import json
import sys
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from getpass import getpass
from pathlib import Path
from typing import Protocol

from seguidores.config import AccountConfig
from seguidores.http_diagnostics import RequestRecorder
from seguidores.models import SocialGraph
from seguidores.paths import AppPaths


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
            _attach_recorder(loader)
            _require_session_cookie(loader)
            profile = instaloader.Profile.from_username(loader.context, account.username)
            followers = {profile.username for profile in profile.get_followers()}
            following = {profile.username for profile in profile.get_followees()}
        except Exception as exc:
            raise _diagnostic_error(
                f"Instagram no permitió obtener @{account.username}", exc, loader
            ) from exc
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
            with _capture_login_requests(loader):
                loader.login(account.login_username, password)
        except instaloader.exceptions.TwoFactorAuthRequiredException as exc:
            if not two_factor_code:
                raise TwoFactorRequired(
                    "Instagram solicitó el código de autenticación de dos factores."
                ) from exc
            try:
                loader.two_factor_login(two_factor_code.strip())
            except Exception as login_exc:
                raise _diagnostic_error(
                    "El código de autenticación no fue aceptado", login_exc, loader
                ) from login_exc
        except Exception as exc:
            raise _diagnostic_error("No se pudo iniciar sesión en Instagram", exc, loader) from exc
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
            raise _diagnostic_error(
                f"No se pudo importar la sesión desde {browser}", exc, loader
            ) from exc
        return self._save_session(account, loader)

    def session_state(self, account: AccountConfig) -> SessionState:
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
            authenticated_username = loader.test_login()
        except Exception as exc:
            raise _diagnostic_error("Instagram rechazó la sesión", exc, loader) from exc
        if not authenticated_username:
            raise _diagnostic_error(
                "Instagram no reconoció la sesión. Probá importarla desde el navegador",
                CollectionError("La validación de sesión no devolvió un usuario autenticado."),
                loader,
            )
        if authenticated_username.casefold() != account.login_username.casefold():
            raise _diagnostic_error(
                f"El navegador tiene abierta la cuenta @{authenticated_username}, pero esta "
                f"configuración espera @{account.login_username}",
                CollectionError("La sesión corresponde a otra cuenta."),
                loader,
            )
        loader.context.username = authenticated_username

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


def _diagnostic_error(message: str, exception: Exception, loader: object) -> CollectionError:
    diagnostic = _attach_recorder(loader).format(exception)
    return CollectionError(f"{message}\n\n{diagnostic}")


@contextmanager
def _capture_login_requests(loader: object):
    """Attach diagnostics to the temporary Session created by Instaloader.login()."""
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
