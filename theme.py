"""WinUI 3 inspired design tokens for MediaMeta.

Every colour, radius and type size lives here so the whole app can be
retuned from one place, much like a WinUI resource dictionary.
"""

from __future__ import annotations

import tkinter.font as tkfont
import tkinter.ttk as ttk

# ---------------------------------------------------------------- colours
# CustomTkinter accepts (light, dark) tuples and swaps them automatically.
COLORS = {
    "bg":           ("#F3F3F3", "#202020"),
    "surface":      ("#FFFFFF", "#2B2B2B"),
    "surface_alt":  ("#FAFAFA", "#272727"),
    "card":         ("#FFFFFF", "#2D2D2D"),
    "card_hover":   ("#F5F5F5", "#333333"),
    "border":       ("#E5E5E5", "#3A3A3A"),
    "accent":       ("#0067C0", "#4CC2FF"),
    "accent_hover": ("#005BA1", "#3AB0F0"),
    "accent_text":  ("#FFFFFF", "#0A0A0A"),
    "text":         ("#1A1A1A", "#FFFFFF"),
    "text_muted":   ("#5C5C5C", "#9A9A9A"),
    "danger":       ("#C42B1C", "#FF99A4"),
    "success":      ("#0F7B0F", "#6CCB5F"),
    "warn":         ("#9D5D00", "#FCE100"),
    "rail":         ("#EBEBEB", "#1A1A1A"),
    "rail_active":  ("#D6E7F7", "#2D3D4D"),
}

RADIUS = 8
RADIUS_SM = 6
PAD = 12
PAD_SM = 6

FONT_FAMILY = "Segoe UI Variable Text"
FONT_DISPLAY = "Segoe UI Variable Display"
FONT_MONO = "Cascadia Mono"


def _pick_family(root, preferred: str, fallback: str) -> str:
    """Use the WinUI font when available, otherwise fall back gracefully."""
    try:
        families = set(tkfont.families(root))
    except Exception:
        return fallback
    return preferred if preferred in families else fallback


def family(root, display: bool = False) -> str:
    return _pick_family(root, FONT_DISPLAY if display else FONT_FAMILY, "Segoe UI")


def font(root, size: int = 13, weight: str = "normal", display: bool = False):
    import customtkinter as ctk

    return ctk.CTkFont(family=family(root, display), size=size, weight=weight)


def apply_appearance(mode: str = "dark") -> None:
    import customtkinter as ctk

    ctk.set_appearance_mode(mode)
    ctk.set_default_color_theme("blue")


def resolve(color) -> str:
    """Turn a (light, dark) token into the concrete colour for the current mode."""
    import customtkinter as ctk

    if isinstance(color, tuple):
        dark = ctk.get_appearance_mode().lower() == "dark"
        return color[1] if dark else color[0]
    return color


# ---------------------------------------------------------------- treeview
TREE_DARK = {
    "bg": "#272727",
    "fg": "#FFFFFF",
    "field": "#272727",
    "head_bg": "#2D2D2D",
    "head_fg": "#9A9A9A",
    "sel": "#2D3D4D",
    "border": "#3A3A3A",
}
TREE_LIGHT = {
    "bg": "#FFFFFF",
    "fg": "#1A1A1A",
    "field": "#FFFFFF",
    "head_bg": "#F3F3F3",
    "head_fg": "#5C5C5C",
    "sel": "#D6E7F7",
    "border": "#E5E5E5",
}


def style_treeview(root, mode: str = "dark") -> None:
    """Make ttk.Treeview look like a WinUI list view."""
    c = TREE_DARK if mode == "dark" else TREE_LIGHT
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        pass
    style.configure(
        "Media.Treeview",
        background=c["bg"],
        fieldbackground=c["field"],
        foreground=c["fg"],
        bordercolor=c["border"],
        borderwidth=0,
        rowheight=30,
        font=(family(root), 11),
    )
    style.configure(
        "Media.Treeview.Heading",
        background=c["head_bg"],
        foreground=c["head_fg"],
        relief="flat",
        borderwidth=0,
        padding=(8, 6),
        font=(family(root), 10, "bold"),
    )
    style.map(
        "Media.Treeview",
        background=[("selected", c["sel"])],
        foreground=[("selected", c["fg"])],
    )
    style.map("Media.Treeview.Heading", background=[("active", c["head_bg"])])
    style.layout("Media.Treeview", [("Media.Treeview.treearea", {"sticky": "nswe"})])


def status_color(status: str):
    s = (status or "").lower()
    if s.startswith(("ready", "done", "written", "ok")):
        return COLORS["success"]
    if s.startswith(("need", "review", "warn", "skip")):
        return COLORS["warn"]
    if s.startswith(("error", "fail")):
        return COLORS["danger"]
    return COLORS["text_muted"]
