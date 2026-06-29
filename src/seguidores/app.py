from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from seguidores.collector import Collector, InstagramCollector
from seguidores.config import AccountConfig, Config, parse_time
from seguidores.locking import RunLock
from seguidores.models import Comparison, SocialGraph, compare_graphs
from seguidores.notifier import NotificationFailure, notify, notify_automatic_failure
from seguidores.paths import AppPaths
from seguidores.storage import Store


@dataclass(frozen=True)
class AccountResult:
    comparison: Comparison
    notification_failures: tuple[NotificationFailure, ...]


@dataclass(frozen=True)
class AccountFailure:
    account_name: str
    error: str


@dataclass(frozen=True)
class RunResult:
    completed: tuple[AccountResult, ...]
    failed: tuple[AccountFailure, ...]
    skipped: bool = False
    automatic_notification_failure: NotificationFailure | None = None


class Tracker:
    def __init__(self, paths: AppPaths, config: Config, collector: Collector | None = None):
        self.paths = paths
        self.config = config
        self.collector = collector or InstagramCollector(paths)
        self.store = Store(paths.database)
        self.log = logging.getLogger("seguidores")

    def run(
        self,
        *,
        account_name: str | None = None,
        if_due: bool = False,
        now: datetime | None = None,
    ) -> RunResult:
        now = now or datetime.now().astimezone()
        accounts = self._selected_accounts(account_name)
        if if_due:
            accounts = [account for account in accounts if self._account_due(account, now)]
            if not accounts:
                self.log.info("No hay cuentas pendientes para hoy.")
                return RunResult((), (), skipped=True)

        completed: list[AccountResult] = []
        failed: list[AccountFailure] = []
        with RunLock(self.paths.lock):
            for account in accounts:
                run_id = self.store.start_run(account.name, now)
                try:
                    graph = self.collector.collect(account)
                    comparison = self.record_graph(account, graph, now)
                    failures = tuple(notify(comparison, self.config.notifications))
                    self.store.finish_run(
                        run_id,
                        succeeded=True,
                        finished_at=datetime.now().astimezone(),
                    )
                    completed.append(AccountResult(comparison, failures))
                    for failure in failures:
                        self.log.error(
                            "Falló notificación %s para %s: %s",
                            failure.channel,
                            account.name,
                            failure.error,
                        )
                except Exception as exc:
                    message = str(exc)
                    self.store.finish_run(
                        run_id,
                        succeeded=False,
                        finished_at=datetime.now().astimezone(),
                        error=message,
                    )
                    self.log.exception("Falló el chequeo de %s", account.name)
                    failed.append(AccountFailure(account.name, message))
        automatic_notification_failure = None
        if if_due and failed:
            automatic_notification_failure = notify_automatic_failure(
                [(failure.account_name, failure.error) for failure in failed],
                self.config.notifications,
                now,
            )
            if automatic_notification_failure:
                self.log.error(
                    "No se pudo avisar por Telegram el fallo automático: %s",
                    automatic_notification_failure.error,
                )
            elif self.config.notifications.telegram.enabled:
                self.log.info("Se avisó por Telegram el fallo de la ejecución automática.")
        return RunResult(
            tuple(completed),
            tuple(failed),
            automatic_notification_failure=automatic_notification_failure,
        )

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

    def _selected_accounts(self, account_name: str | None) -> list[AccountConfig]:
        if account_name:
            account = self.config.account(account_name)
            return [account] if account.enabled else []
        return [account for account in self.config.accounts if account.enabled]

    def _account_due(self, account: AccountConfig, now: datetime) -> bool:
        hour, minute = parse_time(self.config.schedule.time)
        if (now.hour, now.minute) < (hour, minute):
            return False
        return not self.store.succeeded_on_local_date(
            account.name, now.date().isoformat(), now.tzinfo
        )
