"""Manual match dialog — override a wrong (or missing) TMDB match."""

from __future__ import annotations

from tkinter import ttk

import customtkinter as ctk

import scanner
import theme


class FixMatchDialog(ctk.CTkToplevel):
    def __init__(self, master, app, entry, on_applied=None):
        super().__init__(master)
        self.app = app
        self.entry = entry
        self.on_applied = on_applied
        self.results: list[dict] = []

        title, year, _, _ = scanner.parse_name(entry.path.name)
        hint = entry.model.get("title") or title or entry.path.name
        self.title(f"Fix match — {hint}")
        self.geometry("780x560")
        self.minsize(680, 480)
        self.configure(fg_color=theme.COLORS["bg"])
        self.transient(master.winfo_toplevel())
        self.grab_set()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        head = ctk.CTkFrame(self, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=18, pady=(16, 4))
        head.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            head,
            text="Fix match",
            font=theme.font(self, 20, "bold", display=True),
            text_color=theme.COLORS["text"],
            anchor="w",
        ).grid(row=0, column=0, sticky="w")
        kind = "Movie" if entry.kind == "movie" else "TV show"
        ctk.CTkLabel(
            head,
            text=f"{kind} · {entry.path.name} · guess: {hint} ({entry.model.get('year') or '?'})",
            font=theme.font(self, 11),
            text_color=theme.COLORS["text_muted"],
            anchor="w",
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))

        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=1, column=0, sticky="ew", padx=18, pady=(8, 6))
        bar.grid_columnconfigure(0, weight=1)

        self.query_var = ctk.StringVar(value=hint)
        field = ctk.CTkEntry(
            bar,
            textvariable=self.query_var,
            height=36,
            corner_radius=theme.RADIUS_SM,
            fg_color=theme.COLORS["surface"],
            border_color=theme.COLORS["border"],
            text_color=theme.COLORS["text"],
            font=theme.font(self, 12),
        )
        field.grid(row=0, column=0, sticky="ew")
        field.bind("<Return>", lambda _e: self.search())

        ctk.CTkButton(
            bar, text="Search", width=90, height=36, corner_radius=theme.RADIUS_SM,
            fg_color=theme.COLORS["accent"], hover_color=theme.COLORS["accent_hover"],
            text_color=theme.COLORS["accent_text"], font=theme.font(self, 12, "bold"),
            command=self.search,
        ).grid(row=0, column=1, padx=(8, 0))

        wrap = ctk.CTkFrame(
            self, fg_color=theme.COLORS["surface"], corner_radius=theme.RADIUS,
            border_width=1, border_color=theme.COLORS["border"],
        )
        wrap.grid(row=2, column=0, sticky="nsew", padx=18, pady=(0, 6))
        wrap.grid_rowconfigure(0, weight=1)
        wrap.grid_columnconfigure(0, weight=1)

        self.tree = ttk.Treeview(
            wrap, columns=("title", "year", "id", "overview"),
            show="headings", style="Media.Treeview", selectmode="browse",
        )
        for col, text, width in (
            ("title", "Title", 260),
            ("year", "Year", 60),
            ("id", "TMDB ID", 80),
            ("overview", "Overview", 320),
        ):
            self.tree.heading(col, text=text, anchor="w")
            self.tree.column(col, width=width, anchor="w", stretch=(col == "overview"))
        self.tree.grid(row=0, column=0, sticky="nsew", padx=(8, 0), pady=8)
        scroll = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        scroll.grid(row=0, column=1, sticky="ns", padx=(0, 4), pady=8)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.bind("<Double-1>", lambda _e: self.apply())

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=3, column=0, sticky="ew", padx=18, pady=(0, 16))
        footer.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            footer, text="…or paste a TMDB ID:",
            font=theme.font(self, 11), text_color=theme.COLORS["text_muted"],
        ).grid(row=0, column=0, sticky="w")

        self.manual_var = ctk.StringVar()
        ctk.CTkEntry(
            footer, textvariable=self.manual_var, width=110, height=32,
            corner_radius=theme.RADIUS_SM, fg_color=theme.COLORS["surface"],
            border_color=theme.COLORS["border"], text_color=theme.COLORS["text"],
            font=theme.font(self, 11),
        ).grid(row=0, column=1, sticky="w", padx=(8, 0))

        self.status = ctk.CTkLabel(
            footer, text="", font=theme.font(self, 10),
            text_color=theme.COLORS["text_muted"], anchor="w",
        )
        self.status.grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))

        ctk.CTkButton(
            footer, text="Cancel", width=90, height=34, corner_radius=theme.RADIUS_SM,
            fg_color="transparent", hover_color=theme.COLORS["card_hover"],
            text_color=theme.COLORS["text_muted"], border_width=1,
            border_color=theme.COLORS["border"], font=theme.font(self, 11),
            command=self.destroy,
        ).grid(row=0, column=2, padx=(0, 8))

        ctk.CTkButton(
            footer, text="Use this match", width=140, height=34, corner_radius=theme.RADIUS_SM,
            fg_color=theme.COLORS["accent"], hover_color=theme.COLORS["accent_hover"],
            text_color=theme.COLORS["accent_text"], font=theme.font(self, 12, "bold"),
            command=self.apply,
        ).grid(row=0, column=3)

        self.after(150, lambda: field.focus_set())
        self.after(300, self.search)

    # ------------------------------------------------------------ actions
    def search(self) -> None:
        client = self.app.client()
        if client is None:
            return
        query = self.query_var.get().strip()
        if not query:
            return
        self.status.configure(text="Searching…", text_color=theme.resolve(theme.COLORS["text_muted"]))
        kind = self.entry.kind

        def work():
            return client.search_movie(query) if kind == "movie" else client.search_tv(query)

        def done(results) -> None:
            self.results = results or []
            self.tree.delete(*self.tree.get_children())
            for idx, result in enumerate(self.results[:40]):
                date = result.get("release_date") or result.get("first_air_date") or ""
                self.tree.insert(
                    "",
                    "end",
                    iid=str(idx),
                    values=(
                        result.get("title") or result.get("name") or "",
                        date[:4],
                        result.get("id"),
                        (result.get("overview") or "")[:160],
                    ),
                )
            self.status.configure(
                text=f"{len(self.results)} result(s)" if self.results else "No results.",
                text_color=theme.resolve(
                    theme.COLORS["text_muted"] if self.results else theme.COLORS["warn"]
                ),
            )

        self.app.run_async(work, done)

    def apply(self) -> None:
        manual = self.manual_var.get().strip()
        selection = self.tree.selection()

        if manual.isdigit():
            self.entry.tmdb_id = int(manual)
            self.entry.model["tmdb_id"] = int(manual)
            self.entry.confidence = 100
            self.entry.status = "manual match"
        elif selection:
            result = self.results[int(selection[0])]
            title = result.get("title") or result.get("name") or ""
            date = result.get("release_date") or result.get("first_air_date") or ""
            year = int(date[:4]) if len(date) >= 4 else None
            self.entry.tmdb_id = int(result["id"])
            self.entry.model["tmdb_id"] = int(result["id"])
            self.entry.model["title"] = title or self.entry.model.get("title") or ""
            self.entry.model["year"] = year or self.entry.model.get("year")
            self.entry.confidence = 100
            self.entry.status = "manual match"
        else:
            self.status.configure(
                text="Pick a result or paste a TMDB ID.",
                text_color=theme.resolve(theme.COLORS["danger"]),
            )
            return

        self.app.log(f"manual match: {self.entry.path.name} -> #{self.entry.tmdb_id}", "info")
        self.destroy()
        if self.on_applied:
            self.on_applied(self.entry)
