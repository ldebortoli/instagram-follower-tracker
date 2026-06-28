from datetime import UTC, datetime

from seguidores.app import Tracker
from seguidores.config import AccountConfig, Config
from seguidores.models import SocialGraph
from seguidores.paths import AppPaths


class FakeCollector:
    def __init__(self, graph):
        self.graph = graph
        self.calls = 0

    def collect(self, _account):
        self.calls += 1
        return self.graph


def configured_tracker(tmp_path, collector):
    config = Config(accounts=[AccountConfig("personal", "owner", "owner")])
    config.notifications.popup = False
    config.schedule.time = "09:00"
    return Tracker(AppPaths(tmp_path), config, collector)


def test_tracker_records_baseline_and_changes(tmp_path):
    collector = FakeCollector(SocialGraph.from_iterables(["alice", "bob"], ["alice"]))
    tracker = configured_tracker(tmp_path, collector)
    first = tracker.run(now=datetime(2026, 6, 28, 10, tzinfo=UTC))

    assert first.completed[0].comparison.is_baseline

    collector.graph = SocialGraph.from_iterables(["alice"], ["alice", "carol"])
    second = tracker.run(now=datetime(2026, 6, 29, 10, tzinfo=UTC))

    assert second.completed[0].comparison.lost_followers == frozenset({"bob"})
    assert second.completed[0].comparison.not_following_back == frozenset({"carol"})


def test_if_due_skips_before_time_and_after_success(tmp_path):
    collector = FakeCollector(SocialGraph.from_iterables(["alice"], ["alice"]))
    tracker = configured_tracker(tmp_path, collector)

    early = tracker.run(if_due=True, now=datetime(2026, 6, 28, 8, tzinfo=UTC))
    due = tracker.run(if_due=True, now=datetime(2026, 6, 28, 10, tzinfo=UTC))
    duplicate = tracker.run(if_due=True, now=datetime(2026, 6, 28, 11, tzinfo=UTC))

    assert early.skipped
    assert not due.skipped
    assert duplicate.skipped
    assert collector.calls == 1
