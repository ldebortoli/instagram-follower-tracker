import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import requests
from seguidores.collector import (
    CollectionError,
    ExportCollector,
    InstagramCollector,
    TwoFactorRequired,
)
from seguidores.config import AccountConfig
from seguidores.paths import AppPaths


def _entry(username):
    return {"string_list_data": [{"value": username, "timestamp": 0}]}


def test_export_collector_reads_nested_json_files(tmp_path):
    relationships = tmp_path / "connections" / "followers_and_following"
    relationships.mkdir(parents=True)
    (relationships / "followers_1.json").write_text(
        json.dumps([_entry("Alice"), _entry("Bob")]), encoding="utf-8"
    )
    (relationships / "following.json").write_text(
        json.dumps({"relationships_following": [_entry("bob"), _entry("Carol")]}),
        encoding="utf-8",
    )

    graph = ExportCollector().collect_directory(tmp_path)

    assert graph.followers == frozenset({"alice", "bob"})
    assert graph.following == frozenset({"bob", "carol"})


def test_export_collector_requires_both_relationship_files(tmp_path):
    (tmp_path / "followers_1.json").write_text("[]", encoding="utf-8")

    with pytest.raises(CollectionError, match="following.json"):
        ExportCollector().collect_directory(tmp_path)


class FakeTwoFactorError(Exception):
    pass


class FakeProfileNotExistsError(Exception):
    pass


class FakeProfile:
    def __init__(self, _context, node):
        self.username = node["username"]
        self._has_full_metadata = False

    def get_followers(self):
        return [SimpleNamespace(username="alice"), SimpleNamespace(username="bob")]

    def get_followees(self):
        return [SimpleNamespace(username="bob"), SimpleNamespace(username="carol")]


class FakeInstaloader:
    Profile = FakeProfile

    class exceptions:
        TwoFactorAuthRequiredException = FakeTwoFactorError
        ProfileNotExistsException = FakeProfileNotExistsError


class FakeLoader:
    def __init__(self, require_2fa=False):
        self.require_2fa = require_2fa
        self.two_factor_code = None
        self.context = FakeContext()

    def login(self, _username, _password):
        if self.require_2fa:
            raise FakeTwoFactorError

    def two_factor_login(self, code):
        self.two_factor_code = code

    def test_login(self):
        return "owner"

    def save_session_to_file(self, filename):
        # Instaloader owns the actual file format; the tracker only selects the path.
        Path(filename).touch()

    def load_session_from_file(self, _username, _filename):
        return None


class FakeFailingLoginLoader(FakeLoader):
    def login(self, username, password):
        session = requests.Session()
        prepared = requests.Request(
            "POST",
            "https://www.instagram.com/api/v1/web/accounts/login/ajax/",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={"username": username, "enc_password": password},
        ).prepare()
        response = requests.Response()
        response.status_code = 401
        response.reason = "Unauthorized"
        response.headers["Content-Type"] = "application/json"
        response._content = b'{"status":"fail","sessionid":"response-secret"}'
        response.request = prepared
        for hook in session.hooks["response"]:
            hook(response)
        raise RuntimeError("login rejected")


class FakeContext:
    def __init__(self):
        self._session = requests.Session()
        self._session.cookies.set("sessionid", "valid-for-test")
        self.username = "owner"
        self.request_timeout = 30
        self.web_requests = []

    def update_cookies(self, cookies):
        self._session.cookies.update(cookies)

    def get_json(self, path, params, session):
        self.web_requests.append((path, params, session))
        return {"data": {"user": {"id": "1", "username": params["username"]}}}


class FakeForbiddenContext(FakeContext):
    def get_json(self, path, params, session):
        self.web_requests.append((path, params, session))
        prepared = requests.Request(
            "GET",
            f"https://www.instagram.com/{path}",
            params=params,
        ).prepare()
        response = requests.Response()
        response.status_code = 403
        response.reason = "Forbidden"
        response.headers["Content-Type"] = "application/json"
        response._content = b'{"status":"fail","message":"forbidden"}'
        response.request = prepared
        for hook in session.hooks["response"]:
            hook(response)
        raise RuntimeError("profile lookup rejected")


