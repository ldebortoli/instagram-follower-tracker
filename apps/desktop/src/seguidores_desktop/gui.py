from __future__ import annotations

import ctypes
import logging
import queue
import sys
import threading
import tkinter as tk
from collections.abc import Callable
from contextlib import suppress
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any

from seguidores import __version__
from seguidores.app import RunResult, Tracker
from seguidores.collector import (
    ExportCollector,
    InstagramCollector,
    TwoFactorRequired,
)
from seguidores.config import (
    AccountConfig,
    ConfigError,
    default_config,
    load_config,
    parse_time,
    save_config,
)
from seguidores.notifier import (
    NotificationError,
    get_telegram_token,
    notify,
    send_telegram,
    set_telegram_token,
)
from seguidores.paths import AppPaths, app_paths
from seguidores.report import format_report

from seguidores_desktop import scheduler
from seguidores_desktop.launcher import scheduled_invocation
from seguidores_desktop.scheduler import SchedulerStatus

ALL_ACCOUNTS = "Todas las cuentas"


class SeguidoresApp:
    def __init__(self, root: tk.Tk, paths: AppPaths):
        self.root = root
        self.paths = paths
        self.config = load_config(paths) if paths.config.exists() else default_config()
        self.selected_account: str | None = None
        self.busy = False
        self.events: queue.Queue[tuple[str, Any, Callable, Callable | None]] = queue.Queue()

        self._configure_window()
        self._build_header()
        self._build_tabs()
        self._build_status_bar()
        self._load_config_into_form()
        self._refresh_accounts()
        self.root.after(100, self._drain_events)

    def _configure_window(self) -> None:
        self.root.title(f"Seguidores de Instagram {__version__}")
        self.root.minsize(780, 600)
        self.root.geometry("900x680")
        self.root.protocol("WM_DELETE_WINDOW", self._close)

        style = ttk.Style(self.root)
        preferred = (
            "vista" if sys.platform == "win32" else "aqua" if sys.platform == "darwin" else "clam"
        )
        if preferred in style.theme_names():
            style.theme_use(preferred)
        style.configure("Header.TLabel", font=("TkDefaultFont", 18, "bold"))
        style.configure("Subheader.TLabel", font=("TkDefaultFont", 10))
        style.configure("Status.TLabel", padding=(10, 6))
        style.configure("Treeview", rowheight=26)

    def _build_header(self) -> None:
        frame = ttk.Frame(self.root, padding=(18, 14, 18, 8))
        frame.pack(fill="x")
        ttk.Label(frame, text="Seguidores de Instagram", style="Header.TLabel").pack(anchor="w")
        ttk.Label(
            frame,
            text=(
                "Configurá las cuentas, los avisos y el chequeo diario. "
                "Las contraseñas nunca se guardan."
            ),
            style="Subheader.TLabel",
        ).pack(anchor="w", pady=(3, 0))

    def _build_tabs(self) -> None:
        self.notebook = ttk.Notebook(self.root, padding=(12, 4, 12, 8))
        self.notebook.pack(fill="both", expand=True)
        self.accounts_tab = ttk.Frame(self.notebook, padding=14)
        self.notifications_tab = ttk.Frame(self.notebook, padding=14)
        self.schedule_tab = ttk.Frame(self.notebook, padding=14)
        self.results_tab = ttk.Frame(self.notebook, padding=14)
        self.notebook.add(self.accounts_tab, text="1. Cuentas")
        self.notebook.add(self.notifications_tab, text="2. Notificaciones")
        self.notebook.add(self.schedule_tab, text="3. Automatización")
        self.notebook.add(self.results_tab, text="Resultados")
        self._build_accounts_tab()
        self._build_notifications_tab()
        self._build_schedule_tab()
        self._build_results_tab()

    def _build_accounts_tab(self) -> None:
        tab = self.accounts_tab
        tab.columnconfigure(0, weight=2)
        tab.columnconfigure(1, weight=3)
        tab.rowconfigure(1, weight=1)

        ttk.Label(
            tab,
            text="Podés registrar varias cuentas; cada una conserva su propia sesión local.",
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

        left = ttk.Frame(tab)
        left.grid(row=1, column=0, sticky="nsew", padx=(0, 12))
        left.rowconfigure(0, weight=1)
        left.columnconfigure(0, weight=1)
        self.account_tree = ttk.Treeview(
            left,
            columns=("username", "session"),
            show="headings",
            selectmode="browse",
        )
        self.account_tree.heading("username", text="Cuenta")
        self.account_tree.heading("session", text="Sesión")
        self.account_tree.column("username", minwidth=130, width=170)
        self.account_tree.column("session", minwidth=80, width=90, anchor="center")
        self.account_tree.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(left, orient="vertical", command=self.account_tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.account_tree.configure(yscrollcommand=scrollbar.set)
        self.account_tree.bind("<<TreeviewSelect>>", self._account_selected)
        ttk.Button(left, text="Nueva cuenta", command=self._new_account).grid(
            row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0)
        )

        form = ttk.LabelFrame(tab, text="Datos de la cuenta", padding=14)
        form.grid(row=1, column=1, sticky="nsew")
        form.columnconfigure(1, weight=1)
        self.account_name = tk.StringVar()
        self.instagram_username = tk.StringVar()
        self.login_username = tk.StringVar()
        self.account_enabled = tk.BooleanVar(value=True)
        self.session_status = tk.StringVar(value="Sin sesión")
        self._form_row(form, 0, "Nombre local", self.account_name)
        self._form_row(form, 1, "Usuario de Instagram (sin @)", self.instagram_username)
        self._form_row(
            form,
            2,
            "Usuario de sesión (vacío = el mismo)",
            self.login_username,
        )
        ttk.Checkbutton(form, text="Cuenta activa", variable=self.account_enabled).grid(
            row=3, column=1, sticky="w", pady=6
        )
        ttk.Label(form, text="Estado de autenticación").grid(
            row=4, column=0, sticky="w", padx=(0, 12), pady=6
        )
        ttk.Label(form, textvariable=self.session_status).grid(row=4, column=1, sticky="w", pady=6)

        buttons = ttk.Frame(form)
        buttons.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(14, 0))
        buttons.columnconfigure(0, weight=1)
        buttons.columnconfigure(1, weight=1)
        ttk.Button(buttons, text="Guardar cuenta", command=self._save_account).grid(
            row=0, column=0, sticky="ew", padx=(0, 5)
        )
        ttk.Button(buttons, text="Iniciar sesión", command=self._login_account).grid(
            row=0, column=1, sticky="ew", padx=(5, 0)
        )
        ttk.Button(
            buttons,
            text="Importar sesión del navegador",
            command=self._import_browser_session,
        ).grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        ttk.Button(
            buttons,
            text="Ingresar sessionid manualmente",
            command=self._import_session_id,
        ).grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        ttk.Button(buttons, text="Importar JSON de Instagram", command=self._import_export).grid(
            row=3, column=0, columnspan=2, sticky="ew", pady=(8, 0)
        )
        ttk.Button(buttons, text="Eliminar cuenta", command=self._remove_account).grid(
            row=4, column=0, columnspan=2, sticky="ew", pady=(8, 0)
        )

    def _form_row(
        self,
        parent: ttk.Widget,
        row: int,
        label: str,
        variable: tk.StringVar,
    ) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=6)
        entry = ttk.Entry(parent, textvariable=variable)
        entry.grid(row=row, column=1, sticky="ew", pady=6)

    def _build_notifications_tab(self) -> None:
        tab = self.notifications_tab
        tab.columnconfigure(0, weight=1)
        self.popup_enabled = tk.BooleanVar(value=True)
        self.notify_without_changes = tk.BooleanVar(value=True)
        self.telegram_enabled = tk.BooleanVar(value=False)
        self.telegram_chat_id = tk.StringVar()
        self.telegram_token = tk.StringVar()

        desktop = ttk.LabelFrame(tab, text="Escritorio", padding=14)
        desktop.grid(row=0, column=0, sticky="ew")
        ttk.Checkbutton(
            desktop,
            text="Mostrar un popup al terminar el chequeo",
            variable=self.popup_enabled,
        ).pack(anchor="w")
        ttk.Checkbutton(
            desktop,
            text="Avisar también cuando no haya cambios",
            variable=self.notify_without_changes,
        ).pack(anchor="w", pady=(8, 0))

        telegram = ttk.LabelFrame(tab, text="Telegram", padding=14)
        telegram.grid(row=1, column=0, sticky="ew", pady=(14, 0))
        telegram.columnconfigure(1, weight=1)
        ttk.Checkbutton(
            telegram,
            text="Enviar el reporte por Telegram",
            variable=self.telegram_enabled,
            command=self._toggle_telegram_fields,
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        ttk.Label(telegram, text="Chat ID o @canal").grid(row=1, column=0, sticky="w", padx=(0, 12))
        self.telegram_chat_entry = ttk.Entry(telegram, textvariable=self.telegram_chat_id)
        self.telegram_chat_entry.grid(row=1, column=1, sticky="ew")
        ttk.Label(telegram, text="Token del bot").grid(
            row=2, column=0, sticky="w", padx=(0, 12), pady=(8, 0)
        )
        self.telegram_token_entry = ttk.Entry(telegram, textvariable=self.telegram_token, show="•")
        self.telegram_token_entry.grid(row=2, column=1, sticky="ew", pady=(8, 0))
        ttk.Label(
            telegram,
            text="Dejalo vacío para conservar el token guardado en el almacén seguro.",
        ).grid(row=3, column=1, sticky="w", pady=(4, 0))
        ttk.Label(
            telegram,
            text="Con Telegram activo, los errores de ejecuciones automáticas también se avisan.",
            wraplength=620,
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(8, 0))

        buttons = ttk.Frame(tab)
        buttons.grid(row=2, column=0, sticky="ew", pady=(16, 0))
        buttons.columnconfigure(0, weight=1)
        buttons.columnconfigure(1, weight=1)
        ttk.Button(buttons, text="Guardar notificaciones", command=self._save_notifications).grid(
            row=0, column=0, sticky="ew", padx=(0, 5)
        )
        ttk.Button(buttons, text="Probar Telegram", command=self._test_telegram).grid(
            row=0, column=1, sticky="ew", padx=(5, 0)
        )

    def _build_schedule_tab(self) -> None:
        tab = self.schedule_tab
        tab.columnconfigure(0, weight=1)
        self.schedule_enabled = tk.BooleanVar(value=False)
        self.schedule_time = tk.StringVar(value="09:00")
        self.schedule_status = tk.StringVar(value="Todavía no se consultó el scheduler.")

        schedule_frame = ttk.LabelFrame(tab, text="Chequeo automático", padding=16)
        schedule_frame.grid(row=0, column=0, sticky="ew")
        schedule_frame.columnconfigure(1, weight=1)
        ttk.Checkbutton(
            schedule_frame,
            text="Ejecutar automáticamente todos los días",
            variable=self.schedule_enabled,
        ).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(schedule_frame, text="Hora local (HH:MM)").grid(
            row=1, column=0, sticky="w", padx=(0, 12), pady=(12, 0)
        )
        ttk.Entry(schedule_frame, textvariable=self.schedule_time, width=10).grid(
            row=1, column=1, sticky="w", pady=(12, 0)
        )
        ttk.Label(
            schedule_frame,
            text=(
                "Windows usa el Programador de tareas; macOS usa launchd; Linux usa systemd "
                "o cron. Si la computadora estaba apagada, se ejecuta al volver a estar disponible."
            ),
            wraplength=700,
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(12, 0))
        ttk.Label(schedule_frame, textvariable=self.schedule_status, wraplength=700).grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(12, 0)
        )

        buttons = ttk.Frame(tab)
        buttons.grid(row=1, column=0, sticky="ew", pady=(16, 0))
        buttons.columnconfigure(0, weight=1)
        buttons.columnconfigure(1, weight=1)
        ttk.Button(buttons, text="Aplicar automatización", command=self._apply_schedule).grid(
            row=0, column=0, sticky="ew", padx=(0, 5)
        )
        ttk.Button(buttons, text="Actualizar estado", command=self._query_schedule).grid(
            row=0, column=1, sticky="ew", padx=(5, 0)
        )

        manual = ttk.LabelFrame(tab, text="Chequeo manual", padding=16)
        manual.grid(row=2, column=0, sticky="ew", pady=(18, 0))
        manual.columnconfigure(0, weight=1)
        self.run_account = tk.StringVar(value=ALL_ACCOUNTS)
        self.bypass_cooldown = tk.BooleanVar(value=False)
        self.run_account_combo = ttk.Combobox(
            manual, textvariable=self.run_account, state="readonly"
        )
        self.run_account_combo.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        ttk.Button(manual, text="Comprobar ahora", command=self._run_check).grid(
            row=0, column=1, sticky="e"
        )
        ttk.Checkbutton(
            manual,
            text="Omitir el cooldown sólo en este chequeo manual",
            variable=self.bypass_cooldown,
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(10, 0))

    def _build_results_tab(self) -> None:
        self.results_text = tk.Text(
            self.results_tab,
            wrap="word",
            state="disabled",
            padx=12,
            pady=12,
            borderwidth=1,
            relief="solid",
        )
        self.results_text.pack(fill="both", expand=True)

    def _build_status_bar(self) -> None:
        self.status = tk.StringVar(value=f"Datos locales: {self.paths.root}")
        ttk.Separator(self.root).pack(fill="x")
        ttk.Label(self.root, textvariable=self.status, style="Status.TLabel").pack(fill="x")

    def _load_config_into_form(self) -> None:
        notifications = self.config.notifications
        self.popup_enabled.set(notifications.popup)
        self.notify_without_changes.set(notifications.notify_without_changes)
        self.telegram_enabled.set(notifications.telegram.enabled)
        self.telegram_chat_id.set(notifications.telegram.chat_id)
        self.schedule_enabled.set(self.config.schedule.enabled)
        self.schedule_time.set(self.config.schedule.time)
        if self.config.schedule.backend:
            self.schedule_status.set(
                f"Configurado con {self.config.schedule.backend} a las {self.config.schedule.time}."
            )
        self._toggle_telegram_fields()

    def _refresh_accounts(self, select: str | None = None) -> None:
        current = select or self.selected_account
        for item in self.account_tree.get_children():
            self.account_tree.delete(item)
        collector = InstagramCollector(self.paths)
        for account in self.config.accounts:
            session_state = collector.session_state(account)
            session = {
                "saved": "Lista",
                "invalid": "Inválida",
                "missing": "Pendiente",
                "cooldown": "Cooldown",
            }[session_state.code]
            state = "" if account.enabled else " (inactiva)"
            self.account_tree.insert(
                "", "end", iid=account.name, values=(f"@{account.username}{state}", session)
            )
        values = [
            ALL_ACCOUNTS,
            *(account.name for account in self.config.accounts if account.enabled),
        ]
        self.run_account_combo.configure(values=values)
        if self.run_account.get() not in values:
            self.run_account.set(ALL_ACCOUNTS)
        if current and self.account_tree.exists(current):
            self.account_tree.selection_set(current)
            self.account_tree.focus(current)
            self._show_account(self.config.account(current))
        elif self.config.accounts:
            first = self.config.accounts[0].name
            self.account_tree.selection_set(first)
            self._show_account(self.config.accounts[0])
        else:
            self._new_account()

    def _account_selected(self, _event: object = None) -> None:
        selection = self.account_tree.selection()
        if selection:
            self._show_account(self.config.account(selection[0]))

    def _show_account(self, account: AccountConfig) -> None:
        self.selected_account = account.name
        self.account_name.set(account.name)
        self.instagram_username.set(account.username)
        self.login_username.set(account.login_username)
        self.account_enabled.set(account.enabled)
        state = InstagramCollector(self.paths).session_state(account)
        self.session_status.set(state.label)

    def _new_account(self) -> None:
        self.selected_account = None
        self.account_tree.selection_remove(*self.account_tree.selection())
        self.account_name.set("")
        self.instagram_username.set("")
        self.login_username.set("")
        self.account_enabled.set(True)
        self.session_status.set("Sin sesión")

    def _account_from_form(self) -> AccountConfig:
        username = self.instagram_username.get().strip().lstrip("@")
        login_username = self.login_username.get().strip().lstrip("@") or username
        account = AccountConfig(
            name=self.account_name.get().strip(),
            username=username,
            login_username=login_username,
            enabled=self.account_enabled.get(),
        )
        account.validate()
        return account

    def _save_account(self) -> AccountConfig | None:
        try:
            candidate = self._account_from_form()
            if self.selected_account and candidate.name.lower() != self.selected_account.lower():
                raise ConfigError(
                    "El nombre local identifica el historial y no se puede renombrar. "
                    "Creá una cuenta nueva para usar otro nombre."
                )
            for account in self.config.accounts:
                if account.name.lower() == candidate.name.lower() and (
                    not self.selected_account
                    or account.name.lower() != self.selected_account.lower()
                ):
                    raise ConfigError(f"Ya existe la cuenta local {candidate.name!r}.")
            updated = [
                account
                for account in self.config.accounts
                if account.name.lower() != candidate.name.lower()
            ]
            updated.append(candidate)
            self.config.accounts = updated
            save_config(self.paths, self.config)
        except (ConfigError, OSError) as exc:
            messagebox.showerror("No se pudo guardar", str(exc), parent=self.root)
            return None
        self.selected_account = candidate.name
        self._refresh_accounts(candidate.name)
        self._set_status(f"Cuenta {candidate.name} guardada.")
        return candidate

    def _remove_account(self) -> None:
        if not self.selected_account:
            messagebox.showinfo("Cuentas", "Seleccioná una cuenta para eliminar.", parent=self.root)
            return
        account = self.config.account(self.selected_account)
        if not messagebox.askyesno(
            "Eliminar cuenta",
            (
                f"¿Eliminar {account.name} y su cookie de sesión local?\n\n"
                "El historial SQLite se conservará."
            ),
            parent=self.root,
        ):
            return
        self.config.accounts.remove(account)
        InstagramCollector(self.paths).session_file(account).unlink(missing_ok=True)
        save_config(self.paths, self.config)
        self.selected_account = None
        self._refresh_accounts()
        self._set_status(f"Cuenta {account.name} eliminada.")

    def _login_account(self) -> None:
        account = self._save_account()
        if account:
            LoginDialog(self, account)

    def _import_browser_session(self) -> None:
        account = self._save_account()
        if account:
            BrowserSessionDialog(self, account)

    def _import_session_id(self) -> None:
        account = self._save_account()
        if account:
            SessionIdDialog(self, account)

    def _import_export(self) -> None:
        account = self._save_account()
        if not account:
            return
        directory = filedialog.askdirectory(
            title="Elegir la exportación JSON de Instagram", parent=self.root
        )
        if not directory:
            return

        def work() -> str:
            graph = ExportCollector().collect_directory(Path(directory))
            comparison = Tracker(self.paths, self.config).record_graph(
                account, graph, datetime.now().astimezone()
            )
            failures = notify(comparison, self.config.notifications)
            report = format_report(comparison)
            if failures:
                report += "\n\nAvisos:\n" + "\n".join(
                    f"- {failure.channel}: {failure.error}" for failure in failures
                )
            return report

        self.run_async("Importando la exportación…", work, self._show_report)

    def _save_notifications(self) -> None:
        try:
            enabled = self.telegram_enabled.get()
            chat_id = self.telegram_chat_id.get().strip()
            token = self.telegram_token.get().strip()
            if enabled and not chat_id:
                raise NotificationError("Ingresá el chat ID o @alias del canal.")
            if enabled and not token and not get_telegram_token():
                raise NotificationError("Ingresá el token del bot de Telegram.")
            if token:
                set_telegram_token(token)
            self.config.notifications.popup = self.popup_enabled.get()
            self.config.notifications.notify_without_changes = self.notify_without_changes.get()
            self.config.notifications.telegram.enabled = enabled
            self.config.notifications.telegram.chat_id = chat_id
            save_config(self.paths, self.config)
        except (NotificationError, ConfigError, OSError) as exc:
            messagebox.showerror("Notificaciones", str(exc), parent=self.root)
            return
        self.telegram_token.set("")
        self._set_status("Configuración de notificaciones guardada.")

    def _toggle_telegram_fields(self) -> None:
        state = "normal" if self.telegram_enabled.get() else "disabled"
        self.telegram_chat_entry.configure(state=state)
        self.telegram_token_entry.configure(state=state)

    def _test_telegram(self) -> None:
        chat_id = self.telegram_chat_id.get().strip()
        entered_token = self.telegram_token.get().strip()

        def work() -> None:
            token = entered_token or get_telegram_token()
            if not token:
                raise NotificationError("Ingresá el token del bot.")
            send_telegram(token, chat_id, "Seguidores: prueba correcta ✅")

        self.run_async(
            "Enviando mensaje de prueba…",
            work,
            lambda _result: self._set_status("Mensaje de prueba enviado por Telegram."),
        )

    def _apply_schedule(self) -> None:
        enabled = self.schedule_enabled.get()
        time = self.schedule_time.get().strip()
        try:
            parse_time(time)
            if enabled and not any(account.enabled for account in self.config.accounts):
                raise ConfigError("Agregá al menos una cuenta activa antes de automatizar.")
        except ConfigError as exc:
            messagebox.showerror("Automatización", str(exc), parent=self.root)
            return
        previous_backend = self.config.schedule.backend

        def work() -> str:
            if enabled:
                return scheduler.install(
                    self.paths,
                    time,
                    invocation=scheduled_invocation(graphical=True),
                )
            if previous_backend:
                scheduler.uninstall(previous_backend)
            return ""

        def success(backend: str) -> None:
            self.config.schedule.enabled = enabled
            self.config.schedule.time = time
            self.config.schedule.backend = backend
            save_config(self.paths, self.config)
            if enabled:
                self.schedule_status.set(f"Instalado con {backend} a las {time}.")
                self._set_status("Chequeo automático instalado.")
            else:
                self.schedule_status.set("Chequeo automático desactivado.")
                self._set_status("Chequeo automático eliminado.")

        self.run_async("Aplicando la automatización…", work, success)

    def _query_schedule(self) -> None:
        backend = self.config.schedule.backend or None

        def success(current: SchedulerStatus) -> None:
            state = "instalada" if current.installed else "no instalada"
            self.schedule_status.set(f"{current.backend}: {state}. {current.detail}".strip())
            self._set_status("Estado del scheduler actualizado.")

        self.run_async("Consultando el scheduler…", lambda: scheduler.status(backend), success)

    def _run_check(self) -> None:
        if not any(account.enabled for account in self.config.accounts):
            messagebox.showerror("Chequeo", "Agregá al menos una cuenta activa.", parent=self.root)
            return
        selected = self.run_account.get()
        account_name = None if selected == ALL_ACCOUNTS else selected
        bypass_cooldown = self.bypass_cooldown.get()
        if bypass_cooldown:
            confirmed = messagebox.askyesno(
                "Omitir cooldown",
                (
                    "Esta protección existe porque Instagram rechazó requests recientes. "
                    "Intentarlo antes de tiempo puede prolongar el bloqueo de la cuenta.\n\n"
                    "¿Querés omitir el cooldown una sola vez para este chequeo manual?"
                ),
                icon="warning",
                parent=self.root,
            )
            if not confirmed:
                return
            self.bypass_cooldown.set(False)
            logging.getLogger("seguidores").warning(
                "El usuario omitió el cooldown para un chequeo manual de %s.",
                account_name or "todas las cuentas",
            )

        def success(result: RunResult) -> None:
            parts = [format_report(item.comparison) for item in result.completed]
            for item in result.completed:
                parts.extend(
                    f"Aviso: falló {failure.channel}: {failure.error}"
                    for failure in item.notification_failures
                )
            parts.extend(f"Error en {item.account_name}: {item.error}" for item in result.failed)
            if result.skipped:
                parts.append("No había chequeos pendientes.")
            self._show_report("\n\n".join(parts) or "El chequeo no produjo resultados.")
            self._set_status("Chequeo terminado.")

        self.run_async(
            "Consultando Instagram…",
            lambda: Tracker(
                self.paths,
                self.config,
                collector=InstagramCollector(
                    self.paths,
                    bypass_cooldown=bypass_cooldown,
                ),
            ).run(account_name=account_name),
            success,
        )

    def _show_report(self, report: str) -> None:
        self.results_text.configure(state="normal")
        self.results_text.delete("1.0", "end")
        self.results_text.insert("1.0", report)
        self.results_text.configure(state="disabled")
        self.notebook.select(self.results_tab)

    def run_async(
        self,
        label: str,
        work: Callable[[], Any],
        success: Callable[[Any], None],
        error: Callable[[Exception], None] | None = None,
    ) -> bool:
        if self.busy:
            messagebox.showinfo(
                "Operación en curso",
                "Esperá a que termine la operación actual.",
                parent=self.root,
            )
            return False
        self.busy = True
        self.root.configure(cursor="watch")
        self._set_status(label)

        def worker() -> None:
            try:
                result = work()
            except Exception as exc:
                self.events.put(("error", exc, success, error))
            else:
                self.events.put(("success", result, success, error))

        threading.Thread(target=worker, daemon=True).start()
        return True

    def _drain_events(self) -> None:
        try:
            while True:
                kind, value, success, error = self.events.get_nowait()
                self.busy = False
                self.root.configure(cursor="")
                if kind == "success":
                    try:
                        success(value)
                    except Exception as exc:
                        messagebox.showerror("Error", str(exc), parent=self.root)
                elif error:
                    error(value)
                else:
                    self._show_failure("Error", value)
                    self._set_status("La operación falló.")
        except queue.Empty:
            pass
        if self.root.winfo_exists():
            self.root.after(100, self._drain_events)

    def _set_status(self, message: str) -> None:
        self.status.set(message)

    def _show_failure(self, title: str, exception: Exception) -> None:
        detail = str(exception)
        self._show_report(detail)
        summary = detail.splitlines()[0] if detail else type(exception).__name__
        messagebox.showerror(
            title,
            f"{summary}\n\nLa request y la response sanitizadas están en Resultados.",
            parent=self.root,
        )

    def _close(self) -> None:
        if self.busy and not messagebox.askyesno(
            "Salir", "Hay una operación en curso. ¿Cerrar igualmente?", parent=self.root
        ):
            return
        self.root.destroy()


