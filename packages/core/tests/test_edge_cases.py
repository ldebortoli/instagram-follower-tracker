import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from seguidores import collector, config, paths, report, storage
from seguidores.models import SocialGraph, compare_graphs


@pytest.mark.parametrize(("followers", "following"), [([], ["unused"]), (["unused"], [])])
def test_export_requires_both_lists(followers, following):
    with pytest.raises(collector.CollectionError, match="al menos"):
        collector.ExportCollector().collect_files(followers, following)


@pytest.mark.parametrize("empty", ["followers", "following"])
def test_export_rejects_empty_relations(empty, tmp_path):
    files = []
    for kind in ("followers", "following"):
        path = tmp_path / f"{kind}.json"
        payload = [] if kind == empty else [{"title": "synthetic"}]
        path.write_text(json.dumps(payload))
        files.append(path)
    with pytest.raises(collector.CollectionError, match="no contiene usuarios"):
        collector.ExportCollector().collect_files([files[0]], [files[1]])


@pytest.mark.parametrize("payload", [42, {"relationships_followers": {}}])
def test_export_rejects_wrong_container(payload, tmp_path):
    path = tmp_path / "followers.json"
    path.write_text(json.dumps(payload))
    with pytest.raises(collector.CollectionError):
        collector.ExportCollector()._read_relationship_file(path, "followers")


def test_export_ignores_bad_items_and_rejects_threads_links(tmp_path):
    path = tmp_path / "followers.json"
    path.write_text(json.dumps([None, {"string_list_data": [None, {"href": ""}]}]))
    assert collector.ExportCollector()._read_relationship_file(path, "followers") == set()
    path.write_text(json.dumps([{"string_list_data": [{"href": "https://threads.net/fixture"}]}]))
    with pytest.raises(collector.CollectionError, match="enlaces de Threads"):
        collector.ExportCollector()._read_relationship_file(path, "followers")
    assert collector._username_from_url("https://instagram.com/_u") == ""


def test_export_reports_unreadable_and_missing_files(tmp_path):
    missing = tmp_path / "missing.json"
    with pytest.raises(collector.CollectionError, match="No existe el archivo"):
        collector._load_json(missing)
    missing.write_text("invalid json")
    with pytest.raises(collector.CollectionError, match="No se pudo leer"):
        collector._load_json(missing)
    with pytest.raises(collector.CollectionError, match="No existe el directorio"):
        collector.ExportCollector().collect_directory(tmp_path / "missing")


@pytest.mark.parametrize(
    "account", [config.AccountConfig("", "valid"), config.AccountConfig("valid", "invalid!")]
)
def test_config_rejects_invalid_identifiers(account):
    with pytest.raises(config.ConfigError):
        account.validate()


def test_config_reports_schema_and_parse_errors(tmp_path):
    app = paths.AppPaths(tmp_path)
    with pytest.raises(config.ConfigError, match="No existe"):
        config.load_config(app)
    with pytest.raises(config.ConfigError, match="no soportada"):
        config.Config(schema_version=999).validate()
    with pytest.raises(config.ConfigError, match="No existe la cuenta"):
        config.Config().account("missing")
    for payload in ('{"schema_version":999}', "invalid", '{"accounts":[{}]}'):
        app.config.write_text(payload)
        with pytest.raises(config.ConfigError):
            config.load_config(app)


@pytest.mark.parametrize("platform", ["win32", "darwin", "linux"])
def test_default_paths_use_only_synthetic_home(platform, tmp_path, monkeypatch):
    monkeypatch.delenv("SEGUIDORES_HOME")
    monkeypatch.setattr(sys, "platform", platform)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("APPDATA", str(tmp_path / "roaming"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    expected = {
        "win32": tmp_path / "roaming/Seguidores",
        "darwin": tmp_path / "Library/Application Support/Seguidores",
        "linux": tmp_path / "xdg/seguidores",
    }[platform]
    assert paths.app_paths().root == expected
    monkeypatch.setenv("SEGUIDORES_HOME", str(tmp_path / "override"))
    app = paths.app_paths()
    assert app.root == tmp_path / "override"
    assert app.sessions == app.root / "sessions"
    assert app.lock == app.root / "run.lock"


def test_popup_summaries_cover_baseline_and_changes():
    graph = SocialGraph.from_iterables(["fixture"], ["other"])
    for previous, expected in ((None, "Primera captura"), (graph, "Nuevos: 0")):
        comparison = compare_graphs(
            account_name="fixture",
            username="fixture",
            current=graph,
            previous=previous,
            captured_at=datetime.now(UTC),
        )
        assert expected in report.format_popup(comparison)
    with pytest.raises(TypeError):
        SocialGraph.from_iterables(None, [])
    with pytest.raises(ValueError, match="zona horaria"):
        storage._as_utc(datetime(2026, 1, 1))


def test_storage_rolls_back_partial_transaction(tmp_path):
    store = storage.Store(tmp_path / "synthetic.sqlite3")
    with pytest.raises(RuntimeError, match="rollback"), store.connect() as connection:
        connection.execute("INSERT INTO snapshots VALUES (1, 'fixture', '2026', 0, 0)")
        raise RuntimeError("rollback")
    with store.connect() as connection:
        assert connection.execute("SELECT count(*) FROM snapshots").fetchone()[0] == 0
