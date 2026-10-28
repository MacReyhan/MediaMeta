"""Activity view: colourised, auto-scrolling log."""

from __future__ import annotations

import customtkinter as ctk

import store
import theme

LEVELS = {
    "info": theme.COLORS["text_muted"],
    "plan": theme.COLORS["accent"],
    "ok": theme.COLORS["success"],
    "warn": theme.COLORS["warn"],
    "error": theme.COLORS["danger"],
}


class LogView(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color=theme.COLORS["bg"], corner_radius=0)
        self.app = app
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        head = ctk.CTkFrame(self, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 8))
        head.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            head,
            text="Activity",
            font=theme.font(self, 24, "bold", display=True),
            text_color=theme.COLORS["text"],
            anchor="w",
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            head,
            text="Every API call, file write and skipped item lands here.",
            font=theme.font(self, 11),
            text_color=theme.COLORS["text_muted"],
            anchor="w",
        ).grid(row=1, column=0, sticky="w")

        tools = ctk.CTkFrame(self, fg_color="transparent")
        tools.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 6))

        small = dict(
            height=30, corner_radius=theme.RADIUS_SM,
            fg_color="transparent", hover_color=theme.COLORS["card_hover"],
            text_color=theme.COLORS["text_muted"], font=theme.font(self, 11),
            border_width=1, border_color=theme.COLORS["border"],
        )
        ctk.CTkButton(tools, text="Clear", width=80, command=self.clear, **small).pack(side="left")
        ctk.CTkButton(tools, text="Open log folder", width=130, command=self.open_logs, **small).pack(side="left", padx=(8, 0))

        self.box = ctk.CTkTextbox(
            self,
            fg_color=theme.COLORS["surface"],
            text_color=theme.COLORS["text"],
            border_width=1,
            border_color=theme.COLORS["border"],
            corner_radius=theme.RADIUS,
            font=theme.font(self, 11),
            wrap="word",
        )
        self.box.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 14))
        self.box.configure(state="disabled")

        for level, colour in LEVELS.items():
            self.box._textbox.tag_config(level, foreground=theme.resolve(colour))

    def append(self, level: str, message: str) -> None:
        tag = level if level in LEVELS else "info"
        self.box.configure(state="normal")
        self.box._textbox.insert("end", f"{message}\n", tag)
        # keep the buffer bounded
        if int(self.box._textbox.index("end-1c").split(".")[0]) > 4000:
            self.box._textbox.delete("1.0", "500.0")
        self.box.configure(state="disabled")
        self.box._textbox.see("end")

    def clear(self) -> None:
        self.box.configure(state="normal")
        self.box.delete("1.0", "end")
        self.box.configure(state="disabled")

    def open_logs(self) -> None:
        store.ensure_dirs()
        import os

        os.startfile(store.LOG_DIR)  # noqa: S606 - Windows-only helper
