"""Cast tab: edit, reorder, remove and include/exclude actors."""

from __future__ import annotations

import threading

import customtkinter as ctk

import imgs
import theme
from views.widgets import ctk_image

VISIBLE_LIMIT = 40


class CastPanel(ctk.CTkFrame):
    def __init__(self, master, app, on_change=None):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.on_change = on_change
        self.entry = None
        self._refs: list = []
        self._labels: dict[int, ctk.CTkLabel] = {}
        self._load_token = 0

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        head = ctk.CTkFrame(self, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=4, pady=(4, 6))
        head.grid_columnconfigure(0, weight=1)

        self.caption = ctk.CTkLabel(
            head, text="Cast", font=theme.font(self, 12, "bold"),
            text_color=theme.COLORS["text"], anchor="w",
        )
        self.caption.grid(row=0, column=0, sticky="w")

        self.count = ctk.CTkLabel(
            head, text="", font=theme.font(self, 10),
            text_color=theme.COLORS["text_muted"], anchor="e",
        )
        self.count.grid(row=0, column=1, sticky="e")

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent", corner_radius=0)
        self.scroll.grid(row=1, column=0, sticky="nsew")
        self.scroll.grid_columnconfigure(0, weight=1)

    # ------------------------------------------------------------ render
    def show(self, entry) -> None:
        self.entry = entry
        self._load_token += 1
        for widget in self.scroll.winfo_children():
            widget.destroy()
        self._refs.clear()
        self._labels.clear()

        if entry is None:
            self.caption.configure(text="Cast")
            self.count.configure(text="")
            return

        people = entry.cast or []
        self.caption.configure(text=f"Cast — {entry.model.get('title') or entry.path.name}")
        included = sum(1 for p in people if p.include)
        self.count.configure(text=f"{included} of {len(people)} written")

        if not people:
            ctk.CTkLabel(
                self.scroll,
                text="No cast yet. Scrape this item to pull the full billing order.",
                font=theme.font(self, 11), text_color=theme.COLORS["text_muted"],
                anchor="w",
            ).grid(row=0, column=0, sticky="w", padx=8, pady=12)
            return

        for idx, person in enumerate(people[:VISIBLE_LIMIT]):
            self._row(idx, person)

        if len(people) > VISIBLE_LIMIT:
            ctk.CTkLabel(
                self.scroll,
                text=f"+ {len(people) - VISIBLE_LIMIT} more (first {VISIBLE_LIMIT} are written)",
                font=theme.font(self, 10), text_color=theme.COLORS["text_muted"], anchor="w",
            ).grid(row=VISIBLE_LIMIT, column=0, sticky="w", padx=8, pady=(4, 12))

        self._load_images(entry, people[:VISIBLE_LIMIT])

    def _row(self, idx: int, person) -> None:
        row = ctk.CTkFrame(self.scroll, fg_color="transparent")
        row.grid(row=idx, column=0, sticky="ew", pady=2)
        row.grid_columnconfigure(2, weight=1)
        row.grid_columnconfigure(3, weight=1)

        include_var = ctk.BooleanVar(value=person.include)
        ctk.CTkCheckBox(
            row, text="", variable=include_var, width=24,
            checkbox_width=18, checkbox_height=18,
            fg_color=theme.COLORS["accent"], hover_color=theme.COLORS["accent_hover"],
            command=lambda p=person, v=include_var: self._toggle(p, v),
        ).grid(row=0, column=0, padx=(4, 6))

        thumb = ctk.CTkLabel(
            row, text="", width=36, height=54,
            fg_color=theme.COLORS["surface_alt"], corner_radius=4,
        )
        thumb.grid(row=0, column=1, padx=(0, 8))
        self._labels[id(person)] = thumb

        name_var = ctk.StringVar(value=person.name)
        ctk.CTkEntry(
            row, textvariable=name_var, height=28, width=150,
            corner_radius=theme.RADIUS_SM, fg_color=theme.COLORS["surface_alt"],
            border_color=theme.COLORS["border"], text_color=theme.COLORS["text"],
            font=theme.font(self, 11),
        ).grid(row=0, column=2, sticky="ew", padx=(0, 6))
        name_var.trace_add("write", lambda *_, p=person, v=name_var: self._set(p, "name", v.get()))

        role_var = ctk.StringVar(value=person.role)
        ctk.CTkEntry(
            row, textvariable=role_var, height=28,
            corner_radius=theme.RADIUS_SM, fg_color=theme.COLORS["surface_alt"],
            border_color=theme.COLORS["border"], text_color=theme.COLORS["text"],
            font=theme.font(self, 11),
        ).grid(row=0, column=3, sticky="ew", padx=(0, 6))
        role_var.trace_add("write", lambda *_, p=person, v=role_var: self._set(p, "role", v.get()))

        ctk.CTkButton(
            row, text="↑", width=26, height=26, corner_radius=4,
            fg_color="transparent", hover_color=theme.COLORS["card_hover"],
            text_color=theme.COLORS["text_muted"], font=theme.font(self, 11),
            command=lambda i=idx: self._move(i, -1),
        ).grid(row=0, column=4)

        ctk.CTkButton(
            row, text="↓", width=26, height=26, corner_radius=4,
            fg_color="transparent", hover_color=theme.COLORS["card_hover"],
            text_color=theme.COLORS["text_muted"], font=theme.font(self, 11),
            command=lambda i=idx: self._move(i, 1),
        ).grid(row=0, column=5)

        ctk.CTkButton(
            row, text="✕", width=26, height=26, corner_radius=4,
            fg_color="transparent", hover_color=theme.COLORS["card_hover"],
            text_color=theme.COLORS["danger"], font=theme.font(self, 11),
            command=lambda i=idx: self._remove(i),
        ).grid(row=0, column=6, padx=(0, 4))

    # ------------------------------------------------------------ edits
    def _set(self, person, attr: str, value: str) -> None:
        if self.entry is None:
            return
        if getattr(person, attr) != value:
            setattr(person, attr, value)
            self._changed()

    def _toggle(self, person, var) -> None:
        person.include = bool(var.get())
        if self.entry is not None:
            included = sum(1 for p in self.entry.cast if p.include)
            self.count.configure(text=f"{included} of {len(self.entry.cast)} written")
            self._changed()

    def _move(self, index: int, delta: int) -> None:
        if self.entry is None:
            return
        people = self.entry.cast
        target = index + delta
        if target < 0 or target >= len(people):
            return
        people[index], people[target] = people[target], people[index]
        for order, person in enumerate(people):
            person.order = order
        self._changed()
        self.show(self.entry)

    def _remove(self, index: int) -> None:
        if self.entry is None:
            return
        del self.entry.cast[index]
        for order, person in enumerate(self.entry.cast):
            person.order = order
        self._changed()
        self.show(self.entry)

    def _changed(self) -> None:
        if self.entry is not None:
            self.entry.touch()
        if self.on_change:
            self.on_change()

    # ------------------------------------------------------------ images
    def _load_images(self, entry, people) -> None:
        token = self._load_token

        def work() -> None:
            for person in people:
                if not person.profile_path:
                    continue
                path = imgs.cached(person.thumb_url(), "w185")
                if path and token == self._load_token:
                    self.app.post(lambda p=path, person=person: self._apply_thumb(person, p))

        threading.Thread(target=work, daemon=True).start()

    def _apply_thumb(self, person, path) -> None:
        label = self._labels.get(id(person))
        if label is None:
            return
        image = ctk_image(path, (36, 54))
        if image is not None:
            self._refs.append(image)
            label.configure(image=image, text="")
