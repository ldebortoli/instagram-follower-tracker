from datetime import UTC, datetime

from seguidores.app import Tracker
from seguidores.config import AccountConfig
from seguidores.models import SocialGraph
from seguidores.paths import AppPaths


def test_tracker_records_baseline_and_changes(tmp_path):
    tracker = Tracker(AppPaths(tmp_path))
    account = AccountConfig("personal", "owner")

    first = tracker.record_graph(
        account,
        SocialGraph.from_iterables(["alice", "bob"], ["alice"]),
        datetime(2026, 6, 28, 10, tzinfo=UTC),
    )
    second = tracker.record_graph(
        account,
        SocialGraph.from_iterables(["alice"], ["alice", "carol"]),
        datetime(2026, 6, 29, 10, tzinfo=UTC),
    )

    assert first.is_baseline
    assert second.lost_followers == frozenset({"bob"})
    assert second.not_following_back == frozenset({"carol"})
