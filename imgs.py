"""Thumbnail cache for the editor previews.

Downloads are cached under %LOCALAPPDATA%\\MediaMeta\\thumbs so switching
between items in the tree is instant after the first look.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import net
import store
from tmdb import image_url

THUMB_DIR = store.LOCAL_DIR / "thumbs"
USER_AGENT = "MediaMeta/1.0"


def _path_for(url: str) -> Path:
    key = hashlib.sha1(url.encode("utf-8")).hexdigest()[:24]
    return THUMB_DIR / f"{key}.img"


def cached(url: str, size: str = "w342") -> Path | None:
    """Return a local path for `url`, downloading it once."""
    if not url:
        return None
    full = url if url.startswith("http") else image_url(url, size)
    dest = _path_for(full)
    if dest.exists() and dest.stat().st_size > 512:
        return dest

    THUMB_DIR.mkdir(parents=True, exist_ok=True)
    try:
        status, data, headers = net.fetch(
            full, {"User-Agent": USER_AGENT, "Accept": "image/*"}, timeout=30
        )
    except net.NetError:
        return None
    if status != 200 or len(data) < 512:
        return None
    if "image" not in (headers.get("content-type") or "").lower():
        return None

    tmp = dest.with_name(dest.name + ".part")
    tmp.write_bytes(data)
    tmp.replace(dest)
    return dest
