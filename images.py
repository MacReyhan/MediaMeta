"""Artwork downloading, naming and optional post-processing."""

from __future__ import annotations

import re
from pathlib import Path

import net
import store
from tmdb import image_url

USER_AGENT = "MediaMeta/1.0"
MIN_BYTES = 512


def _safe(name: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", name or "").strip(" .")
    return cleaned or "unknown"


def download(url: str, dest: Path, overwrite: bool = False, timeout: int = 45) -> bool:
    """Fetch an image to `dest`. Returns True when the file is usable."""
    if not url:
        return False
    if dest.exists() and not overwrite and dest.stat().st_size > MIN_BYTES:
        return True

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    try:
        status, data, headers = net.fetch(
            url, {"User-Agent": USER_AGENT, "Accept": "image/*"}, timeout=timeout
        )
    except net.NetError:
        return False

    if status != 200:
        return False
    if "image" not in (headers.get("content-type") or "").lower():
        return False
    if len(data) < MIN_BYTES:
        return False
    tmp.write_bytes(data)
    tmp.replace(dest)
    return True


def save_image(
    url: str,
    dest: Path,
    manifest: store.Manifest | None,
    overwrite: bool = False,
) -> bool:
    existed = dest.exists()
    ok = download(url, dest, overwrite=overwrite)
    if ok and manifest is not None and not existed:
        manifest.record(dest, "created")
    return ok


# ---------------------------------------------------------------- naming
POSTER = "poster.jpg"
FANART = "fanart.jpg"
LOGO = "logo.png"
BANNER = "banner.jpg"


def season_poster_name(season: int) -> str:
    return f"season{season:02d}-poster.jpg"


def episode_thumb_name(video: Path) -> str:
    return f"{video.stem}-thumb.jpg"


def actor_dir(root: Path) -> Path:
    return root / ".actors"


# ---------------------------------------------------------------- banner
def make_banner(fanart: Path, dest: Path, size: tuple[int, int] = (758, 140)) -> bool:
    """Center-crop fanart into a Jellyfin banner. Requires Pillow; silent no-op."""
    if not fanart.exists() or dest.exists():
        return dest.exists()
    try:
        from PIL import Image  # type: ignore
    except ImportError:
        return False
    try:
        with Image.open(fanart) as img:
            img = img.convert("RGB")
            target_ratio = size[0] / size[1]
            w, h = img.size
            if w / h > target_ratio:
                new_w = int(h * target_ratio)
                left = (w - new_w) // 2
                img = img.crop((left, 0, left + new_w, h))
            else:
                new_h = int(w / target_ratio)
                top = (h - new_h) // 2
                img = img.crop((0, top, w, top + new_h))
            img = img.resize(size, Image.LANCZOS)
            dest.parent.mkdir(parents=True, exist_ok=True)
            img.save(dest, "JPEG", quality=90)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------- pickers
def best(images: dict, key: str, language: str = "en") -> dict | None:
    entries = [e for e in (images or {}).get(key) or [] if e.get("file_path")]
    if not entries:
        return None

    def rank(entry: dict) -> tuple:
        lang = entry.get("iso_639_1") or "null"
        if lang == language:
            lang_rank = 0
        elif lang in ("null", ""):
            lang_rank = 1
        elif lang == "en":
            lang_rank = 2
        else:
            lang_rank = 3
        area = (entry.get("width") or 0) * (entry.get("height") or 0)
        return (lang_rank, -(entry.get("vote_average") or 0), -area)

    return sorted(entries, key=rank)[0]


def url_for(entry: dict | None, size: str) -> str:
    return image_url(entry.get("file_path"), size) if entry else ""
