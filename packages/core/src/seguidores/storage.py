from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from seguidores.models import Snapshot, SocialGraph

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY,
    account_name TEXT NOT NULL,
    captured_at TEXT NOT NULL,
    follower_count INTEGER NOT NULL,
    following_count INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS snapshots_account_time
    ON snapshots(account_name, captured_at DESC);

CREATE TABLE IF NOT EXISTS relationships (
    snapshot_id INTEGER NOT NULL REFERENCES snapshots(id) ON DELETE CASCADE,
    kind TEXT NOT NULL CHECK(kind IN ('follower', 'following')),
    username TEXT NOT NULL,
    PRIMARY KEY (snapshot_id, kind, username)
);
"""


class Store:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript(SCHEMA)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=30)
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def latest_snapshot(self, account_name: str) -> Snapshot | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT id, account_name, captured_at
                FROM snapshots
                WHERE account_name = ?
                ORDER BY captured_at DESC, id DESC
                LIMIT 1
                """,
                (account_name,),
            ).fetchone()
            if row is None:
                return None
            relationships = connection.execute(
                "SELECT kind, username FROM relationships WHERE snapshot_id = ?", (row[0],)
            ).fetchall()
        return Snapshot(
            id=row[0],
            account_name=row[1],
            captured_at=datetime.fromisoformat(row[2]),
            graph=SocialGraph.from_iterables(
                (username for kind, username in relationships if kind == "follower"),
                (username for kind, username in relationships if kind == "following"),
            ),
        )

    def add_snapshot(
        self, account_name: str, graph: SocialGraph, captured_at: datetime
    ) -> Snapshot:
        timestamp = _as_utc(captured_at).isoformat()
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO snapshots(account_name, captured_at, follower_count, following_count)
                VALUES (?, ?, ?, ?)
                """,
                (account_name, timestamp, len(graph.followers), len(graph.following)),
            )
            snapshot_id = int(cursor.lastrowid)
            rows = [
                *((snapshot_id, "follower", username) for username in graph.followers),
                *((snapshot_id, "following", username) for username in graph.following),
            ]
            connection.executemany(
                "INSERT INTO relationships(snapshot_id, kind, username) VALUES (?, ?, ?)", rows
            )
        return Snapshot(snapshot_id, account_name, _as_utc(captured_at), graph)

    def history(self, account_name: str, limit: int = 10) -> list[tuple[str, int, int]]:
        with self.connect() as connection:
            return connection.execute(
                """
                SELECT captured_at, follower_count, following_count
                FROM snapshots
                WHERE account_name = ?
                ORDER BY captured_at DESC, id DESC
                LIMIT ?
                """,
                (account_name, limit),
            ).fetchall()


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("La fecha debe incluir zona horaria.")
    return value.astimezone(UTC)
