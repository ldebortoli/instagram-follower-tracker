from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class SocialGraph:
    followers: frozenset[str]
    following: frozenset[str]

    @classmethod
    def from_iterables(cls, followers: object, following: object) -> SocialGraph:
        return cls(
            followers=frozenset(_normalize(followers)),
            following=frozenset(_normalize(following)),
        )


def _normalize(values: object) -> set[str]:
    if not hasattr(values, "__iter__"):
        raise TypeError("Se esperaba una colección de usuarios.")
    return {str(value).strip().lstrip("@").lower() for value in values if str(value).strip()}


@dataclass(frozen=True)
class Snapshot:
    id: int
    account_name: str
    captured_at: datetime
    graph: SocialGraph


@dataclass(frozen=True)
class Comparison:
    account_name: str
    username: str
    captured_at: datetime
    followers: frozenset[str]
    following: frozenset[str]
    not_following_back: frozenset[str]
    not_followed_back: frozenset[str]
    lost_followers: frozenset[str]
    new_followers: frozenset[str]
    unfollowed_accounts: frozenset[str]
    newly_followed_accounts: frozenset[str]
    is_baseline: bool

    @property
    def has_changes(self) -> bool:
        return bool(
            self.lost_followers
            or self.new_followers
            or self.unfollowed_accounts
            or self.newly_followed_accounts
        )


def compare_graphs(
    *,
    account_name: str,
    username: str,
    current: SocialGraph,
    previous: SocialGraph | None,
    captured_at: datetime,
) -> Comparison:
    baseline = previous is None
    previous_followers = previous.followers if previous else frozenset()
    previous_following = previous.following if previous else frozenset()
    return Comparison(
        account_name=account_name,
        username=username,
        captured_at=captured_at,
        followers=current.followers,
        following=current.following,
        not_following_back=current.following - current.followers,
        not_followed_back=current.followers - current.following,
        lost_followers=(previous_followers - current.followers) if previous else frozenset(),
        new_followers=(current.followers - previous_followers) if previous else frozenset(),
        unfollowed_accounts=(previous_following - current.following) if previous else frozenset(),
        newly_followed_accounts=(
            (current.following - previous_following) if previous else frozenset()
        ),
        is_baseline=baseline,
    )