class LoginDialog:
    def __init__(self, app: SeguidoresApp, account: AccountConfig):
        self.app = app
        self.account = account
        self.window = tk.Toplevel(app.root)
        self.window.title(f"Iniciar sesión · @{account.login_username}")
        self.window.resizable(False, False)
        self.window.transient(app.root)
        self.window.grab_set()
        self.password = tk.StringVar()
        self.code = tk.StringVar()
        self.status = tk.StringVar(value="La contraseña se usa sólo para crear la sesión local.")

        frame = ttk.Frame(self.window, padding=18)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(1, weight=1)
        ttk.Label(frame, text=f"Cuenta: @{account.login_username}").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 12)
        )
        ttk.Label(frame, text="Contraseña").grid(row=1, column=0, sticky="w", padx=(0, 12))
        password_entry = ttk.Entry(frame, textvariable=self.password, show="•", width=32)
        password_entry.grid(row=1, column=1, sticky="ew")
        self.code_label = ttk.Label(frame, text="Código 2FA")
        self.code_entry = ttk.Entry(frame, textvariable=self.code, width=12)
        ttk.Label(frame, textvariable=self.status, wraplength=360).grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(12, 0)
        )
        buttons = ttk.Frame(frame)
        buttons.grid(row=4, column=0, columnspan=2, sticky="e", pady=(16, 0))
        ttk.Button(buttons, text="Cancelar", command=self.window.destroy).pack(
            side="left", padx=(0, 8)
        )
        ttk.Button(buttons, text="Iniciar sesión", command=self._submit).pack(side="left")
        self.window.bind("<Return>", lambda _event: self._submit())
        password_entry.focus_set()

    def _submit(self) -> None:
        password = self.password.get()
        code = self.code.get().strip() or None

        def work() -> Path:
            return InstagramCollector(self.app.paths).login_with_credentials(
                self.account, password, code
            )

        def success(_path: Path) -> None:
            self.password.set("")
            self.code.set("")
            self.app._refresh_accounts(self.account.name)
            self.app._set_status(f"Sesión de {self.account.name} guardada.")
            messagebox.showinfo(
                "Instagram",
                "La sesión quedó guardada. La contraseña no se almacenó.",
                parent=self.window,
            )
            self.window.destroy()

        def error(exc: Exception) -> None:
            if isinstance(exc, TwoFactorRequired):
                self.code_label.grid(row=2, column=0, sticky="w", padx=(0, 12), pady=(10, 0))
                self.code_entry.grid(row=2, column=1, sticky="w", pady=(10, 0))
                self.status.set("Instagram solicitó autenticación de dos factores.")
                self.code_entry.focus_set()
            else:
                self.status.set(str(exc))
                self.app._show_failure("Instagram", exc)

        self.app.run_async("Iniciando sesión en Instagram…", work, success, error)


