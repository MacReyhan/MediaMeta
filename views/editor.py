"""Right pane: metadata preview, editable fields, cast, artwork, files and NFO."""

from __future__ import annotations

import customtkinter as ctk

import images as art
import imgs
import nfo
import rename
import theme
from tmdb import image_url
from views.artwork import ArtworkPanel
from views.cast import CastPanel
from views.widgets import ctk_image, section_label

FIELDS = {
    "movie": (
        ("title", "Title"), ("original_title", "Original title"),
        ("year", "Year", "int"), ("premiered", "Release date"),
        ("runtime", "Runtime (min)", "int"), ("certification", "Certification"),
        ("rating", "Rating", "float"), ("tagline", "Tagline"),
        ("overview", "Overview", "text"),
        ("genres", "Genres", "list"), ("directors", "Directors", "list"),
        ("writers", "Writers", "list"), ("studios", "Studios", "list"),
        ("countries", "Countries", "list"), ("collection", "Collection"),
        ("trailer", "Trailer URL"),
        ("tmdb_id", "TMDB ID", "int"), ("imdb_id", "IMDb ID"),
    ),
    "show": (
        ("title", "Title"), ("original_title", "Original title"),
        ("year", "Year", "int"), ("premiered", "First aired"),
        ("runtime", "Episode runtime", "int"), ("certification", "Certification"),
        ("rating", "Rating", "float"), ("tagline", "Tagline"),
        ("overview", "Overview", "text"),
        ("genres", "Genres", "list"), ("studios", "Studios", "list"),
        ("countries", "Countries", "list"), ("network", "Network"),
        ("status", "Status"), ("trailer", "Trailer URL"),
        ("tmdb_id", "TMDB ID", "int"), ("imdb_id", "IMDb ID"),
        ("tvdb_id", "TVDB ID", "int"),
    ),
    "season": (
        ("title", "Title"), ("season", "Season number", "int"),
        ("premiered", "Air date"), ("year", "Year", "int"),
        ("overview", "Overview", "text"),
    ),
    "episode": (
        ("title", "Title"), ("season", "Season", "int"),
        ("episode", "Episode", "int"), ("premiered", "Air date"),
        ("runtime", "Runtime (min)", "int"), ("rating", "Rating", "float"),
        ("overview", "Overview", "text"),
        ("directors", "Directors", "list"), ("writers", "Writers", "list"),
        ("tmdb_id", "TMDB ID", "int"),
    ),
}

KIND_LABEL = {"movie": "Movie", "show": "TV show", "season": "Season", "episode": "Episode"}
STATE_COLOR = {
    "staged": theme.COLORS["accent"],
    "dirty": theme.COLORS["warn"],
    "saved": theme.COLORS["success"],
    "review": theme.COLORS["warn"],
    "error": theme.COLORS["danger"],
    "empty": theme.COLORS["text_muted"],
}