def test_collect_uses_web_profile_info_instead_of_retired_graphql(tmp_path, monkeypatch):
    loader = FakeLoader()
    monkeypatch.setattr("seguidores.collector._instaloader", lambda: FakeInstaloader)
    monkeypatch.setattr("seguidores.collector._loader", lambda _module: loader)
    collector = InstagramCollector(AppPaths(tmp_path))
    account = AccountConfig("personal", "Target_User", "owner")
    collector.session_file(account).parent.mkdir(parents=True)
    collector.session_file(account).touch()

    graph = collector.collect(account)

    assert graph.followers == frozenset({"alice", "bob"})
    assert graph.following == frozenset({"bob", "carol"})
    path, params, web_session = loader.context.web_requests[0]
    assert path == "api/v1/users/web_profile_info/"
    assert params == {"username": "target_user"}
    assert web_session is not loader.context._session
    assert web_session.headers["x-ig-app-id"] == "936619743392459"
    assert web_session.headers["referer"] == "https://www.instagram.com/target_user/"
    assert web_session.cookies.get("sessionid") == "valid-for-test"


def test_collect_captures_web_profile_403_and_activates_cooldown(tmp_path, monkeypatch):
    loader = FakeLoader()
    loader.context = FakeForbiddenContext()
    monkeypatch.setattr("seguidores.collector._instaloader", lambda: FakeInstaloader)
    monkeypatch.setattr("seguidores.collector._loader", lambda _module: loader)
    collector = InstagramCollector(AppPaths(tmp_path))
    account = AccountConfig("personal", "target", "owner")
    collector.session_file(account).parent.mkdir(parents=True)
    collector.session_file(account).touch()

    with pytest.raises(CollectionError) as error:
        collector.collect(account)

    detail = str(error.value)
    assert "GET https://www.instagram.com/api/v1/users/web_profile_info/" in detail
    assert "HTTP 403 Forbidden" in detail
    assert "Protección activada" in detail
    cooldown = collector.store.active_cooldown("owner")
    assert cooldown is not None
    assert cooldown.status_code == 403


def test_login_with_credentials_saves_session_without_password(tmp_path, monkeypatch):
    loader = FakeLoader()
    monkeypatch.setattr("seguidores.collector._instaloader", lambda: FakeInstaloader)
    monkeypatch.setattr("seguidores.collector._loader", lambda _module: loader)
    account = AccountConfig("personal", "owner", "owner")
    collector = InstagramCollector(AppPaths(tmp_path))
    collector.store.register_cooldown("owner", 401)

    session = collector.login_with_credentials(account, "secret")

    assert session.exists()
    assert "secret" not in session.read_text(encoding="utf-8")
    assert collector.store.active_cooldown("owner") is None


def test_login_with_credentials_requests_and_accepts_2fa(tmp_path, monkeypatch):
    loader = FakeLoader(require_2fa=True)
    monkeypatch.setattr("seguidores.collector._instaloader", lambda: FakeInstaloader)
    monkeypatch.setattr("seguidores.collector._loader", lambda _module: loader)
    collector = InstagramCollector(AppPaths(tmp_path))
    account = AccountConfig("personal", "owner", "owner")

    with pytest.raises(TwoFactorRequired):
        collector.login_with_credentials(account, "secret")

    session = collector.login_with_credentials(account, "secret", "123456")

    assert session.exists()
    assert loader.two_factor_code == "123456"


def test_login_failure_includes_temporary_session_exchange_without_secrets(tmp_path, monkeypatch):
    loader = FakeFailingLoginLoader()
    monkeypatch.setattr("seguidores.collector._instaloader", lambda: FakeInstaloader)
    monkeypatch.setattr("seguidores.collector._loader", lambda _module: loader)
    collector = InstagramCollector(AppPaths(tmp_path))
    account = AccountConfig("personal", "owner", "owner")

    with pytest.raises(CollectionError) as error:
        collector.login_with_credentials(account, "password-secret")

    detail = str(error.value)
    assert "POST https://www.instagram.com/api/v1/web/accounts/login/ajax/" in detail
    assert "HTTP 401 Unauthorized" in detail
    assert "password-secret" not in detail
    assert "response-secret" not in detail
    cooldown = collector.store.active_cooldown("owner")
    assert cooldown is not None
    assert cooldown.status_code == 401


