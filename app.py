"""MediaMeta — a small, review-first TMDB scraper for movies and TV shows."""

from __future__ import annotations

import queue
import sys
import threading
import traceback
from pathlib import Path

try:
    import customtkinter as ctk
except ImportError:  # pragma: no cover - friendly first-run failure
    import tkinter as tk
    from tkinter import messagebox

    root = tk.Tk()
    root.withdraw()
    messagebox.showerror(
        "MediaMeta",
        "CustomTkinter is not installed.\n\n"
        "Run run.bat, or:\n"
        "    python -m pip install -r requirements.txt",
    )
    raise SystemExit(1)

from tkinter import messagebox

import edit
import store
import theme
import tmdb
from views.library import LibraryView
from views.logview import LogView
from views.settings import SettingsView

APP_TITLE = "MediaMeta"


class MediaMetaApp(ctk.CTk):
    def __init__(self):
        cfg = store.load_config()
        theme.apply_appearance(cfg.get("appearance", "dark"))
        super().__init__(fg_color=theme.COLORS["bg"])

        self.cfg = cfg
        self.entries = edit.EntryStore()
        self.manifest = store.Manifest()
        self._client: tmdb.TMDB | None = None
        self._q: queue.Queue = queue.Queue()
        self._busy = False

        self.title(APP_TITLE)
        self.geometry("1180x780")
        self.minsize(1000, 640)

        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_rail()
        self._build_content()
        self._pump()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.show("library")

    # ------------------------------------------------------------ chrome
    def _build_rail(self) -> None:
        rail = ctk.CTkFrame(self, width=232, corner_radius=0, fg_color=theme.COLORS["rail"])
        rail.grid(row=0, column=0, sticky="nsw")
        rail.grid_propagate(False)

        brand = ctk.CTkFrame(rail, fg_color="transparent")
        brand.pack(fill="x", padx=18, pady=(22, 18))
        ctk.CTkLabel(
            brand,
            text="MediaMeta",
            font=theme.font(self, 22, "bold", display=True),
            text_color=theme.COLORS["text"],
            anchor="w",
        ).pack(anchor="w")
        ctk.CTkLabel(
            brand,
            text="TMDB metadata, reviewed",
            font=theme.font(self, 11),
            text_color=theme.COLORS["text_muted"],
            anchor="w",
        ).pack(anchor="w")

        self._nav_buttons: dict[str, ctk.CTkButton] = {}
        for key, label in (
            ("library", "  Library"),
            ("activity", "  Activity"),
            ("settings", "  Settings"),
        ):
            btn = ctk.CTkButton(
                rail,
                text=label,
                anchor="w",
                height=40,
                corner_radius=theme.RADIUS_SM,
                fg_color="transparent",
                hover_color=theme.COLORS["card_hover"],
                text_color=theme.COLORS["text"],
                font=theme.font(self, 13),
                command=lambda k=key: self.show(k),
            )
            btn.pack(fill="x", padx=10, pady=2)
            self._nav_buttons[key] = btn

        spacer = ctk.CTkFrame(rail, fg_color="transparent")
        spacer.pack(fill="both", expand=True)

        self.appearance_switch = ctk.CTkSwitch(
            rail,
            text="Dark mode",
            command=self._toggle_appearance,
            progress_color=theme.COLORS["accent"],
            text_color=theme.COLORS["text_muted"],
            font=theme.font(self, 11),
        )
        self.appearance_switch.pack(anchor="w", padx=20, pady=18)
        if self.cfg.get("appearance", "dark") == "dark":
            self.appearance_switch.select()

        ctk.CTkLabel(
            rail,
            text="v1.0 · TMDB",
            font=theme.font(self, 10),
            text_color=theme.COLORS["text_muted"],
        ).pack(anchor="w", padx=20, pady=(0, 16))

    def _build_content(self) -> None:
        self.container = ctk.CTkFrame(self, fg_color=theme.COLORS["bg"], corner_radius=0)
        self.container.grid(row=0, column=1, sticky="nsew")
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)

        self.views = {}
        for key, cls in (
            ("library", LibraryView),
            ("activity", LogView),
            ("settings", SettingsView),
        ):
            view = cls(self.container, self)
            view.grid(row=0, column=0, sticky="nsew")
            self.views[key] = view

        footer = ctk.CTkFrame(self.container, fg_color=theme.COLORS["surface"], corner_radius=0, height=44)
        footer.grid(row=1, column=0, sticky="ew")
        footer.grid_columnconfigure(0, weight=1)

        self.status_label = ctk.CTkLabel(
            footer,
            text="Ready",
            font=theme.font(self, 11),
            text_color=theme.COLORS["text_muted"],
            anchor="w",
        )
        self.status_label.grid(row=0, column=0, sticky="w", padx=16, pady=12)

        self.progressbar = ctk.CTkProgressBar(
            footer,
            width=220,
            height=6,
            corner_radius=3,
            progress_color=theme.COLORS["accent"],
            fg_color=theme.COLORS["border"],
        )
        self.progressbar.grid(row=0, column=1, sticky="e", padx=16)
        self.progressbar.set(0)

    def show(self, key: str) -> None:
        view = self.views.get(key)
        if not view:
            return
        view.tkraise()
        for name, btn in self._nav_buttons.items():
            btn.configure(
                fg_color=theme.COLORS["rail_active"] if name == key else "transparent"
            )

    def _toggle_appearance(self) -> None:
        mode = "dark" if self.appearance_switch.get() else "light"
        self.cfg["appearance"] = mode
        store.save_config(self.cfg)
        theme.apply_appearance(mode)
        theme.style_treeview(self, mode)
        self.views["library"].restyle()

    # ------------------------------------------------------------ plumbing
    def log(self, message: str, level: str = "info") -> None:
        self._q.put(("log", level, str(message)))

    def progress(self, value: float, text: str | None = None) -> None:
        self._q.put(("progress", float(value), text))

    def post(self, fn) -> None:
        self._q.put(("call", fn, None))

    def _pump(self) -> None:
        try:
            while True:
                kind, a, b = self._q.get_nowait()
                if kind == "log":
                    self.views["activity"].append(a, b)
                    store.log_line(f"{a.upper():<5} {b}")
                elif kind == "progress":
                    self.progressbar.set(max(0.0, min(1.0, a)))
                    if b:
                        self.status_label.configure(text=b)
                elif kind == "call":
                    a()
        except queue.Empty:
            pass
        self.after(110, self._pump)

    def run_async(self, fn, done=None) -> None:
        def runner() -> None:
            try:
                result = fn()
            except Exception as exc:
                self.log(f"{type(exc).__name__}: {exc}", "error")
                traceback.print_exc()
                result = None
            if done is not None:
                self.post(lambda: done(result))

        threading.Thread(target=runner, daemon=True).start()

    # ------------------------------------------------------------ client
    def client(self) -> tmdb.TMDB | None:
        token = (self.cfg.get("tmdb_token") or "").strip()
        if not token:
            messagebox.showinfo(
                APP_TITLE,
                "Add your TMDB API key or Read Access Token in Settings first.",
            )
            self.show("settings")
            return None
        if self._client is None:
            self._client = tmdb.TMDB(
                token,
                language=self.cfg.get("language", "en-US"),
                image_language=self.cfg.get("image_language", "en,null"),
            )
        return self._client

    def reset_client(self) -> None:
        self._client = None

    @property
    def busy(self) -> bool:
        return self._busy

    def set_busy(self, value: bool) -> None:
        self._busy = value
        self.post(lambda: self.views["library"].set_busy(value))

    def _on_close(self) -> None:
        self.save_config()
        self.destroy()

    def save_config(self) -> None:
        try:
            store.save_config(self.cfg)
        except Exception:
            pass


def main() -> int:
    store.ensure_dirs()
    app = MediaMetaApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
