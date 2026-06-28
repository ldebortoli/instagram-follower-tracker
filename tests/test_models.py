from datetime import UTC, datetime

from seguidores.models import SocialGraph, compare_graphs


def test_social_graph_normalizes_usernames():
    graph = SocialGraph.from_iterables(["@Alice", "BOB", "alice"], [" Bob ", "Carol"])

    assert graph.followers == frozenset({"alice", "bob"})
    assert graph.following == frozenset({"bob", "carol"})


def test_comparison_calculates_relationships_and_changes():
    previous = SocialGraph.from_iterables(
        followers=["alice", "bob", "lost"],
        following=["alice", "carol", "removed"],
    )
    current = SocialGraph.from_iterables(
        followers=["alice", "bob", "new"],
        following=["alice", "carol", "added"],
    )

    result = compare_graphs(
        account_name="personal",
        username="owner",
        current=current,
        previous=previous,
        captured_at=datetime(2026, 6, 28, tzinfo=UTC),
    )

    assert result.not_following_back == frozenset({"carol", "added"})
    assert result.not_followed_back == frozenset({"bob", "new"})
    assert result.lost_followers == frozenset({"lost"})
    assert result.new_followers == frozenset({"new"})
    assert result.unfollowed_accounts == frozenset({"removed"})
    assert result.newly_followed_accounts == frozenset({"added"})
    assert result.has_changes
    assert not result.is_baseline


def test_first_comparison_is_baseline_without_false_changes():
    current = SocialGraph.from_iterables(["alice"], ["bob"])

    result = compare_graphs(
        account_name="personal",
        username="owner",
        current=current,
        previous=None,
        captured_at=datetime.now(UTC),
    )

    assert result.is_baseline
    assert not result.has_changes
    assert not result.lost_followers
    assert not result.new_followers