def test_collect_does_not_send_requests_during_active_cooldown(tmp_path, monkeypatch):
    collector = InstagramCollector(AppPaths(tmp_path))
    collector.store.register_cooldown("owner", 401)
    account = AccountConfig("personal", "target", "owner")
    called = False

    def unexpected_instaloader():
        nonlocal called
        called = True

    monkeypatch.setattr("seguidores.collector._instaloader", unexpected_instaloader)

    with pytest.raises(CollectionError, match="no se envió ninguna request"):
        collector.collect(account)

    assert not called


def test_collect_can_bypass_active_cooldown_for_one_explicit_attempt(tmp_path, monkeypatch):
    loader = FakeLoader()
    monkeypatch.setattr("seguidores.collector._instaloader", lambda: FakeInstaloader)
    monkeypatch.setattr("seguidores.collector._loader", lambda _module: loader)
    collector = InstagramCollector(AppPaths(tmp_path), bypass_cooldown=True)
    account = AccountConfig("personal", "target", "owner")
    collector.session_file(account).parent.mkdir(parents=True)
    collector.session_file(account).touch()
    collector.store.register_cooldown("owner", 429)

    graph = collector.collect(account)

    assert graph.followers == frozenset({"alice", "bob"})
    assert loader.context.web_requests
    assert collector.store.active_cooldown("owner") is None


def test_login_rejects_empty_session_cookie(tmp_path, monkeypatch):
    loader = FakeLoader()
    loader.context._session.cookies.set("sessionid", "")
    monkeypatch.setattr("seguidores.collector._instaloader", lambda: FakeInstaloader)
    monkeypatch.setattr("seguidores.collector._loader", lambda _module: loader)
    collector = InstagramCollector(AppPaths(tmp_path))
    account = AccountConfig("personal", "owner", "owner")

    with pytest.raises(CollectionError, match="sessionid válido") as error:
        collector.login_with_credentials(account, "secret")

    assert "Diagnóstico HTTP" in str(error.value)
    assert not collector.session_file(account).exists()


def test_browser_import_filters_instagram_cookies_and_validates(tmp_path, monkeypatch):
    loader = FakeLoader()
    loader.context._session.cookies.clear()
    cookies = [
        SimpleNamespace(name="sessionid", value="browser-session", domain=".instagram.com"),
        SimpleNamespace(name="unrelated", value="secret", domain=".example.com"),
    ]
    monkeypatch.setattr("seguidores.collector._instaloader", lambda: FakeInstaloader)
    monkeypatch.setattr("seguidores.collector._loader", lambda _module: loader)
    monkeypatch.setattr("seguidores.collector._browser_cookies", lambda _browser: cookies)
    collector = InstagramCollector(AppPaths(tmp_path))
    account = AccountConfig("personal", "owner", "owner")

    session = collector.import_browser_session(account, "edge")

    assert session.exists()
    assert loader.context._session.cookies.get("sessionid") == "browser-session"
    assert loader.context._session.cookies.get("unrelated") is None


def test_manual_session_id_is_extracted_validated_and_clears_cooldown(tmp_path, monkeypatch):
    loader = FakeLoader()
    loader.context._session.cookies.clear()
    monkeypatch.setattr("seguidores.collector._instaloader", lambda: FakeInstaloader)
    monkeypatch.setattr("seguidores.collector._loader", lambda _module: loader)
    collector = InstagramCollector(AppPaths(tmp_path))
    collector.store.register_cooldown("owner", 401)
    account = AccountConfig("personal", "target", "owner")

    session = collector.import_session_id(
        account, 'sessionid="manual-session-value"; Path=/; Secure'
    )

    assert session.exists()
    assert loader.context._session.cookies.get("sessionid") == "manual-session-value"
    assert collector.store.active_cooldown("owner") is None


@pytest.mark.parametrize("value", ["", "foo=bar; sessionid=value", "contains whitespace"])
def test_manual_session_id_rejects_invalid_values(tmp_path, value):
    collector = InstagramCollector(AppPaths(tmp_path))
    account = AccountConfig("personal", "owner", "owner")

    with pytest.raises(CollectionError, match="sessionid"):
        collector.import_session_id(account, value)
