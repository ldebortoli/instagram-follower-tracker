import json
from pathlib import Path

import pytest

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


class FakeInstaloader:
    class exceptions:
        TwoFactorAuthRequiredException = FakeTwoFactorError


class FakeLoader:
    def __init__(self, require_2fa=False):
        self.require_2fa = require_2fa
        self.two_factor_code = None

    def login(self, _username, _password):
        if self.require_2fa:
            raise FakeTwoFactorError

    def two_factor_login(self, code):
        self.two_factor_code = code

    def save_session_to_file(self, filename):
        # Instaloader owns the actual file format; the tracker only selects the path.
        Path(filename).touch()


def test_login_with_credentials_saves_session_without_password(tmp_path, monkeypatch):
    loader = FakeLoader()
    monkeypatch.setattr("seguidores.collector._instaloader", lambda: FakeInstaloader)
    monkeypatch.setattr("seguidores.collector._loader", lambda _module: loader)
    account = AccountConfig("personal", "owner", "owner")

    session = InstagramCollector(AppPaths(tmp_path)).login_with_credentials(account, "secret")

    assert session.exists()
    assert "secret" not in session.read_text(encoding="utf-8")


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
