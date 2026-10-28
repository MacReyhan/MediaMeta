"""Small shared widget helpers."""

from __future__ import annotations

from pathlib import Path

import customtkinter as ctk

import theme


def ctk_image(path: Path | str | None, size: tuple[int, int]):
    """Load a PIL image into a CTkImage, or None when unreadable."""
    if not path:
        return None
    try:
        from PIL import Image

        with Image.open(path) as raw:
            image = raw.convert("RGB")
        return ctk.CTkImage(light_image=image, dark_image=image, size=size)
    except Exception:
        return None


def section_label(parent, text: str) -> ctk.CTkLabel:
    return ctk.CTkLabel(
        parent,
        text=text,
        font=theme.font(parent, 11, "bold"),
        text_color=theme.COLORS["text_muted"],
        anchor="w",
    )
