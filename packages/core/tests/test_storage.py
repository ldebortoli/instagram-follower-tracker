from datetime import UTC, datetime

from seguidores.models import SocialGraph
from seguidores.storage import Store


def test_snapshot_roundtrip_and_history(tmp_path):
    store = Store(tmp_path / "db.sqlite3")
    graph = SocialGraph.from_iterables(["alice", "bob"], ["bob", "carol"])
    captured = datetime(2026, 6, 28, 12, tzinfo=UTC)

    created = store.add_snapshot("personal", graph, captured)
    loaded = store.latest_snapshot("personal")

    assert loaded == created
    assert store.history("personal") == [(captured.isoformat(), 2, 2)]


def test_old_database_tables_do_not_interfere_with_manual_snapshots(tmp_path):
    path = tmp_path / "db.sqlite3"
    store = Store(path)
    with store.connect() as connection:
        connection.execute("CREATE TABLE request_cooldowns (login_username TEXT PRIMARY KEY)")

    reopened = Store(path)
    reopened.add_snapshot(
        "personal",
        SocialGraph.from_iterables(["alice"], ["bob"]),
        datetime(2026, 7, 1, 12, tzinfo=UTC),
    )

    assert reopened.latest_snapshot("personal") is not None
