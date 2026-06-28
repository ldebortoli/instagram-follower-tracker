from datetime import UTC, datetime, timedelta, timezone

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


def test_successful_run_is_detected_in_local_date(tmp_path):
    store = Store(tmp_path / "db.sqlite3")
    started = datetime(2026, 6, 28, 2, tzinfo=UTC)
    run_id = store.start_run("personal", started)
    store.finish_run(
        run_id,
        succeeded=True,
        finished_at=started + timedelta(minutes=1),
    )

    argentina = timezone(timedelta(hours=-3))
    assert store.succeeded_on_local_date("personal", "2026-06-27", argentina)
    assert not store.succeeded_on_local_date("personal", "2026-06-28", argentina)
