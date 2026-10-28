"""Jellyfin / Emby compatible NFO writers.

Builders take the flat model from `edit.py`, so the GUI editor and the scraper
produce byte-identical output.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

import store
from edit import CastMember
from tmdb import image_url


def _sub(parent: ET.Element, tag: str, value) -> ET.Element | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    el = ET.SubElement(parent, tag)
    el.text = text
    return el


def _many(parent: ET.Element, tag: str, values) -> None:
    for value in values or []:
        _sub(parent, tag, value)


def _ratings(parent: ET.Element, rating, votes, source: str = "tmdb") -> None:
    try:
        value = round(float(rating), 1)
    except (TypeError, ValueError):
        return
    if not value:
        return
    holder = ET.SubElement(parent, "ratings")
    entry = ET.SubElement(holder, "rating", {"name": source, "max": "10", "default": "true"})
    _sub(entry, "value", value)
    _sub(entry, "votes", votes)


def _unique_ids(parent: ET.Element, tmdb_id=None, imdb_id: str = "", tvdb_id=None) -> None:
    if tmdb_id:
        el = ET.SubElement(parent, "uniqueid", {"type": "tmdb", "default": "true"})
        el.text = str(tmdb_id)
        _sub(parent, "tmdbid", tmdb_id)
    if imdb_id:
        el = ET.SubElement(parent, "uniqueid", {"type": "imdb"})
        el.text = imdb_id
        _sub(parent, "imdbid", imdb_id)
    if tvdb_id:
        el = ET.SubElement(parent, "uniqueid", {"type": "tvdb"})
        el.text = str(tvdb_id)
        _sub(parent, "tvdbid", tvdb_id)


def _actors(parent: ET.Element, cast: list[CastMember], embed_urls: bool = True) -> None:
    for person in cast or []:
        if not person.include or not person.name:
            continue
        actor = ET.SubElement(parent, "actor")
        _sub(actor, "name", person.name)
        _sub(actor, "role", person.role)
        _sub(actor, "order", person.order)
        if embed_urls and person.profile_path:
            _sub(actor, "thumb", image_url(person.profile_path, "w185"))


def sort_title(title: str) -> str:
    return re.sub(r"^(the|a|an)\s+", "", title or "", flags=re.I)


# ---------------------------------------------------------------- movie
def movie_nfo(model: dict, cast: list[CastMember], embed_urls: bool = True) -> ET.Element:
    root = ET.Element("movie")
    title = model.get("title") or ""
    _sub(root, "title", title)
    _sub(root, "originaltitle", model.get("original_title"))
    _sub(root, "sorttitle", sort_title(title))
    _sub(root, "year", model.get("year"))
    _sub(root, "premiered", model.get("premiered"))
    _sub(root, "plot", model.get("overview"))
    _sub(root, "tagline", model.get("tagline"))
    _sub(root, "runtime", model.get("runtime"))
    _sub(root, "mpaa", model.get("certification"))
    _sub(root, "rating", model.get("rating"))
    _ratings(root, model.get("rating"), model.get("votes"))

    _many(root, "genre", model.get("genres"))
    _many(root, "country", model.get("countries"))
    _many(root, "studio", model.get("studios"))
    _many(root, "director", model.get("directors"))
    _many(root, "writer", model.get("writers"))

    if model.get("collection"):
        set_el = ET.SubElement(root, "set")
        _sub(set_el, "name", model["collection"])

    _sub(root, "trailer", model.get("trailer"))
    _actors(root, cast, embed_urls)
    _unique_ids(root, model.get("tmdb_id"), model.get("imdb_id") or "")
    return root


# ---------------------------------------------------------------- tv show
def show_nfo(model: dict, cast: list[CastMember], embed_urls: bool = True) -> ET.Element:
    root = ET.Element("tvshow")
    title = model.get("title") or ""
    _sub(root, "title", title)
    _sub(root, "originaltitle", model.get("original_title"))
    _sub(root, "showtitle", title)
    _sub(root, "sorttitle", sort_title(title))
    _sub(root, "year", model.get("year"))
    _sub(root, "premiered", model.get("premiered"))
    _sub(root, "plot", model.get("overview"))
    _sub(root, "tagline", model.get("tagline"))
    _sub(root, "mpaa", model.get("certification"))
    _sub(root, "rating", model.get("rating"))
    _ratings(root, model.get("rating"), model.get("votes"))
    _sub(root, "runtime", model.get("runtime"))
    _sub(root, "status", model.get("status"))
    _sub(root, "network", model.get("network"))
    _many(root, "genre", model.get("genres"))
    _many(root, "studio", model.get("studios"))
    _many(root, "country", model.get("countries"))
    _sub(root, "trailer", model.get("trailer"))
    _actors(root, cast, embed_urls)
    _unique_ids(root, model.get("tmdb_id"), model.get("imdb_id") or "", model.get("tvdb_id"))
    return root


# ---------------------------------------------------------------- season
def season_nfo(season_number: int, model: dict) -> ET.Element:
    root = ET.Element("season")
    _sub(root, "title", model.get("title") or f"Season {season_number}")
    _sub(root, "seasonnumber", season_number)
    _sub(root, "plot", model.get("overview"))
    _sub(root, "premiered", model.get("premiered"))
    _sub(root, "year", model.get("year"))
    return root


# ---------------------------------------------------------------- episode
def episode_nfo(model: dict, cast: list[CastMember], embed_urls: bool = True) -> ET.Element:
    root = ET.Element("episodedetails")
    _sub(root, "title", model.get("title"))
    _sub(root, "showtitle", model.get("show_title"))
    _sub(root, "season", model.get("season"))
    _sub(root, "episode", model.get("episode"))
    _sub(root, "plot", model.get("overview"))
    _sub(root, "aired", model.get("premiered"))
    _sub(root, "runtime", model.get("runtime"))
    _sub(root, "rating", model.get("rating"))
    _ratings(root, model.get("rating"), model.get("votes"))
    _many(root, "director", model.get("directors"))
    _many(root, "writer", model.get("writers"))

    if model.get("thumb"):
        _sub(root, "thumb", image_url(model["thumb"], "w780"))

    _actors(root, cast, embed_urls)
    if model.get("tmdb_id"):
        _unique_ids(root, model["tmdb_id"])
    return root


# ---------------------------------------------------------------- writing
def write_xml(root: ET.Element, path: Path, manifest: store.Manifest | None = None) -> bool:
    """Write an NFO atomically, backing up any previous version."""
    path.parent.mkdir(parents=True, exist_ok=True)
    existed = path.exists()
    backup = store.backup(path) if existed else None

    ET.indent(root, space="  ")
    body = ET.tostring(root, encoding="utf-8", xml_declaration=False)
    payload = b'<?xml version="1.0" encoding="utf-8" standalone="yes"?>\n' + body

    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(payload)
    tmp.replace(path)

    if manifest is not None:
        manifest.record(path, "modified" if existed else "created", backup)
    return True


def to_string(root: ET.Element) -> str:
    ET.indent(root, space="  ")
    body = ET.tostring(root, encoding="unicode")
    return '<?xml version="1.0" encoding="utf-8" standalone="yes"?>\n' + body


def nfo_path_for_video(video: Path) -> Path:
    return video.with_suffix(".nfo")


def tvshow_path(show_root: Path) -> Path:
    return show_root / "tvshow.nfo"


def season_path(season_dir: Path) -> Path:
    return season_dir / "season.nfo"