class BrowserSessionDialog:
    BROWSERS = {
        "Brave": "brave",
        "Chrome": "chrome",
        "Chromium": "chromium",
        "Edge": "edge",
        "Firefox": "firefox",
        "LibreWolf": "librewolf",
        "Opera": "opera",
        "Opera GX": "opera_gx",
        "Safari": "safari",
        "Vivaldi": "vivaldi",
    }

    def __init__(self, app: SeguidoresApp, account: AccountConfig):
        self.app = app
        self.account = account
        self.window = tk.Toplevel(app.root)
        self.window.title("Importar sesión del navegador")
        self.window.resizable(False, False)
        self.window.transient(app.root)
        self.window.grab_set()
        defaults = {
            "win32": ["Edge", "Chrome", "Firefox", "Brave"],
            "darwin": ["Safari", "Chrome", "Firefox", "Brave"],
        }
        choices = defaults.get(sys.platform, ["Chrome", "Chromium", "Firefox", "Brave"])
        self.browser = tk.StringVar(value=choices[0])

        frame = ttk.Frame(self.window, padding=18)
        frame.pack(fill="both", expand=True)
        ttk.Label(
            frame,
            text=(
                f"Iniciá sesión como @{account.login_username} en instagram.com y elegí "
                "ese navegador. Sólo se copiarán las cookies de Instagram."
            ),
            wraplength=430,
        ).pack(anchor="w")
        combo = ttk.Combobox(
            frame,
            textvariable=self.browser,
            values=choices,
            state="readonly",
            width=24,
        )
        combo.pack(fill="x", pady=(14, 0))
        ttk.Label(
            frame,
            text="Si el navegador bloquea su base de cookies, cerralo y volvé a intentar.",
            wraplength=430,
        ).pack(anchor="w", pady=(8, 0))
        buttons = ttk.Frame(frame)
        buttons.pack(anchor="e", pady=(16, 0))
        ttk.Button(buttons, text="Cancelar", command=self.window.destroy).pack(
            side="left", padx=(0, 8)
        )
        ttk.Button(buttons, text="Importar", command=self._submit).pack(side="left")

    def _submit(self) -> None:
        browser = self.BROWSERS[self.browser.get()]

        def work() -> Path:
            return InstagramCollector(self.app.paths).import_browser_session(self.account, browser)

        def success(_path: Path) -> None:
            self.app._refresh_accounts(self.account.name)
            self.app._set_status(f"Sesión de {self.account.name} importada desde {browser}.")
            messagebox.showinfo(
                "Instagram",
                "La sesión del navegador fue validada y guardada.",
                parent=self.window,
            )
            self.window.destroy()

        def error(exc: Exception) -> None:
            self.app._show_failure("Importar sesión", exc)

        self.app.run_async("Importando y validando la sesión…", work, success, error)


