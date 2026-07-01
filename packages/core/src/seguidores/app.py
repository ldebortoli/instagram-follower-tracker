from __future__ import annotations

from datetime import datetime

from seguidores.config import AccountConfig
from seguidores.models import Comparison, SocialGraph, compare_graphs
from seguidores.paths import AppPaths
from seguidores.storage import Store


class Tracker:
    """Compara y persiste capturas importadas manualmente."""

    def __init__(self, paths: AppPaths):
        self.store = Store(paths.database)

    def record_graph(
        self, account: AccountConfig, graph: SocialGraph, captured_at: datetime
    ) -> Comparison:
        previous = self.store.latest_snapshot(account.name)
        comparison = compare_graphs(
            account_name=account.name,
            username=account.username,
            current=graph,
            previous=previous.graph if previous else None,
            captured_at=captured_at,
        )
        self.store.add_snapshot(account.name, graph, captured_at)
        return comparison
