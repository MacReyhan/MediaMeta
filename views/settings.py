"""Settings view: credentials, language, artwork and safety switches."""

from __future__ import annotations

import os
import webbrowser

import customtkinter as ctk

import store
import theme
import tmdb

LANGUAGES = [
    "en-US", "en-GB", "it-IT", "de-DE", "fr-FR", "es-ES", "pt-BR", "pt-PT",
    "nl-NL", "pl-PL", "sv-SE", "da-DK", "fi-FI", "nb-NO", "ru-RU", "uk-UA",
    "tr-TR", "ja-JP", "ko-KR", "zh-CN", "zh-TW", "hi-IN", "ar-SA", "he-IL",
]


class SettingsView(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color=theme.COLORS["bg"], corner_radius=0)
        self.app = app
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        head = ctk.CTkFrame(self, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 6))
        ctk.CTkLabel(
            head, text="Settings",
            font=theme.font(self, 24, "bold", display=True),
            text_color=theme.COLORS["text"], anchor="w",
        ).pack(anchor="w")
        ctk.CTkLabel(
            head, text="Saved to %APPDATA%\\MediaMeta\\config.json — never to your media folders.",
            font=theme.font(self, 11), text_color=theme.COLORS["text_muted"], anchor="w",
        ).pack(anchor="w", pady=(2, 0))

        body = ctk.CTkScrollableFrame(
            self, fg_color=theme.COLORS["bg"], corner_radius=0,
        )
        body.grid(row=1, column=0, sticky="nsew", padx=14, pady=(4, 0))
        body.grid_columnconfigure(0, weight=1)

        row = 0
        row = self._section(body, row, "TMDB credential")
        row = self._token_card(body, row)
        row = self._section(body, row, "Matching")
        row = self._matching_card(body, row)
        row = self._section(body, row, "Library roots")
        row = self._roots_card(body, row)
        row = self._section(body, row, "Artwork")
        row = self._art_card(body, row)
        row = self._section(body, row, "Renaming")
        row = self._naming_card(body, row)
        row = self._section(body, row, "Advanced")
        row = self._advanced_card(body, row)

        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.grid(row=2, column=0, sticky="ew", padx=20, pady=12)
        actions.grid_columnconfigure(0, weight=1)

        self.hint = ctk.CTkLabel(
            actions, text="", font=theme.font(self, 11),
            text_color=theme.COLORS["text_muted"], anchor="w",
        )
        self.hint.grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            actions, text="Open config folder", width=150, height=34,
            corner_radius=theme.RADIUS_SM, fg_color="transparent",
            hover_color=theme.COLORS["card_hover"], text_color=theme.COLORS["text_muted"],
            border_width=1, border_color=theme.COLORS["border"],
            font=theme.font(self, 11), command=self._open_config,
        ).grid(row=0, column=1, padx=(0, 8))

        ctk.CTkButton(
            actions, text="Save", width=120, height=34,
            corner_radius=theme.RADIUS_SM, fg_color=theme.COLORS["accent"],
            hover_color=theme.COLORS["accent_hover"], text_color=theme.COLORS["accent_text"],
            font=theme.font(self, 12, "bold"), command=self.save,
        ).grid(row=0, column=2)

        self._load()

    # ------------------------------------------------------------ widgets
    def _section(self, parent, row: int, title: str) -> int:
        ctk.CTkLabel(
            parent, text=title, font=theme.font(self, 12, "bold"),
            text_color=theme.COLORS["text"], anchor="w",
        ).grid(row=row, column=0, sticky="w", padx=8, pady=(14, 4))
        return row + 1

    def _card(self, parent, row: int) -> tuple[ctk.CTkFrame, int]:
        card = ctk.CTkFrame(
            parent, fg_color=theme.COLORS["surface"], corner_radius=theme.RADIUS,
            border_width=1, border_color=theme.COLORS["border"],
        )
        card.grid(row=row, column=0, sticky="ew", padx=8, pady=(0, 2))
        card.grid_columnconfigure(1, weight=1)
        return card, row + 1

    def _label(self, card, row: int, text: str, sub: str = "") -> None:
        holder = ctk.CTkFrame(card, fg_color="transparent")
        holder.grid(row=row, column=0, sticky="w", padx=16, pady=10)
        ctk.CTkLabel(
            holder, text=text, font=theme.font(self, 12),
            text_color=theme.COLORS["text"], anchor="w",
        ).pack(anchor="w")
        if sub:
            ctk.CTkLabel(
                holder, text=sub, font=theme.font(self, 10),
                text_color=theme.COLORS["text_muted"], anchor="w", justify="left",
            ).pack(anchor="w")

    # ------------------------------------------------------------ cards
    def _token_card(self, parent, row: int) -> int:
        card, row = self._card(parent, row)
        self._label(card, 0, "API key / Read Access Token", "v4 tokens are sent as a Bearer header.")

        self.token_var = ctk.StringVar()
        self.token_entry = ctk.CTkEntry(
            card, textvariable=self.token_var, show="•", height=34,
            corner_radius=theme.RADIUS_SM, fg_color=theme.COLORS["surface_alt"],
            border_color=theme.COLORS["border"], text_color=theme.COLORS["text"],
            font=theme.font(self, 11),
        )
        self.token_entry.grid(row=0, column=1, sticky="ew", padx=(0, 12), pady=10)

        self.reveal_var = ctk.BooleanVar(value=False)
        ctk.CTkSwitch(
            card, text="Show", variable=self.reveal_var, width=90,
            command=lambda: self.token_entry.configure(show="" if self.reveal_var.get() else "•"),
            progress_color=theme.COLORS["accent"], text_color=theme.COLORS["text_muted"],
            font=theme.font(self, 10),
        ).grid(row=0, column=2, padx=(0, 10))

        ctk.CTkButton(
            card, text="Test", width=70, height=30, corner_radius=theme.RADIUS_SM,
            fg_color="transparent", hover_color=theme.COLORS["card_hover"],
            text_color=theme.COLORS["text"], border_width=1, border_color=theme.COLORS["border"],
            font=theme.font(self, 10), command=self.test_connection,
        ).grid(row=0, column=3, padx=(0, 16))

        ctk.CTkButton(
            card, text="Get a key →", width=100, height=26, corner_radius=theme.RADIUS_SM,
            fg_color="transparent", hover_color=theme.COLORS["card_hover"],
            text_color=theme.COLORS["accent"], font=theme.font(self, 10),
            command=lambda: webbrowser.open("https://www.themoviedb.org/settings/api"),
        ).grid(row=1, column=1, sticky="w", padx=(2, 0), pady=(0, 10))
        return row

    def _matching_card(self, parent, row: int) -> int:
        card, row = self._card(parent, row)

        self._label(card, 0, "Metadata language", "Titles, overviews and taglines.")
        self.lang_var = ctk.StringVar()
        ctk.CTkOptionMenu(
            card, values=LANGUAGES, variable=self.lang_var, width=140, height=32,
            corner_radius=theme.RADIUS_SM, fg_color=theme.COLORS["surface_alt"],
            button_color=theme.COLORS["border"], button_hover_color=theme.COLORS["card_hover"],
            text_color=theme.COLORS["text"], font=theme.font(self, 11),
        ).grid(row=0, column=1, sticky="w", padx=(0, 16), pady=10)

        self._label(card, 1, "Artwork languages", "Comma list, first match wins, e.g. en,null")
        self.imglang_var = ctk.StringVar()
        ctk.CTkEntry(
            card, textvariable=self.imglang_var, height=32, width=140,
            corner_radius=theme.RADIUS_SM, fg_color=theme.COLORS["surface_alt"],
            border_color=theme.COLORS["border"], text_color=theme.COLORS["text"],
            font=theme.font(self, 11),
        ).grid(row=1, column=1, sticky="w", padx=(0, 16), pady=(0, 10))

        self._label(card, 2, "Auto-write threshold", "Below this score an item is left for review.")
        holder = ctk.CTkFrame(card, fg_color="transparent")
        holder.grid(row=2, column=1, sticky="ew", padx=(0, 16), pady=(0, 10))
        self.threshold_var = ctk.IntVar(value=80)
        ctk.CTkSlider(
            holder, from_=50, to=100, number_of_steps=10, variable=self.threshold_var,
            progress_color=theme.COLORS["accent"], button_color=theme.COLORS["accent"],
            button_hover_color=theme.COLORS["accent_hover"],
        ).pack(side="left", fill="x", expand=True)
        self.threshold_label = ctk.CTkLabel(
            holder, text="80%", width=46, font=theme.font(self, 11),
            text_color=theme.COLORS["text_muted"],
        )
        self.threshold_label.pack(side="left", padx=(8, 0))
        self.threshold_var.trace_add(
            "write", lambda *_: self.threshold_label.configure(text=f"{self.threshold_var.get()}%")
        )
        return row

    def _art_card(self, parent, row: int) -> int:
        card, row = self._card(parent, row)
        self.overwrite_var = ctk.BooleanVar()
        self.actors_var = ctk.BooleanVar()
        self.embed_var = ctk.BooleanVar()

        items = [
            ("Overwrite existing artwork", "Off = only fill in missing images.", self.overwrite_var),
            ("Download actor headshots", "Saves into .actors next to the media.", self.actors_var),
            ("Embed image URLs in NFO", "Jellyfin/Emby can fetch people images itself.", self.embed_var),
        ]
        for idx, (text, sub, var) in enumerate(items):
            self._label(card, idx, text, sub)
            ctk.CTkSwitch(
                card, text="", variable=var, width=44,
                progress_color=theme.COLORS["accent"],
            ).grid(row=idx, column=1, sticky="w", padx=(0, 16), pady=10)
        return row

    def _roots_card(self, parent, row: int) -> int:
        card, row = self._card(parent, row)
        holder = ctk.CTkFrame(card, fg_color="transparent")
        holder.grid(row=0, column=0, columnspan=2, sticky="ew", padx=16, pady=12)
        holder.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            holder,
            text="Every root shows up in the library tree. Nothing outside them is touched.",
            font=theme.font(self, 10), text_color=theme.COLORS["text_muted"], anchor="w",
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            holder, text="Add folder…", width=120, height=30,
            corner_radius=theme.RADIUS_SM, fg_color="transparent",
            hover_color=theme.COLORS["card_hover"], text_color=theme.COLORS["text"],
            border_width=1, border_color=theme.COLORS["border"],
            font=theme.font(self, 10), command=self.add_root,
        ).grid(row=0, column=1, sticky="e")

        self.roots_list = ctk.CTkFrame(holder, fg_color="transparent")
        self.roots_list.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        self.roots_list.grid_columnconfigure(0, weight=1)
        self.refresh_roots()
        return row

    def refresh_roots(self) -> None:
        if not hasattr(self, "roots_list"):
            return
        for widget in self.roots_list.winfo_children():
            widget.destroy()

        roots = list(self.app.cfg.get("library_roots") or [])
        if not roots:
            ctk.CTkLabel(
                self.roots_list, text="No roots yet.",
                font=theme.font(self, 10), text_color=theme.COLORS["text_muted"], anchor="w",
            ).grid(row=0, column=0, sticky="w")
            return

        for idx, path in enumerate(roots):
            holder = ctk.CTkFrame(
                self.roots_list, fg_color=theme.COLORS["surface_alt"],
                corner_radius=theme.RADIUS_SM,
            )
            holder.grid(row=idx, column=0, sticky="ew", pady=2)
            holder.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(
                holder, text=path, font=theme.font(self, 10),
                text_color=theme.COLORS["text"], anchor="w",
            ).grid(row=0, column=0, sticky="w", padx=8, pady=6)
            ctk.CTkButton(
                holder, text="✕", width=26, height=24, corner_radius=4,
                fg_color="transparent", hover_color=theme.COLORS["card_hover"],
                text_color=theme.COLORS["danger"], font=theme.font(self, 10),
                command=lambda p=path: self.remove_root(p),
            ).grid(row=0, column=1, padx=4)

    def add_root(self) -> None:
        from tkinter import filedialog

        chosen = filedialog.askdirectory(title="Add a library root")
        if not chosen:
            return
        roots = list(self.app.cfg.get("library_roots") or [])
        if chosen in roots:
            return
        roots.append(chosen)
        self.app.cfg["library_roots"] = roots
        self.app.save_config()
        self.refresh_roots()
        self.app.views["library"].reload_roots()

    def remove_root(self, path: str) -> None:
        roots = [p for p in (self.app.cfg.get("library_roots") or []) if p != path]
        self.app.cfg["library_roots"] = roots
        self.app.save_config()
        self.refresh_roots()
        self.app.views["library"].reload_roots()

    def _naming_card(self, parent, row: int) -> int:
        card, row = self._card(parent, row)
        self.rename_files_var = ctk.BooleanVar()
        self.rename_folders_var = ctk.BooleanVar()
        self.confirm_var = ctk.BooleanVar()
        self.template_vars: dict[str, ctk.StringVar] = {}

        items = [
            ("Rename media files", "Movie and episode files follow the templates below.", self.rename_files_var),
            ("Rename folders", "Movie, show and season folders.", self.rename_folders_var),
        ]
        for idx, (text, sub, var) in enumerate(items):
            self._label(card, idx, text, sub)
            ctk.CTkSwitch(
                card, text="", variable=var, width=44,
                progress_color=theme.COLORS["accent"],
            ).grid(row=idx, column=1, sticky="w", padx=(0, 16), pady=10)

        templates = [
            ("rename_movie_file", "Movie file", "{title} ({year})"),
            ("rename_movie_folder", "Movie folder", "{title} ({year})"),
            ("rename_show_folder", "Show folder", "{show} ({year})"),
            ("rename_season_folder", "Season folder", "Season {season:02}"),
            ("rename_episode_file", "Episode file", "{show} - S{season:02}E{episode:02} - {title}"),
        ]
        start = len(items)
        for offset, (key, label, hint) in enumerate(templates):
            self._label(card, start + offset, label, hint)
            var = ctk.StringVar()
            self.template_vars[key] = var
            ctk.CTkEntry(
                card, textvariable=var, height=30,
                corner_radius=theme.RADIUS_SM, fg_color=theme.COLORS["surface_alt"],
                border_color=theme.COLORS["border"], text_color=theme.COLORS["text"],
                font=theme.font(self, 10),
            ).grid(row=start + offset, column=1, sticky="ew", padx=(0, 16), pady=(4, 4))

        last = start + len(templates)
        self._label(card, last, "Confirm before first save", "Shows the rename plan once, then remembers.")
        ctk.CTkSwitch(
            card, text="", variable=self.confirm_var, width=44,
            progress_color=theme.COLORS["accent"],
        ).grid(row=last, column=1, sticky="w", padx=(0, 16), pady=(4, 12))
        return row

    def _advanced_card(self, parent, row: int) -> int:
        card, row = self._card(parent, row)
        self._label(card, 0, "Parallel downloads", "Keep it low — TMDB throttles bursts.")
        holder = ctk.CTkFrame(card, fg_color="transparent")
        holder.grid(row=0, column=1, sticky="ew", padx=(0, 16), pady=10)
        self.threads_var = ctk.IntVar(value=4)
        ctk.CTkSlider(
            holder, from_=1, to=8, number_of_steps=7, variable=self.threads_var,
            progress_color=theme.COLORS["accent"], button_color=theme.COLORS["accent"],
            button_hover_color=theme.COLORS["accent_hover"],
        ).pack(side="left", fill="x", expand=True)
        self.threads_label = ctk.CTkLabel(
            holder, text="4", width=30, font=theme.font(self, 11),
            text_color=theme.COLORS["text_muted"],
        )
        self.threads_label.pack(side="left", padx=(8, 0))
        self.threads_var.trace_add(
            "write", lambda *_: self.threads_label.configure(text=str(self.threads_var.get()))
        )
        return row

    # ------------------------------------------------------------ actions
    def _load(self) -> None:
        cfg = self.app.cfg
        self.token_var.set(cfg.get("tmdb_token", ""))
        self.lang_var.set(cfg.get("language", "en-US"))
        self.imglang_var.set(cfg.get("image_language", "en,null"))
        self.threshold_var.set(int(cfg.get("confidence_threshold", 80)))
        self.threshold_label.configure(text=f"{self.threshold_var.get()}%")
        self.threads_var.set(int(cfg.get("threads", 4)))
        self.threads_label.configure(text=str(self.threads_var.get()))
        self.overwrite_var.set(bool(cfg.get("overwrite_art", False)))
        self.actors_var.set(bool(cfg.get("download_actor_images", True)))
        self.embed_var.set(bool(cfg.get("embed_image_urls", True)))
        self.rename_files_var.set(bool(cfg.get("rename_files", True)))
        self.rename_folders_var.set(bool(cfg.get("rename_folders", True)))
        self.confirm_var.set(bool(cfg.get("confirm_first_commit", True)))
        for key, var in self.template_vars.items():
            var.set(str(cfg.get(key, store.DEFAULTS.get(key, ""))))
        self.refresh_roots()

    def save(self) -> None:
        cfg = self.app.cfg
        cfg["tmdb_token"] = self.token_var.get().strip()
        cfg["language"] = self.lang_var.get()
        cfg["image_language"] = self.imglang_var.get().strip() or "en,null"
        cfg["confidence_threshold"] = int(self.threshold_var.get())
        cfg["threads"] = int(self.threads_var.get())
        cfg["overwrite_art"] = bool(self.overwrite_var.get())
        cfg["download_actor_images"] = bool(self.actors_var.get())
        cfg["embed_image_urls"] = bool(self.embed_var.get())
        cfg["rename_files"] = bool(self.rename_files_var.get())
        cfg["rename_folders"] = bool(self.rename_folders_var.get())
        cfg["confirm_first_commit"] = bool(self.confirm_var.get())
        for key, var in self.template_vars.items():
            cfg[key] = var.get().strip() or store.DEFAULTS.get(key, "")
        store.save_config(cfg)
        self.app.reset_client()
        self.app.views["library"].reload_roots()
        self.hint.configure(text="Saved.", text_color=theme.resolve(theme.COLORS["success"]))
        self.app.log("settings saved", "info")

    def test_connection(self) -> None:
        token = self.token_var.get().strip()
        if not token:
            self.hint.configure(text="No token entered.", text_color=theme.resolve(theme.COLORS["danger"]))
            return
        self.hint.configure(text="Testing…", text_color=theme.resolve(theme.COLORS["text_muted"]))

        def work():
            client = tmdb.TMDB(
                token,
                language=self.lang_var.get(),
                image_language=self.imglang_var.get(),
            )
            return client.search_movie("Inception")

        def done(results) -> None:
            if results:
                self.hint.configure(
                    text=f"Connected — {len(results)} result(s) for “Inception”.",
                    text_color=theme.resolve(theme.COLORS["success"]),
                )
            else:
                self.hint.configure(
                    text="Connected, but the search returned nothing.",
                    text_color=theme.resolve(theme.COLORS["warn"]),
                )

        self.app.run_async(work, done)

    def _open_config(self) -> None:
        store.ensure_dirs()
        try:
            os.startfile(store.CONFIG_DIR)  # noqa: S606
        except Exception:
            pass