class SessionIdDialog:
    def __init__(self, app: SeguidoresApp, account: AccountConfig):
        self.app = app
        self.account = account
        self.window = tk.Toplevel(app.root)
        self.window.title("Ingresar sessionid")
        self.window.resizable(False, False)
        self.window.transient(app.root)
        self.window.grab_set()
        self.session_id = tk.StringVar()

        frame = ttk.Frame(self.window, padding=18)
        frame.pack(fill="both", expand=True)
        ttk.Label(
            frame,
            text=(
                f"Pegá el valor de la cookie sessionid correspondiente a "
                f"@{account.login_username}. Se validará antes de guardarlo."
            ),
            wraplength=440,
        ).pack(anchor="w")
        entry = ttk.Entry(frame, textvariable=self.session_id, show="•", width=58)
        entry.pack(fill="x", pady=(14, 0))
        ttk.Label(
            frame,
            text=(
                "Este valor permite acceder a tu cuenta: tratalo como una contraseña. "
                "No se mostrará en logs ni diagnósticos."
            ),
            wraplength=440,
        ).pack(anchor="w", pady=(8, 0))
        buttons = ttk.Frame(frame)
        buttons.pack(anchor="e", pady=(16, 0))
        ttk.Button(buttons, text="Cancelar", command=self.window.destroy).pack(
            side="left", padx=(0, 8)
        )
        ttk.Button(buttons, text="Validar y guardar", command=self._submit).pack(side="left")
        self.window.bind("<Return>", lambda _event: self._submit())
        entry.focus_set()

    def _submit(self) -> None:
        session_id = self.session_id.get()
        self.session_id.set("")

        def work() -> Path:
            return InstagramCollector(self.app.paths).import_session_id(self.account, session_id)

        def success(_path: Path) -> None:
            self.app._refresh_accounts(self.account.name)
            self.app._set_status(f"sessionid de {self.account.name} validado y guardado.")
            messagebox.showinfo(
                "Instagram",
                "El sessionid fue validado y la sesión quedó guardada.",
                parent=self.window,
            )
            self.window.destroy()

        def error(exc: Exception) -> None:
            self.app._show_failure("Validar sessionid", exc)

        self.app.run_async("Validando sessionid…", work, success, error)


def main(paths: AppPaths | None = None) -> int:
    if sys.argv[1:] == ["--version"]:
        print(f"seguidores-gui {__version__}")
        return 0
    if sys.argv[1:] == ["--scheduled-run"]:
        from seguidores_desktop.cli import main as cli_main

        return cli_main(["run", "--if-due"])
    paths = paths or app_paths()
    paths.ensure()
    _configure_logging(paths)
    if sys.platform == "win32":
        with suppress(AttributeError, OSError):
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        print(f"No se pudo abrir la interfaz gráfica: {exc}", file=sys.stderr)
        return 2
    SeguidoresApp(root, paths)
    root.mainloop()
    return 0


def _configure_logging(paths: AppPaths) -> None:
    logger = logging.getLogger("seguidores")
    logger.setLevel(logging.INFO)
    if logger.handlers:
        return
    handler = RotatingFileHandler(
        paths.logs / "seguidores.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)


if __name__ == "__main__":
    raise SystemExit(main())
