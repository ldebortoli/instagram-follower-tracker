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
from seguidores.app import Tracker
from seguidores.collector import CollectionError, ExportCollector
from seguidores.config import AccountConfig, ConfigError, default_config, load_config, save_config
from seguidores.notifier import (
    NotificationError,
    get_telegram_token,
    notify,
    send_telegram,
    set_telegram_token,
)
from seguidores.paths import AppPaths, app_paths
from seguidores.report import format_report

from seguidores_desktop.legacy_cleanup import LegacyCleanupError, cleanup_legacy_state

NEW_PROFILE = "<Nuevo perfil>"


class SeguidoresApp:
    def __init__(self, root: tk.Tk, paths: AppPaths):
        self.root = root
        self.paths = paths
        self.config = load_config(paths) if paths.config.exists() else default_config()
        self.busy = False
        self.events: queue.Queue[tuple[str, Any, Callable, Callable | None]] = queue.Queue()
        self.follower_paths: tuple[Path, ...] = ()
        self.following_paths: tuple[Path, ...] = ()

        self._configure_window()
        self._build_header()
        self._build_tabs()
        self._build_status_bar()
        self._load_config_into_form()
        self._refresh_profiles()
        self.root.after(100, self._drain_events)
        self.root.after(150, self._cleanup_legacy_installation)

    def _configure_window(self) -> None:
        self.root.title(f"Seguidores de Instagram {__version__}")
        self.root.minsize(760, 560)
        self.root.geometry("900x660")
        self.root.protocol("WM_DELETE_WINDOW", self._close)
        style = ttk.Style(self.root)
        preferred = (
            "vista" if sys.platform == "win32" else "aqua" if sys.platform == "darwin" else "clam"
        )
        if preferred in style.theme_names():
            style.theme_use(preferred)
        style.configure("Header.TLabel", font=("TkDefaultFont", 18, "bold"))
        style.configure("Status.TLabel", padding=(10, 6))

    def _build_header(self) -> None:
        frame = ttk.Frame(self.root, padding=(18, 14, 18, 8))
        frame.pack(fill="x")
        ttk.Label(frame, text="Seguidores de Instagram", style="Header.TLabel").pack(anchor="w")
        ttk.Label(
            frame,
            text=(
                "Compará los archivos JSON oficiales de seguidores y seguidos, "
                "sin iniciar sesión."
            ),
        ).pack(anchor="w", pady=(3, 0))

    def _build_tabs(self) -> None:
        self.notebook = ttk.Notebook(self.root, padding=(12, 4, 12, 8))
        self.notebook.pack(fill="both", expand=True)
        self.import_tab = ttk.Frame(self.notebook, padding=16)
        self.notifications_tab = ttk.Frame(self.notebook, padding=16)
        self.results_tab = ttk.Frame(self.notebook, padding=14)
        self.notebook.add(self.import_tab, text="1. Importar JSON")
        self.notebook.add(self.notifications_tab, text="2. Notificaciones")
        self.notebook.add(self.results_tab, text="Resultados")
        self._build_import_tab()
        self._build_notifications_tab()
        self._build_results_tab()

    def _build_import_tab(self) -> None:
        tab = self.import_tab
        tab.columnconfigure(0, weight=1)
        profile = ttk.LabelFrame(tab, text="Perfil", padding=14)
        profile.grid(row=0, column=0, sticky="ew")
        profile.columnconfigure(1, weight=1)

        self.profile_choice = tk.StringVar(value=NEW_PROFILE)
        self.account_name = tk.StringVar()
        self.instagram_username = tk.StringVar()
        ttk.Label(profile, text="Perfil guardado").grid(
            row=0, column=0, sticky="w", padx=(0, 12), pady=5
        )
        self.profile_combo = ttk.Combobox(
            profile, textvariable=self.profile_choice, state="readonly"
        )
        self.profile_combo.grid(row=0, column=1, sticky="ew", pady=5)
        self.profile_combo.bind("<<ComboboxSelected>>", self._profile_selected)
        self._form_row(profile, 1, "Nombre local", self.account_name)
        self._form_row(profile, 2, "Usuario de Instagram (sin @)", self.instagram_username)
        ttk.Label(
            profile,
            text=(
                "El nombre local identifica el historial. "
                "Los JSON no incluyen el dueño de la cuenta."
            ),
            wraplength=680,
        ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(6, 0))

        files = ttk.LabelFrame(tab, text="Archivos exportados", padding=14)
        files.grid(row=1, column=0, sticky="ew", pady=(14, 0))
        files.columnconfigure(0, weight=1)
        self.followers_label = tk.StringVar(value="Ningún archivo seleccionado")
        self.following_label = tk.StringVar(value="Ningún archivo seleccionado")
        ttk.Label(files, text="Seguidores (followers_1.json)").grid(row=0, column=0, sticky="w")
        ttk.Button(files, text="Elegir archivo(s)…", command=self._choose_followers).grid(
            row=0, column=1, sticky="e", padx=(12, 0)
        )
        ttk.Label(files, textvariable=self.followers_label, wraplength=650).grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(3, 12)
        )
        ttk.Label(files, text="Seguidos (following.json)").grid(row=2, column=0, sticky="w")
        ttk.Button(files, text="Elegir archivo(s)…", command=self._choose_following).grid(
            row=2, column=1, sticky="e", padx=(12, 0)
        )
        ttk.Label(files, textvariable=self.following_label, wraplength=650).grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(3, 0)
        )
        ttk.Label(
            files,
            text=(
                "Podés elegir varios followers_*.json si Instagram dividió la lista. "
                "La aplicación rechaza reportes de Threads para evitar resultados incorrectos."
            ),
            wraplength=700,
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(12, 0))

        ttk.Button(tab, text="Comparar y guardar captura", command=self._import_files).grid(
            row=2, column=0, sticky="ew", pady=(16, 0), ipady=5
        )

    def _form_row(self, parent: ttk.Widget, row: int, label: str, variable: tk.StringVar) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=5)
        ttk.Entry(parent, textvariable=variable).grid(row=row, column=1, sticky="ew", pady=5)

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
            desktop, text="Mostrar un popup al terminar la importación", variable=self.popup_enabled
        ).pack(anchor="w")
        ttk.Checkbutton(
            desktop,
            text="Avisar también cuando no haya cambios respecto de la captura anterior",
            variable=self.notify_without_changes,
        ).pack(anchor="w", pady=(8, 0))

        telegram = ttk.LabelFrame(tab, text="Telegram", padding=14)
        telegram.grid(row=1, column=0, sticky="ew", pady=(14, 0))
        telegram.columnconfigure(1, weight=1)
        ttk.Checkbutton(
            telegram,
            text="Enviar el reporte al importar",
            variable=self.telegram_enabled,
            command=self._toggle_telegram_fields,
        ).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(telegram, text="Chat ID o @canal").grid(
            row=1, column=0, sticky="w", padx=(0, 12), pady=(12, 5)
        )
        self.telegram_chat_entry = ttk.Entry(telegram, textvariable=self.telegram_chat_id)
        self.telegram_chat_entry.grid(row=1, column=1, sticky="ew", pady=(12, 5))
        ttk.Label(telegram, text="Token del bot").grid(
            row=2, column=0, sticky="w", padx=(0, 12), pady=5
        )
        self.telegram_token_entry = ttk.Entry(telegram, textvariable=self.telegram_token, show="•")
        self.telegram_token_entry.grid(row=2, column=1, sticky="ew", pady=5)
        buttons = ttk.Frame(telegram)
        buttons.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        buttons.columnconfigure((0, 1), weight=1)
        ttk.Button(buttons, text="Guardar", command=self._save_notifications).grid(
            row=0, column=0, sticky="ew", padx=(0, 5)
        )
        ttk.Button(buttons, text="Probar Telegram", command=self._test_telegram).grid(
            row=0, column=1, sticky="ew", padx=(5, 0)
        )

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
        self._toggle_telegram_fields()

    def _refresh_profiles(self, select: str | None = None) -> None:
        values = [NEW_PROFILE, *(account.name for account in self.config.accounts)]
        self.profile_combo.configure(values=values)
        selected = select if select in values else values[1] if len(values) > 1 else NEW_PROFILE
        self.profile_choice.set(selected)
        self._profile_selected()

    def _profile_selected(self, _event: object = None) -> None:
        if self.profile_choice.get() == NEW_PROFILE:
            self.account_name.set("")
            self.instagram_username.set("")
            return
        account = self.config.account(self.profile_choice.get())
        self.account_name.set(account.name)
        self.instagram_username.set(account.username)

    def _choose_followers(self) -> None:
        selected = filedialog.askopenfilenames(
            title="Elegir JSON de seguidores de Instagram",
            filetypes=(("Archivos JSON", "*.json"), ("Todos los archivos", "*.*")),
            parent=self.root,
        )
        if selected:
            self.follower_paths = tuple(Path(value) for value in selected)
            self.followers_label.set(", ".join(path.name for path in self.follower_paths))

    def _choose_following(self) -> None:
        selected = filedialog.askopenfilenames(
            title="Elegir JSON de seguidos de Instagram",
            filetypes=(("Archivos JSON", "*.json"), ("Todos los archivos", "*.*")),
            parent=self.root,
        )
        if selected:
            self.following_paths = tuple(Path(value) for value in selected)
            self.following_label.set(", ".join(path.name for path in self.following_paths))

    def _account_from_form(self) -> AccountConfig:
        account = AccountConfig(
            name=self.account_name.get().strip(),
            username=self.instagram_username.get().strip().lstrip("@"),
        )
        account.validate()
        selected = self.profile_choice.get()
        if selected != NEW_PROFILE and account.name.casefold() != selected.casefold():
            raise ConfigError(
                "El nombre local identifica el historial y no se puede renombrar. "
                "Elegí <Nuevo perfil> para crear otro."
            )
        return account

    def _save_account(self) -> AccountConfig:
        candidate = self._account_from_form()
        for account in self.config.accounts:
            if account.name.casefold() == candidate.name.casefold():
                account.username = candidate.username
                break
        else:
            self.config.accounts.append(candidate)
        save_config(self.paths, self.config)
        return candidate

    def _import_files(self) -> None:
        try:
            account = self._save_account()
            if not self.follower_paths or not self.following_paths:
                raise CollectionError("Seleccioná los archivos de seguidores y de seguidos.")
        except (ConfigError, CollectionError, OSError) as exc:
            messagebox.showerror("Importar JSON", str(exc), parent=self.root)
            return

        def work() -> str:
            graph = ExportCollector().collect_files(self.follower_paths, self.following_paths)
            comparison = Tracker(self.paths).record_graph(
                account, graph, datetime.now().astimezone()
            )
            failures = notify(comparison, self.config.notifications)
            report = format_report(comparison)
            if failures:
                report += "\n\nAvisos:\n" + "\n".join(
                    f"- {failure.channel}: {failure.error}" for failure in failures
                )
            return report

        def success(report: str) -> None:
            self._refresh_profiles(account.name)
            self._show_report(report)
            self._set_status("Archivos importados y captura guardada.")

        self.run_async("Leyendo y comparando los JSON…", work, success)

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

    def _cleanup_legacy_installation(self) -> None:
        if self.config.legacy_cleanup_done:
            return
        try:
            cleanup_legacy_state(self.paths)
            self.config.legacy_cleanup_done = True
            save_config(self.paths, self.config)
            self._set_status("Se retiró la automatización y las sesiones de la versión anterior.")
        except (LegacyCleanupError, OSError) as exc:
            messagebox.showwarning("Limpieza de versión anterior", str(exc), parent=self.root)

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
                "Operación en curso", "Esperá a que termine la operación actual.", parent=self.root
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
                    success(value)
                elif error:
                    error(value)
                else:
                    self._show_report(str(value))
                    messagebox.showerror("Error", str(value), parent=self.root)
                    self._set_status("La operación falló.")
        except queue.Empty:
            pass
        if self.root.winfo_exists():
            self.root.after(100, self._drain_events)

    def _set_status(self, message: str) -> None:
        self.status.set(message)

    def _close(self) -> None:
        if self.busy and not messagebox.askyesno(
            "Salir", "Hay una operación en curso. ¿Cerrar igualmente?", parent=self.root
        ):
            return
        self.root.destroy()


def main(paths: AppPaths | None = None) -> int:
    if sys.argv[1:] == ["--version"]:
        print(f"seguidores-gui {__version__}")
        return 0
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