class EditorPane(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color=theme.COLORS["bg"], corner_radius=0)
        self.app = app
        self.entry = None
        self.node = None
        self._vars: dict[str, ctk.StringVar] = {}
        self._boxes: dict[str, ctk.CTkTextbox] = {}
        self._loading = False
        self._refs: list = []

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_header()
        self._build_tabs()
        self.clear()

    # ------------------------------------------------------------ chrome
    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color=theme.COLORS["surface"], corner_radius=0)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(1, weight=1)

        self.poster = ctk.CTkLabel(
            header, text="", width=96, height=144,
            fg_color=theme.COLORS["surface_alt"], corner_radius=theme.RADIUS_SM,
        )
        self.poster.grid(row=0, column=0, rowspan=4, padx=16, pady=14)

        self.title_label = ctk.CTkLabel(
            header, text="", font=theme.font(self, 20, "bold", display=True),
            text_color=theme.COLORS["text"], anchor="w",
        )
        self.title_label.grid(row=0, column=1, sticky="w", pady=(16, 0))

        self.sub_label = ctk.CTkLabel(
            header, text="", font=theme.font(self, 11),
            text_color=theme.COLORS["text_muted"], anchor="w", justify="left",
        )
        self.sub_label.grid(row=1, column=1, sticky="w", pady=(2, 0))

        self.badge_label = ctk.CTkLabel(
            header, text="", font=theme.font(self, 10, "bold"),
            text_color=theme.COLORS["text_muted"], anchor="w",
        )
        self.badge_label.grid(row=2, column=1, sticky="w", pady=(4, 14))

        buttons = ctk.CTkFrame(header, fg_color="transparent")
        buttons.grid(row=0, column=2, rowspan=3, sticky="e", padx=16, pady=16)

        self.scrape_btn = ctk.CTkButton(
            buttons, text="Scrape", width=96, height=32, corner_radius=theme.RADIUS_SM,
            fg_color=theme.COLORS["accent"], hover_color=theme.COLORS["accent_hover"],
            text_color=theme.COLORS["accent_text"], font=theme.font(self, 11, "bold"),
            command=self._scrape,
        )
        self.scrape_btn.pack(side="left", padx=(0, 6))

        self.fix_btn = ctk.CTkButton(
            buttons, text="Fix match…", width=96, height=32, corner_radius=theme.RADIUS_SM,
            fg_color="transparent", hover_color=theme.COLORS["card_hover"],
            text_color=theme.COLORS["text"], border_width=1, border_color=theme.COLORS["border"],
            font=theme.font(self, 11), command=self._fix,
        )
        self.fix_btn.pack(side="left", padx=(0, 6))

        self.save_btn = ctk.CTkButton(
            buttons, text="Save Changes", width=120, height=32, corner_radius=theme.RADIUS_SM,
            fg_color=theme.COLORS["accent"], hover_color=theme.COLORS["accent_hover"],
            text_color=theme.COLORS["accent_text"], font=theme.font(self, 11, "bold"),
            command=self._save,
        )
        self.save_btn.pack(side="left")

    def _build_tabs(self) -> None:
        self.tabs = ctk.CTkTabview(
            self, fg_color=theme.COLORS["bg"], corner_radius=0,
            segmented_button_selected_color=theme.COLORS["accent"],
            segmented_button_selected_hover_color=theme.COLORS["accent_hover"],
            segmented_button_unselected_color=theme.COLORS["surface"],
            text_color=theme.COLORS["text"],
        )
        self.tabs.grid(row=1, column=0, sticky="nsew", padx=12, pady=(8, 12))

        for name in ("Details", "Cast", "Artwork", "Files", "NFO"):
            self.tabs.add(name)

        self.details = ctk.CTkScrollableFrame(
            self.tabs.tab("Details"), fg_color="transparent", corner_radius=0
        )
        self.details.pack(fill="both", expand=True)
        self.details.grid_columnconfigure(1, weight=1)

        self.cast_panel = CastPanel(self.tabs.tab("Cast"), self.app, on_change=self.mark_dirty)
        self.cast_panel.pack(fill="both", expand=True)

        self.art_panel = ArtworkPanel(self.tabs.tab("Artwork"), self.app, on_change=self.mark_dirty)
        self.art_panel.pack(fill="both", expand=True)

        self.files_box = ctk.CTkTextbox(
            self.tabs.tab("Files"), fg_color=theme.COLORS["surface"],
            text_color=theme.COLORS["text"], font=theme.font(self, 11),
            corner_radius=theme.RADIUS_SM, wrap="none",
        )
        self.files_box.pack(fill="both", expand=True, padx=4, pady=4)

        self.nfo_box = ctk.CTkTextbox(
            self.tabs.tab("NFO"), fg_color=theme.COLORS["surface"],
            text_color=theme.COLORS["text"], font=theme.font(self, 11),
            corner_radius=theme.RADIUS_SM, wrap="none",
        )
        self.nfo_box.pack(fill="both", expand=True, padx=4, pady=4)

    # ------------------------------------------------------------ public
    def clear(self) -> None:
        self.entry = None
        self.node = None
        self.title_label.configure(text="Nothing selected")
        self.sub_label.configure(text="Pick a movie, show, season or episode on the left.")
        self.badge_label.configure(text="", text_color=theme.COLORS["text_muted"])
        self.poster.configure(image=None, text="")
        self._set_buttons(False)
        self._clear_details()
        ctk.CTkLabel(
            self.details,
            text="Scrape an item to preview its metadata here.\nNothing is written until you press Save Changes.",
            font=theme.font(self, 12), text_color=theme.COLORS["text_muted"],
            justify="left",
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=8, pady=16)
        self._set_textbox(self.files_box, "")
        self._set_textbox(self.nfo_box, "")

    def show(self, entry, node=None) -> None:
        self.entry = entry
        self.node = node
        if entry is None:
            self.clear()
            return

        self._set_buttons(True)
        self._build_details(entry)
        self.cast_panel.show(entry)
        self.art_panel.show(entry)
        self._fill_files(entry)
        self._fill_nfo(entry)
        self.refresh_header()
        self._load_poster(entry)

    def mark_dirty(self) -> None:
        if self.entry is None:
            return
        self.refresh_header()
        self._fill_files(self.entry)
        self._fill_nfo(self.entry)
        try:
            self.app.views["library"].tree_pane.refresh()
        except Exception:
            pass

    def refresh_header(self) -> None:
        entry = self.entry
        if entry is None:
            return
        title = entry.model.get("title") or entry.path.name
        if entry.kind == "episode":
            title = f"{title}"
        self.title_label.configure(text=title)

        bits = [KIND_LABEL.get(entry.kind, entry.kind.title())]
        if entry.model.get("year"):
            bits.append(str(entry.model["year"]))
        if entry.kind == "episode":
            bits.append(f"S{entry.season or 0:02d}E{entry.episode or 0:02d}")
        bits.append(str(entry.path))
        self.sub_label.configure(text="  ·  ".join(bits))

        colour = STATE_COLOR.get(entry.state, theme.COLORS["text_muted"])
        status = entry.status or entry.state
        if entry.state == "staged" and entry.confidence:
            status = f"staged · {entry.confidence}% match"
        self.badge_label.configure(
            text=f"{entry.state.upper()}   {status}", text_color=colour
        )

    # ------------------------------------------------------------ details
    def _clear_details(self) -> None:
        for widget in self.details.winfo_children():
            widget.destroy()
        self._vars.clear()
        self._boxes.clear()

    def _build_details(self, entry) -> None:
        self._clear_details()
        self._loading = True
        try:
            row = 0
            for spec in FIELDS.get(entry.kind, FIELDS["movie"]):
                key, label = spec[0], spec[1]
                kind = spec[2] if len(spec) > 2 else "str"
                section_label(self.details, label).grid(
                    row=row, column=0, sticky="nw", padx=(8, 12), pady=(8, 4)
                )
                if kind == "text":
                    box = ctk.CTkTextbox(
                        self.details, height=110, corner_radius=theme.RADIUS_SM,
                        fg_color=theme.COLORS["surface"], border_width=1,
                        border_color=theme.COLORS["border"], text_color=theme.COLORS["text"],
                        font=theme.font(self, 11), wrap="word",
                    )
                    box.insert("1.0", str(entry.get(key) or ""))
                    box.grid(row=row, column=1, sticky="ew", padx=(0, 10), pady=(4, 4))
                    box.bind("<KeyRelease>", lambda _e, k=key, b=box: self._set_text(k, b))
                    box.bind("<FocusOut>", lambda _e, k=key, b=box: self._set_text(k, b))
                    self._boxes[key] = box
                else:
                    value = entry.get(key)
                    if isinstance(value, list):
                        text = ", ".join(str(v) for v in value)
                    elif value is None:
                        text = ""
                    else:
                        text = str(value)
                    var = ctk.StringVar(value=text)
                    var.trace_add(
                        "write", lambda *_a, k=key, v=var, t=kind: self._set_var(k, v, t)
                    )
                    entry_widget = ctk.CTkEntry(
                        self.details, textvariable=var, height=32,
                        corner_radius=theme.RADIUS_SM, fg_color=theme.COLORS["surface"],
                        border_color=theme.COLORS["border"], text_color=theme.COLORS["text"],
                        font=theme.font(self, 11),
                        placeholder_text="comma separated" if kind == "list" else "",
                    )
                    entry_widget.grid(row=row, column=1, sticky="ew", padx=(0, 10), pady=(4, 4))
                    self._vars[key] = var
                row += 1

            hint = ctk.CTkLabel(
                self.details,
                text="Changes are staged. Press Save Changes to write NFO, artwork and renames.",
                font=theme.font(self, 10), text_color=theme.COLORS["text_muted"], anchor="w",
            )
            hint.grid(row=row, column=0, columnspan=2, sticky="w", padx=8, pady=(10, 16))
        finally:
            self._loading = False

    def _set_var(self, key: str, var, kind: str) -> None:
        if self._loading or self.entry is None:
            return
        raw = var.get().strip()
        if kind == "int":
            value = int(raw) if raw.lstrip("-").isdigit() else None
        elif kind == "float":
            try:
                value = round(float(raw), 1)
            except ValueError:
                value = None
        elif kind == "list":
            value = [part.strip() for part in raw.split(",") if part.strip()]
        else:
            value = raw
        self.entry.set(key, value)
        if key in ("season", "episode") and isinstance(value, int):
            setattr(self.entry, key, value)
        if key == "tmdb_id" and isinstance(value, int):
            self.entry.tmdb_id = value
        self.mark_dirty()

    def _set_text(self, key: str, box) -> None:
        if self._loading or self.entry is None:
            return
        value = box.get("1.0", "end-1c").strip()
        if self.entry.model.get(key) != value:
            self.entry.set(key, value)
            self.mark_dirty()

    # ------------------------------------------------------------ actions
    def _set_buttons(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        for btn in (self.scrape_btn, self.fix_btn, self.save_btn):
            btn.configure(state=state)

    def _scrape(self) -> None:
        if self.node is not None:
            self.app.views["library"].scrape_nodes([self.node])

    def _fix(self) -> None:
        if self.node is not None:
            self.app.views["library"].fix_match(self.node)

    def _save(self) -> None:
        self.app.views["library"].save_changes()

    # ------------------------------------------------------------ poster
    def _load_poster(self, entry) -> None:
        folder = entry.path if entry.path.is_dir() else entry.path.parent
        local = folder / art.POSTER
        if local.exists():
            image = ctk_image(local, (96, 144))
            if image is not None:
                self._refs.append(image)
                self.poster.configure(image=image, text="")
                return

        url = self._poster_url(entry)
        if not url:
            self.poster.configure(image=None, text="No\nposter")
            return

        def done(path) -> None:
            if self.entry is not entry:
                return
            image = ctk_image(path, (96, 144))
            if image is not None:
                self._refs.append(image)
                self.poster.configure(image=image, text="")

        self.app.run_async(lambda: imgs.cached(url, "w342"), done)

    def _poster_url(self, entry) -> str:
        if entry.kind == "season":
            return image_url((entry.data or {}).get("poster_path"), "w342")
        if entry.kind == "episode":
            return image_url(entry.model.get("thumb"), "w300")
        chosen = entry.art.get("poster")
        if chosen:
            return image_url(chosen, "w342")
        best = art.best(
            entry.data.get("images") or {}, "posters",
            (self.app.cfg.get("image_language") or "en").split(",")[0],
        )
        return art.url_for(best, "w342")

    # ------------------------------------------------------------ files
    def _fill_files(self, entry) -> None:
        lines: list[str] = []
        cfg = self.app.cfg
        try:
            if entry.kind == "movie":
                for ren in rename.plan_movie(entry, cfg):
                    tag = "FOLDER" if ren.kind == "folder" else "FILE  "
                    lines.append(f"{tag}  {ren.src.name}  →  {ren.dst.name}")
                if entry.video:
                    lines.append(f"WRITE   {entry.video.with_suffix('.nfo').name}")
                lines.append("WRITE   poster.jpg · fanart.jpg · banner.jpg · logo.png")
            elif entry.kind == "show":
                seasons = {
                    e.season: e for e in self.app.entries.entries.values()
                    if e.kind == "season" and e.path.parent == entry.path
                }
                episodes = [
                    e for e in self.app.entries.entries.values()
                    if e.kind == "episode" and e.video and entry.path in e.video.parents
                ]
                for ren in rename.plan_show(entry, seasons, episodes, cfg):
                    tag = "FOLDER" if ren.kind == "folder" else "FILE  "
                    lines.append(f"{tag}  {ren.src.name}  →  {ren.dst.name}")
                lines.append(f"WRITE   tvshow.nfo · poster.jpg · fanart.jpg · banner.jpg · logo.png")
                for number in sorted(seasons):
                    lines.append(f"WRITE   Season {number:02d} → season.nfo · season{number:02d}-poster.jpg")
                for episode in episodes:
                    lines.append(f"WRITE   {episode.video.stem}.nfo")
            elif entry.kind == "season":
                lines.append(f"WRITE   season.nfo · season{(entry.season or 0):02d}-poster.jpg")
            elif entry.kind == "episode":
                video = entry.video or entry.path
                lines.append(f"WRITE   {video.stem}.nfo · {video.stem}-thumb.jpg")
        except Exception as exc:  # noqa: BLE001
            lines.append(f"Could not plan: {type(exc).__name__}: {exc}")

        if not lines:
            lines = ["Nothing planned yet — scrape this item first."]
        if cfg.get("rename_files", True) or cfg.get("rename_folders", True):
            lines.append("")
            lines.append("Renaming is enabled — first commit asks for confirmation.")
        self._set_textbox(self.files_box, "\n".join(lines))

    def _fill_nfo(self, entry) -> None:
        try:
            embed = bool(self.app.cfg.get("embed_image_urls", True))
            if entry.kind == "movie":
                root = nfo.movie_nfo(entry.model, entry.cast, embed)
            elif entry.kind == "show":
                root = nfo.show_nfo(entry.model, entry.cast, embed)
            elif entry.kind == "season":
                root = nfo.season_nfo(entry.season or 0, entry.model)
            else:
                root = nfo.episode_nfo(entry.model, entry.cast, embed)
            self._set_textbox(self.nfo_box, nfo.to_string(root))
        except Exception as exc:  # noqa: BLE001
            self._set_textbox(self.nfo_box, f"Could not render NFO: {exc}")

    @staticmethod
    def _set_textbox(box: ctk.CTkTextbox, text: str) -> None:
        box.configure(state="normal")
        box.delete("1.0", "end")
        box.insert("1.0", text)
        box.configure(state="disabled")
