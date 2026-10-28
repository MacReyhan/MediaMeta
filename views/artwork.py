"""Artwork tab: pick posters, fanart, logos and episode stills."""

from __future__ import annotations

import customtkinter as ctk

import images as art
import imgs
import theme
from tmdb import image_url
from views.widgets import ctk_image

SECTIONS = {
    "movie": (("poster", "Poster", (150, 225)), ("fanart", "Fanart", (260, 146)), ("logo", "Logo", (180, 90))),
    "show": (("poster", "Poster", (150, 225)), ("fanart", "Fanart", (260, 146)), ("logo", "Logo", (180, 90))),
    "season": (("poster", "Season poster", (150, 225)),),
    "episode": (("thumb", "Episode still", (260, 146)),),
}

IMAGE_KEYS = {"poster": "posters", "fanart": "backdrops", "logo": "logos", "thumb": "stills"}
PICK_SIZE = {"poster": "w342", "fanart": "w780", "logo": "w300", "thumb": "w780"}


class ArtworkPanel(ctk.CTkFrame):
    def __init__(self, master, app, on_change=None):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.on_change = on_change
        self.entry = None
        self._refs: list = []
        self._option_map: dict[str, dict[str, str]] = {}
        self._previews: dict[str, ctk.CTkLabel] = {}

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent", corner_radius=0)
        self.scroll.grid(row=0, column=0, sticky="nsew")
        self.scroll.grid_columnconfigure(0, weight=1)

    # ------------------------------------------------------------ render
    def show(self, entry) -> None:
        self.entry = entry
        for widget in self.scroll.winfo_children():
            widget.destroy()
        self._refs.clear()
        self._option_map.clear()
        self._previews.clear()

        if entry is None:
            return

        for idx, (key, title, size) in enumerate(SECTIONS.get(entry.kind, SECTIONS["movie"])):
            self._section(idx, key, title, size)

    def _section(self, row: int, key: str, title: str, size: tuple[int, int]) -> None:
        entry = self.entry
        card = ctk.CTkFrame(
            self.scroll, fg_color=theme.COLORS["surface"], corner_radius=theme.RADIUS,
            border_width=1, border_color=theme.COLORS["border"],
        )
        card.grid(row=row, column=0, sticky="ew", padx=6, pady=6)
        card.grid_columnconfigure(1, weight=1)

        preview = ctk.CTkLabel(
            card, text="", width=size[0], height=size[1],
            fg_color=theme.COLORS["surface_alt"], corner_radius=theme.RADIUS_SM,
        )
        preview.grid(row=0, column=0, rowspan=3, padx=12, pady=12)
        self._previews[key] = preview

        ctk.CTkLabel(
            card, text=title, font=theme.font(self, 12, "bold"),
            text_color=theme.COLORS["text"], anchor="w",
        ).grid(row=0, column=1, sticky="w", padx=(0, 12), pady=(12, 2))

        options = self._collect(key)
        labels = ["Auto — best available"]
        mapping = {"Auto — best available": ""}
        for idx, item in enumerate(options, start=1):
            label = self._label_for(item, idx)
            labels.append(label)
            mapping[label] = item.get("file_path") or ""
        self._option_map[key] = mapping

        current = entry.art.get(key) or ""
        current_label = "Auto — best available"
        if current:
            for label, path in mapping.items():
                if path == current:
                    current_label = label
                    break

        var = ctk.StringVar(value=current_label)
        menu = ctk.CTkOptionMenu(
            card, values=labels, variable=var, height=30,
            corner_radius=theme.RADIUS_SM, fg_color=theme.COLORS["surface_alt"],
            button_color=theme.COLORS["border"], button_hover_color=theme.COLORS["card_hover"],
            text_color=theme.COLORS["text"], font=theme.font(self, 10),
            dynamic_resizing=False,
            command=lambda choice, k=key: self._choose(k, choice),
        )
        menu.grid(row=1, column=1, sticky="ew", padx=(0, 12), pady=(0, 4))

        note = self._disk_note(key)
        ctk.CTkLabel(
            card, text=note, font=theme.font(self, 10),
            text_color=theme.COLORS["text_muted"], anchor="w",
        ).grid(row=2, column=1, sticky="w", padx=(0, 12), pady=(0, 12))

        self._load_preview(key, size)

    def _label_for(self, item: dict, index: int) -> str:
        lang = item.get("iso_639_1") or "—"
        width = item.get("width") or 0
        height = item.get("height") or 0
        vote = item.get("vote_average") or 0
        return f"{index}. {lang} · {width}×{height} · ★{vote:.1f}"

    def _collect(self, key: str) -> list[dict]:
        entry = self.entry
        if entry is None:
            return []

        if key == "thumb":
            items = list((entry.data.get("images") or {}).get("stills") or [])
            if not items and entry.model.get("thumb"):
                items = [{"file_path": entry.model["thumb"], "iso_639_1": None,
                          "width": 0, "height": 0, "vote_average": 0}]
            return items

        if key == "poster" and entry.kind == "season":
            path = (entry.data or {}).get("poster_path")
            return [{"file_path": path, "iso_639_1": None, "width": 0,
                     "height": 0, "vote_average": 0}] if path else []

        return list((entry.data.get("images") or {}).get(IMAGE_KEYS[key]) or [])

    def _disk_note(self, key: str) -> str:
        entry = self.entry
        folder = entry.path if entry.path.is_dir() else entry.path.parent
        if key == "poster" and entry.kind == "season":
            name = art.season_poster_name(entry.season or 0)
        elif key == "thumb":
            video = entry.video or entry.path
            name = art.episode_thumb_name(video)
        else:
            name = {"poster": art.POSTER, "fanart": art.FANART, "logo": art.LOGO}[key]
        target = folder / name
        state = "present" if target.exists() else "not written yet"
        return f"{name} — {state}"

    # ------------------------------------------------------------ actions
    def _choose(self, key: str, label: str) -> None:
        if self.entry is None:
            return
        path = self._option_map.get(key, {}).get(label, "")
        if path:
            self.entry.art[key] = path
        else:
            self.entry.art.pop(key, None)
        self.entry.touch()
        if self.on_change:
            self.on_change()
        size = dict((k, s) for k, _t, s in SECTIONS.get(self.entry.kind, ())).get(key, (150, 225))
        self._load_preview(key, size)

    # ------------------------------------------------------------ preview
    def _preview_url(self, key: str) -> str:
        entry = self.entry
        if entry is None:
            return ""
        chosen = entry.art.get(key)
        if chosen:
            return image_url(chosen, PICK_SIZE[key])

        if key == "thumb":
            return image_url(entry.model.get("thumb"), "w780") if entry.model.get("thumb") else ""

        if key == "poster" and entry.kind == "season":
            return image_url((entry.data or {}).get("poster_path"), "w342")

        best = art.best(entry.data.get("images") or {}, IMAGE_KEYS[key],
                        (self.app.cfg.get("image_language") or "en").split(",")[0])
        return art.url_for(best, PICK_SIZE[key])

    def _load_preview(self, key: str, size: tuple[int, int]) -> None:
        entry = self.entry
        label = self._previews.get(key)
        if entry is None or label is None:
            return

        local = self._local_file(key)
        if local and local.exists() and not entry.art.get(key):
            image = ctk_image(local, size)
            if image is not None:
                self._refs.append(image)
                label.configure(image=image, text="")
                return

        url = self._preview_url(key)
        if not url:
            label.configure(image=None, text="No artwork")
            return

        def done(path) -> None:
            if self.entry is not entry:
                return
            image = ctk_image(path, size)
            if image is not None:
                self._refs.append(image)
                label.configure(image=image, text="")

        self.app.run_async(lambda: imgs.cached(url, PICK_SIZE[key]), done)

    def _local_file(self, key: str):
        entry = self.entry
        folder = entry.path if entry.path.is_dir() else entry.path.parent
        if key == "poster" and entry.kind == "season":
            return folder / art.season_poster_name(entry.season or 0)
        if key == "thumb":
            video = entry.video or entry.path
            return folder / art.episode_thumb_name(video)
        name = {"poster": art.POSTER, "fanart": art.FANART, "logo": art.LOGO}.get(key)
        return folder / name if name else None
