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


def test_access_cooldown_escalates_and_status_change_resets_counter(tmp_path):
    store = Store(tmp_path / "db.sqlite3")
    started = datetime(2026, 6, 28, 12, tzinfo=UTC)

    first = store.register_cooldown("Owner", 401, started)
    second = store.register_cooldown("owner", 401, started + timedelta(days=1, minutes=1))
    changed = store.register_cooldown("owner", 403, started + timedelta(days=3, minutes=2))

    assert first.blocked_until == started + timedelta(hours=24)
    assert second.failure_count == 2
    assert second.blocked_until == started + timedelta(days=3, minutes=1)
    assert changed.failure_count == 1
    assert changed.blocked_until == started + timedelta(days=4, minutes=2)

    store.clear_cooldown("owner")
    assert store.get_cooldown("owner") is None


def test_429_waits_two_hours_then_one_day_on_third_consecutive_rejection(tmp_path):
    store = Store(tmp_path / "db.sqlite3")
    started = datetime(2026, 6, 28, 12, tzinfo=UTC)

    first = store.register_cooldown("owner", 429, started)
    second_at = started + timedelta(hours=2, minutes=1)
    second = store.register_cooldown("owner", 429, second_at)
    third_at = second_at + timedelta(hours=2, minutes=1)
    third = store.register_cooldown("owner", 429, third_at)

    assert first.failure_count == 1
    assert first.blocked_until == started + timedelta(hours=2)
    assert second.failure_count == 2
    assert second.blocked_until == second_at + timedelta(hours=2)
    assert third.failure_count == 3
    assert third.blocked_until == third_at + timedelta(days=1)


def test_existing_429_cooldown_is_shortened_to_new_policy(tmp_path):
    path = tmp_path / "db.sqlite3"
    store = Store(path)
    started = datetime(2026, 6, 28, 12, tzinfo=UTC)
    with store.connect() as connection:
        connection.execute(
            """
            INSERT INTO request_cooldowns(
                login_username, failure_count, status_code, blocked_until, updated_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                "owner",
                1,
                429,
                (started + timedelta(days=1)).isoformat(),
                started.isoformat(),
            ),
        )

    migrated = Store(path).get_cooldown("owner")

    assert migrated is not None
    assert migrated.blocked_until == started + timedelta(hours=2)
