"""Left pane: the saved library roots as a lazy folder tree."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

import customtkinter as ctk

import library
import theme

BADGES = {
    "staged": "●",
    "dirty": "✎",
    "saved": "✓",
    "review": "⚠",
    "error": "!",
    "empty": "",
}


class TreePane(ctk.CTkFrame):
    def __init__(self, master, app, on_select):
        super().__init__(master, fg_color=theme.COLORS["surface"], corner_radius=0)
        self.app = app
        self.on_select = on_select
        self.roots: list[library.Node] = []
        self.nodes: dict[str, library.Node] = {}
        self.iids: dict[int, str] = {}
        self._counter = 0
        self._filtering = False

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        head = ctk.CTkFrame(self, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 6))
        head.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            head, text="Library", font=theme.font(self, 13, "bold"),
            text_color=theme.COLORS["text"], anchor="w",
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            head, text="+ Root", width=64, height=26, corner_radius=theme.RADIUS_SM,
            fg_color="transparent", hover_color=theme.COLORS["card_hover"],
            text_color=theme.COLORS["text_muted"], border_width=1,
            border_color=theme.COLORS["border"], font=theme.font(self, 10),
            command=self.add_root,
        ).grid(row=0, column=1)

        self.filter_var = ctk.StringVar()
        self.filter_entry = ctk.CTkEntry(
            self, textvariable=self.filter_var,
            placeholder_text="Filter loaded folders…", height=30,
            corner_radius=theme.RADIUS_SM, fg_color=theme.COLORS["surface_alt"],
            border_color=theme.COLORS["border"], text_color=theme.COLORS["text"],
            font=theme.font(self, 11),
        )
        self.filter_entry.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 6))
        self.filter_var.trace_add("write", lambda *_: self._apply_filter())

        wrap = ctk.CTkFrame(self, fg_color="transparent")
        wrap.grid(row=2, column=0, sticky="nsew")
        wrap.grid_rowconfigure(0, weight=1)
        wrap.grid_columnconfigure(0, weight=1)

        self.tree = ttk.Treeview(wrap, show="tree", style="Media.Treeview", selectmode="extended")
        self.tree.grid(row=0, column=0, sticky="nsew", padx=(6, 0), pady=4)
        scroll = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        scroll.grid(row=0, column=1, sticky="ns", padx=(0, 4), pady=4)
        self.tree.configure(yscrollcommand=scroll.set)

        self.tree.bind("<<TreeviewOpen>>", self._on_open)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Button-3>", self._on_right_click)
        self.tree.bind("<Double-1>", self._on_double)

        self.empty = ctk.CTkLabel(
            self,
            text="No library roots yet.\nAdd one in Settings, or press “+ Root”.",
            font=theme.font(self, 11), text_color=theme.COLORS["text_muted"],
            justify="left",
        )
        self.empty.grid(row=2, column=0, sticky="nsew", padx=16, pady=16)

        self._menu = tk.Menu(self, tearoff=0)
        self._menu.add_command(label="Scrape", command=self._menu_scrape)
        self._menu.add_command(label="Save changes", command=self._menu_save)
        self._menu.add_separator()
        self._menu.add_command(label="Fix match…", command=self._menu_fix)
        self._menu.add_command(label="Open folder", command=self._menu_open)
        self._menu.add_separator()
        self._menu.add_command(label="Delete…", command=self._menu_delete)

        self.restyle()
        self.reload_roots()

    # ------------------------------------------------------------ styling
    def restyle(self) -> None:
        theme.style_treeview(self, ctk.get_appearance_mode().lower())
        for tag, colour in (
            ("staged", theme.COLORS["accent"]),
            ("dirty", theme.COLORS["warn"]),
            ("saved", theme.COLORS["success"]),
            ("error", theme.COLORS["danger"]),
            ("folder", theme.COLORS["text_muted"]),
            ("normal", theme.COLORS["text"]),
        ):
            self.tree.tag_configure(tag, foreground=theme.resolve(colour))

    # ------------------------------------------------------------ tree
    def reload_roots(self) -> None:
        self.tree.delete(*self.tree.get_children())
        self.nodes.clear()
        self.iids.clear()
        paths = list(self.app.cfg.get("library_roots") or [])
        self.roots = library.build_roots(paths)

        for root in self.roots:
            self._insert("", root)

        self.empty.grid() if not self.roots else self.empty.grid_remove()

    def _new_iid(self) -> str:
        self._counter += 1
        return f"n{self._counter}"

    def _insert(self, parent_iid: str, node: library.Node) -> str:
        iid = self._new_iid()
        self.nodes[iid] = node
        self.iids[id(node)] = iid
        self.tree.insert(
            parent_iid, "end", iid=iid, text=self._label(node), tags=(self._tag(node),)
        )
        if node.kind not in ("movie", "episode"):
            self.tree.insert(iid, "end", iid=f"{iid}-d", text="…")
        return iid

    def _label(self, node: library.Node) -> str:
        entry = self.app.entries.get(node.path)
        badge = BADGES.get(entry.state, "") if entry else ""
        text = node.label
        if node.kind == "root":
            text = f"▣ {text}"
        elif node.kind == "show":
            text = f"▤ {text}"
        elif node.kind == "season":
            text = f"▸ {text}"
        elif node.kind == "movie":
            text = f"▶ {text}"
        elif node.kind == "episode":
            text = f"   {text}"
        return f"{text}  {badge}".rstrip()

    def _tag(self, node: library.Node) -> str:
        entry = self.app.entries.get(node.path)
        if entry and entry.state in BADGES:
            return entry.state
        return "normal" if node.kind not in ("root",) else "folder"

    def _expand(self, node: library.Node) -> None:
        iid = self.iids.get(id(node))
        if not iid or not self.tree.exists(iid):
            return
        for child in list(self.tree.get_children(iid)):
            self.tree.delete(child)
            self.nodes.pop(child, None)
        for child in library.children_of(node):
            self._insert(iid, child)

    def _on_open(self, _event=None) -> None:
        iid = self.tree.focus()
        node = self.nodes.get(iid)
        if node:
            self._expand(node)

    def _on_select(self, _event=None) -> None:
        selection = self.tree.selection()
        if len(selection) != 1:
            return
        node = self.nodes.get(selection[0])
        if node:
            self.on_select(node)

    def _on_double(self, event) -> None:
        iid = self.tree.identify_row(event.y)
        node = self.nodes.get(iid)
        if node and node.kind not in ("movie", "episode"):
            self._expand(node)
            self.tree.item(iid, open=True)

    # ------------------------------------------------------------ actions
    def add_root(self) -> None:
        from tkinter import filedialog

        chosen = filedialog.askdirectory(title="Add a library root")
        if not chosen:
            return
        roots = list(self.app.cfg.get("library_roots") or [])
        if chosen in roots:
            messagebox.showinfo("MediaMeta", "That folder is already a library root.")
            return
        roots.append(chosen)
        self.app.cfg["library_roots"] = roots
        self.app.save_config()
        self.reload_roots()
        self.app.views["settings"].refresh_roots()

    def selected_nodes(self) -> list[library.Node]:
        return [self.nodes[i] for i in self.tree.selection() if i in self.nodes]

    def top_of(self, node: library.Node) -> library.Node:
        """Nearest movie/show ancestor, skipping intermediate folders.

        A movie or show may live one or more folder levels below the root
        (e.g. Movies\Hindi\Dhurandhar (2025)\). Return the actual media node,
        not the genre folder.
        """
        result = node if node.kind in ("movie", "show") else None
        current = node
        while current.parent is not None and current.parent.kind != "root":
            current = current.parent
            if current.kind in ("movie", "show"):
                result = current
        return result or node

    def reveal(self, path: Path) -> library.Node | None:
        """Expand down to `path` after a reload and select it."""
        for root in self.roots:
            node = library.node_for_path(root, path)
            if node is None:
                continue
            chain: list[library.Node] = []
            current: library.Node | None = node
            while current is not None:
                chain.append(current)
                current = current.parent
            # expand top-down (root first) so each parent has an iid before its child
            for ancestor in reversed(chain[1:]):
                self._expand(ancestor)
            iid = self.iids.get(id(node))
            if iid and self.tree.exists(iid):
                self.tree.see(iid)
                self.tree.selection_set(iid)
                self.tree.focus(iid)
            return node
        return None

    def select_node(self, node: library.Node) -> None:
        iid = self.iids.get(id(node))
        if iid and self.tree.exists(iid):
            self.tree.selection_set(iid)
            self.tree.focus(iid)
            self.tree.see(iid)

    def refresh(self) -> None:
        for iid, node in list(self.nodes.items()):
            if self.tree.exists(iid):
                self.tree.item(iid, text=self._label(node), tags=(self._tag(node),))

    def _apply_filter(self) -> None:
        needle = self.filter_var.get().strip().lower()
        if not needle:
            if self._filtering:
                self._filtering = False
                self.reload_roots()
            return

        self._filtering = True
        self.tree.delete(*self.tree.get_children())
        self.nodes.clear()
        self.iids.clear()
        for node in self._loaded_nodes():
            if needle in node.label.lower():
                self._insert("", node)

    def _loaded_nodes(self):
        for root in self.roots:
            library.children_of(root)
            yield from root.walk()

    # ------------------------------------------------------------ context menu
    def _on_right_click(self, event) -> None:
        iid = self.tree.identify_row(event.y)
        if iid and iid in self.nodes:
            if iid not in self.tree.selection():
                self.tree.selection_set(iid)
            self._menu.tk_popup(event.x_root, event.y_root)

    def _menu_scrape(self) -> None:
        self.app.views["library"].scrape_nodes(self.selected_nodes())

    def _menu_save(self) -> None:
        self.app.views["library"].save_changes()

    def _menu_fix(self) -> None:
        nodes = self.selected_nodes()
        if not nodes:
            return
        self.app.views["library"].fix_match(nodes[0])

    def _menu_open(self) -> None:
        nodes = self.selected_nodes()
        if not nodes:
            return
        import os

        target = nodes[0].path
        if target.is_file():
            target = target.parent
        try:
            os.startfile(target)  # noqa: S606
        except Exception:
            pass

    def _menu_delete(self) -> None:
        """Remove the selected item from the tree view (no disk changes)."""
        nodes = self.selected_nodes()
        if len(nodes) != 1:
            messagebox.showinfo("MediaMeta", "Select one item to remove.")
            return
        node = nodes[0]
        if node.kind == "root":
            messagebox.showinfo("MediaMeta", "Cannot remove a library root.")
            return

        kind_label = {"movie": "movie", "show": "TV show", "season": "season",
                      "episode": "episode", "folder": "folder"}.get(node.kind, "item")

        if not messagebox.askyesno(
            "MediaMeta",
            f"Remove “{node.label}” from the library tree?\n\n"
            "Nothing on disk will be changed or deleted.",
            icon="warning",
        ):
            return

        # drop any staged entry for this path so it isn't committed later
        try:
            self.app.entries.remove(node.path)
        except Exception:
            pass

        # remove from the tree display
        iid = self.iids.get(id(node))
        if iid and self.tree.exists(iid):
            self.tree.delete(iid)
            self.nodes.pop(iid, None)
            self.iids.pop(id(node), None)

        self.refresh()
        self.app.log(f"removed from tree: {node.label}", "info")

        # clear the editor if it was showing the removed item
        try:
            editor = self.app.views["library"].editor
            if editor.node is node:
                editor.clear()
        except Exception:
            pass
