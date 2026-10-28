"""Library view: tree on the left, metadata editor on the right."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk

import edit
import library
import nfo_reader
import pipeline
import rename
import scanner
import store
import theme
from views.editor import EditorPane
from views.tree import TreePane


class CommitDialog(ctk.CTkToplevel):
    def __init__(self, master, summary: str, renames: int):
        super().__init__(master)
        self.result = False
        self.dont_ask = ctk.BooleanVar(value=False)
        self.title("Save changes")
        self.geometry("600x480")
        self.minsize(520, 400)
        self.configure(fg_color=theme.COLORS["bg"])
        self.transient(master.winfo_toplevel())
        self.grab_set()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        head = ctk.CTkFrame(self, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=18, pady=(16, 6))
        ctk.CTkLabel(
            head, text="Write these changes?", font=theme.font(self, 18, "bold", display=True),
            text_color=theme.COLORS["text"], anchor="w",
        ).pack(anchor="w")
        ctk.CTkLabel(
            head,
            text="NFO files and artwork will be written. "
                 + (f"{renames} file/folder rename(s) will be applied." if renames else "No renames are planned."),
            font=theme.font(self, 11), text_color=theme.COLORS["text_muted"], anchor="w",
            justify="left",
        ).pack(anchor="w", pady=(2, 0))

        self.box = ctk.CTkTextbox(
            self, fg_color=theme.COLORS["surface"], text_color=theme.COLORS["text"],
            font=theme.font(self, 11), corner_radius=theme.RADIUS_SM, wrap="none",
        )
        self.box.grid(row=1, column=0, sticky="nsew", padx=18, pady=(6, 6))
        self.box.insert("1.0", summary)
        self.box.configure(state="disabled")

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 16))
        footer.grid_columnconfigure(0, weight=1)

        ctk.CTkCheckBox(
            footer, text="Don't ask again", variable=self.dont_ask,
            checkbox_width=18, checkbox_height=18,
            fg_color=theme.COLORS["accent"], hover_color=theme.COLORS["accent_hover"],
            text_color=theme.COLORS["text_muted"], font=theme.font(self, 10),
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            footer, text="Cancel", width=90, height=34, corner_radius=theme.RADIUS_SM,
            fg_color="transparent", hover_color=theme.COLORS["card_hover"],
            text_color=theme.COLORS["text_muted"], border_width=1,
            border_color=theme.COLORS["border"], font=theme.font(self, 11),
            command=self.destroy,
        ).grid(row=0, column=1, padx=(0, 8))

        ctk.CTkButton(
            footer, text="Write files", width=130, height=34, corner_radius=theme.RADIUS_SM,
            fg_color=theme.COLORS["accent"], hover_color=theme.COLORS["accent_hover"],
            text_color=theme.COLORS["accent_text"], font=theme.font(self, 12, "bold"),
            command=self._accept,
        ).grid(row=0, column=2)

        self.after(120, self.grab_set)

    def _accept(self) -> None:
        self.result = True
        self.destroy()


class LibraryView(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color=theme.COLORS["bg"], corner_radius=0)
        self.app = app

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # ---------------------------------------------------------- toolbar
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 6))
        bar.grid_columnconfigure(3, weight=1)

        self.scrape_btn = ctk.CTkButton(
            bar, text="Scrape selected", width=140, height=34,
            corner_radius=theme.RADIUS_SM, fg_color=theme.COLORS["accent"],
            hover_color=theme.COLORS["accent_hover"], text_color=theme.COLORS["accent_text"],
            font=theme.font(self, 12, "bold"), command=self.scrape_selected,
        )
        self.scrape_btn.grid(row=0, column=0, padx=(0, 8))

        self.save_btn = ctk.CTkButton(
            bar, text="Save Changes", width=140, height=34,
            corner_radius=theme.RADIUS_SM, fg_color=theme.COLORS["accent"],
            hover_color=theme.COLORS["accent_hover"], text_color=theme.COLORS["accent_text"],
            font=theme.font(self, 12, "bold"), command=self.save_changes,
        )
        self.save_btn.grid(row=0, column=1, padx=(0, 8))

        small = dict(
            height=34, corner_radius=theme.RADIUS_SM, fg_color="transparent",
            hover_color=theme.COLORS["card_hover"], text_color=theme.COLORS["text_muted"],
            font=theme.font(self, 11), border_width=1, border_color=theme.COLORS["border"],
        )
        ctk.CTkButton(bar, text="Revert last", width=100, command=self.revert, **small).grid(
            row=0, column=2
        )

        self.summary = ctk.CTkLabel(
            bar, text="", font=theme.font(self, 11),
            text_color=theme.COLORS["text_muted"], anchor="e",
        )
        self.summary.grid(row=0, column=3, sticky="e", padx=(12, 0))

        # ---------------------------------------------------------- panes
        bg = theme.resolve(theme.COLORS["bg"])
        self.paned = tk.PanedWindow(
            self, orient="horizontal", sashwidth=5, bd=0, bg=bg,
            sashrelief="flat", showhandle=False,
        )
        self.paned.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 10))

        self.tree_pane = TreePane(self.paned, app, self.on_select)
        self.editor = EditorPane(self.paned, app)

        width = int(app.cfg.get("tree_width", 300) or 300)
        self.paned.add(self.tree_pane, minsize=220, width=width, stretch="never")
        self.paned.add(self.editor, minsize=520, stretch="always")
        self.paned.bind("<ButtonRelease-1>", self._save_width)

    # ------------------------------------------------------------ chrome
    def restyle(self) -> None:
        self.tree_pane.restyle()

    def set_busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        self.scrape_btn.configure(state=state)
        self.save_btn.configure(state=state)

    def reload_roots(self) -> None:
        self.tree_pane.reload_roots()
        self.update_summary()

    def _save_width(self, _event=None) -> None:
        try:
            self.app.cfg["tree_width"] = self.paned.sash_coord(0)[0]
            self.app.save_config()
        except Exception:
            pass

    def update_summary(self) -> None:
        staged = len(self.app.entries.staged())
        if staged:
            self.summary.configure(
                text=f"{staged} item(s) staged", text_color=theme.resolve(theme.COLORS["accent"])
            )
        else:
            self.summary.configure(text="", text_color=theme.COLORS["text_muted"])

    # ------------------------------------------------------------ selection
    def on_select(self, node: library.Node) -> None:
        entry = self.entry_for_node(node)
        self.editor.show(entry, node)

    def entry_for_node(self, node: library.Node | None):
        if node is None or node.kind in ("root", "folder"):
            return None

        existing = self.app.entries.get(node.path)
        if existing is not None:
            return existing

        entry = edit.MediaEntry(
            kind=node.kind, path=node.path, video=node.video,
            season=node.season, episode=node.episode,
        )

        parsed = self._read_nfo(node)
        if parsed:
            kind, model, cast = parsed
            entry.model = model
            entry.cast = cast
            entry.state = "saved"
            entry.status = "loaded from NFO"
            entry.origin = "nfo"
            entry.tmdb_id = model.get("tmdb_id") or None
        else:
            title, year, season, episode = scanner.parse_name(node.path.name)
            if node.kind == "episode":
                title = scanner.episode_title(node.path.name)
            entry.model["title"] = title
            entry.model["year"] = year
            if node.kind == "season":
                entry.model["season"] = node.season
            if node.kind == "episode":
                entry.model["season"] = node.season
                entry.model["episode"] = node.episode
            entry.state = "empty"
            entry.status = "not scraped"

        return self.app.entries.put(entry)

    def _read_nfo(self, node: library.Node):
        if node.kind == "movie":
            video = node.video or (node.path if node.path.is_file() else None)
            if video:
                parsed = nfo_reader.for_video(video)
                if parsed:
                    return parsed
            return nfo_reader.read(node.path / "movie.nfo")
        if node.kind == "show":
            return nfo_reader.for_show(node.path)
        if node.kind == "season":
            return nfo_reader.read(node.path / "season.nfo")
        if node.kind == "episode":
            return nfo_reader.for_video(node.path)
        return None

    # ------------------------------------------------------------ scraping
    def scrape_selected(self) -> None:
        self.scrape_nodes(self.tree_pane.selected_nodes())

    def _jobs_for(self, nodes: list[library.Node]) -> dict[int, dict]:
        jobs: dict[int, dict] = {}
        for node in nodes:
            if node is None:
                continue
            top = self.tree_pane.top_of(node)
            if top.kind not in ("movie", "show"):
                self.app.log(f"{node.label}: not a movie or show — skipped", "warn")
                continue
            job = jobs.setdefault(id(top), {"node": top, "seasons": set(), "all": False})
            if node.kind == "season" and node.season is not None:
                job["seasons"].add(node.season)
            elif node.kind == "episode" and node.season is not None:
                job["seasons"].add(node.season)
            else:
                job["all"] = True
        return jobs

    def scrape_nodes(self, nodes: list[library.Node]) -> None:
        if self.app.busy:
            return
        nodes = [n for n in nodes if n is not None]
        if not nodes:
            messagebox.showinfo("MediaMeta", "Select a movie, show, season or episode first.")
            return

        jobs = self._jobs_for(nodes)
        if not jobs:
            return

        client = self.app.client()
        if client is None:
            return

        cfg = dict(self.app.cfg)
        self.app.set_busy(True)
        self.app.log(f"staging {len(jobs)} item(s) — nothing is written yet", "info")
        self.app.progress(0, "Staging…")

        def work() -> None:
            total = len(jobs)
            for index, job in enumerate(jobs.values(), start=1):
                node = job["node"]
                entry = self.entry_for_node(node)
                if entry is None:
                    continue
                seasons = None if job["all"] or not job["seasons"] else set(job["seasons"])
                pipeline.stage(client, entry, self.app.entries, cfg, self.app.log, seasons)
                self.app.progress(index / total, f"{index}/{total} · {node.label}")

        def done(_result) -> None:
            self.app.set_busy(False)
            self.tree_pane.refresh()
            self.update_summary()
            first = next(iter(jobs.values()))["node"]
            entry = self.entry_for_node(first)
            self.editor.show(entry, first)
            self.app.progress(1, "Staged — review, then Save Changes")

        self.app.run_async(work, done)

    # ------------------------------------------------------------ commit
    def _top_entry(self, entry):
        if entry.kind in ("movie", "show"):
            return entry

        folder = entry.path.parent if entry.path.is_file() else entry.path
        if scanner.SEASON_DIR.match(folder.name) or scanner.SPECIALS_DIR.match(folder.name):
            folder = folder.parent

        existing = self.app.entries.get(folder)
        if existing is not None:
            return existing

        show = edit.MediaEntry(kind="show", path=folder)
        parsed = nfo_reader.for_show(folder)
        if parsed:
            _kind, model, cast = parsed
            show.model = model
            show.cast = cast
            show.state = "saved"
            show.status = "loaded from NFO"
        else:
            title, year, _, _ = scanner.parse_name(folder.name)
            show.model["title"] = title
            show.model["year"] = year
            show.state = "empty"
            show.status = "not scraped"
        return self.app.entries.put(show)

    def staged_tops(self) -> list:
        tops: dict[str, object] = {}
        for entry in self.app.entries.staged():
            top = self._top_entry(entry)
            tops[str(top.path).lower()] = top
        return list(tops.values())

    def _plan_for(self, top) -> list:
        cfg = self.app.cfg
        if top.kind == "movie":
            return rename.plan_movie(top, cfg)
        seasons = {
            e.season: e for e in self.app.entries.entries.values()
            if e.kind == "season" and e.path.parent == top.path
        }
        episodes = [
            e for e in self.app.entries.entries.values()
            if e.kind == "episode" and e.video and top.path in e.video.parents
        ]
        return rename.plan_show(top, seasons, episodes, cfg)

    def _summary_text(self, tops: list) -> tuple[str, int]:
        lines: list[str] = []
        total_renames = 0
        for top in tops:
            title = top.model.get("title") or top.path.name
            try:
                plan = self._plan_for(top)
            except Exception:
                plan = []
            renames = [r for r in plan if r.src != r.dst]
            total_renames += len(renames)

            if top.kind == "movie":
                lines.append(f"{title} — movie · {len(renames)} rename(s)")
            else:
                episodes = [
                    e for e in self.app.entries.entries.values()
                    if e.kind == "episode" and e.video and top.path in e.video.parents
                ]
                lines.append(f"{title} — {len(episodes)} episodes · {len(renames)} rename(s)")

            for ren in renames[:200]:
                tag = "DIR " if ren.kind == "folder" else "FILE"
                lines.append(f"   {tag}  {ren.src.name}  →  {ren.dst.name}")
            lines.append("")

        if not total_renames:
            lines.append("No renames planned — only NFO files and artwork will be written.")
        return "\n".join(lines), total_renames

    def save_changes(self) -> None:
        if self.app.busy:
            return
        tops = self.staged_tops()
        if not tops:
            messagebox.showinfo(
                "MediaMeta", "Nothing is staged yet.\n\nScrape an item first, then Save Changes."
            )
            return

        summary, renames = self._summary_text(tops)
        if self.app.cfg.get("confirm_first_commit", True):
            dialog = CommitDialog(self, summary, renames)
            self.wait_window(dialog)
            if not dialog.result:
                return
            if dialog.dont_ask.get():
                self.app.cfg["confirm_first_commit"] = False
                self.app.save_config()

        manifest = store.Manifest()
        cfg = dict(self.app.cfg)
        self.app.set_busy(True)
        self.app.progress(0, "Saving…")
        self.app.log(f"committing {len(tops)} item(s)", "info")

        def work() -> None:
            pipeline.commit(tops, self.app.entries, cfg, manifest, self.app.log, self.app.progress)
            saved = manifest.save()
            if saved:
                self.app.log(f"manifest saved: {saved.name}", "info")

        def done(_result) -> None:
            self.app.set_busy(False)
            self.tree_pane.reload_roots()
            self.update_summary()
            if tops:
                node = self.tree_pane.reveal(tops[0].path)
                if node is not None:
                    entry = self.entry_for_node(node)
                    self.editor.show(entry, node)
            self.app.progress(1, "Saved")
            messagebox.showinfo(
                "MediaMeta",
                f"Wrote {len(tops)} item(s).\n\nUse “Revert last” to undo this run.",
            )

        self.app.run_async(work, done)

    # ------------------------------------------------------------ misc
    def fix_match(self, node: library.Node) -> None:
        from views.review import FixMatchDialog

        top = self.tree_pane.top_of(node)
        entry = self.entry_for_node(top)
        if entry is None:
            return

        def applied(_entry) -> None:
            self.scrape_nodes([top])

        FixMatchDialog(self, self.app, entry, on_applied=applied)

    def revert(self) -> None:
        if self.app.busy:
            return
        if not messagebox.askyesno(
            "MediaMeta",
            "Undo the most recent save?\n\nCreated files are deleted, overwritten NFOs are "
            "restored from .bak, and renames are reversed.",
        ):
            return

        def done(_result) -> None:
            self.tree_pane.reload_roots()
            self.update_summary()
            self.app.log("revert finished", "info")

        self.app.run_async(lambda: store.revert_last(self.app.log), done)
