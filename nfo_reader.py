"""Read existing NFO files back into the editable model."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from edit import CastMember, empty_model


def _text(root: ET.Element, tag: str, default: str = "") -> str:
    el = root.find(tag)
    return (el.text or "").strip() if el is not None and el.text else default


def _int(root: ET.Element, tag: str) -> int | None:
    raw = _text(root, tag)
    try:
        return int(float(raw))
    except (TypeError, ValueError):
        return None


def _float(root: ET.Element, tag: str) -> float | None:
    raw = _text(root, tag)
    try:
        return round(float(raw), 1)
    except (TypeError, ValueError):
        return None


def _all(root: ET.Element, tag: str) -> list[str]:
    return [(el.text or "").strip() for el in root.findall(tag) if el.text]


def _cast(root: ET.Element) -> list[CastMember]:
    out: list[CastMember] = []
    for idx, actor in enumerate(root.findall("actor")):
        name = _text(actor, "name")
        if not name:
            continue
        thumb = _text(actor, "thumb")
        profile = ""
        if thumb and "/t/p/" in thumb:
            profile = "/" + thumb.split("/t/p/")[-1].split("/", 1)[-1]
        out.append(
            CastMember(
                name=name,
                role=_text(actor, "role"),
                order=_int(actor, "order") or idx,
                profile_path=profile,
            )
        )
    out.sort(key=lambda c: c.order)
    return out


def _unique(root: ET.Element, kind: str) -> str:
    for el in root.findall("uniqueid"):
        if (el.get("type") or "").lower() == kind and el.text:
            return el.text.strip()
    legacy = {"tmdb": "tmdbid", "imdb": "imdbid", "tvdb": "tvdbid"}.get(kind)
    return _text(root, legacy) if legacy else ""


def read(path: Path) -> tuple[str, dict, list[CastMember]] | None:
    """Return (kind, model, cast) for an existing NFO, or None."""
    if not path.exists():
        return None
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError):
        return None

    tag = root.tag.lower()
    if tag == "movie":
        model = empty_model("movie")
        model.update({
            "title": _text(root, "title"),
            "original_title": _text(root, "originaltitle"),
            "year": _int(root, "year"),
            "premiered": _text(root, "premiered"),
            "runtime": _int(root, "runtime"),
            "certification": _text(root, "mpaa"),
            "rating": _float(root, "rating"),
            "tagline": _text(root, "tagline"),
            "overview": _text(root, "plot"),
            "genres": _all(root, "genre"),
            "directors": _all(root, "director"),
            "writers": _all(root, "writer"),
            "studios": _all(root, "studio"),
            "countries": _all(root, "country"),
            "collection": _text(root, "set/name"),
            "trailer": _text(root, "trailer"),
            "tmdb_id": _int(root, "tmdbid") or _int(root, "uniqueid"),
            "imdb_id": _text(root, "imdbid") or _unique(root, "imdb"),
        })
        return "movie", model, _cast(root)

    if tag == "tvshow":
        model = empty_model("show")
        model.update({
            "title": _text(root, "title") or _text(root, "showtitle"),
            "original_title": _text(root, "originaltitle"),
            "year": _int(root, "year"),
            "premiered": _text(root, "premiered"),
            "runtime": _int(root, "runtime"),
            "certification": _text(root, "mpaa"),
            "rating": _float(root, "rating"),
            "tagline": _text(root, "tagline"),
            "overview": _text(root, "plot"),
            "genres": _all(root, "genre"),
            "studios": _all(root, "studio"),
            "countries": _all(root, "country"),
            "network": _text(root, "network"),
            "status": _text(root, "status"),
            "trailer": _text(root, "trailer"),
            "tmdb_id": _int(root, "tmdbid"),
            "imdb_id": _text(root, "imdbid"),
            "tvdb_id": _int(root, "tvdbid"),
        })
        return "show", model, _cast(root)

    if tag == "season":
        model = empty_model("season")
        model.update({
            "title": _text(root, "title"),
            "season": _int(root, "seasonnumber"),
            "overview": _text(root, "plot"),
            "premiered": _text(root, "premiered"),
            "year": _int(root, "year"),
        })
        return "season", model, []

    if tag == "episodedetails":
        model = empty_model("episode")
        model.update({
            "title": _text(root, "title"),
            "show_title": _text(root, "showtitle"),
            "season": _int(root, "season"),
            "episode": _int(root, "episode"),
            "premiered": _text(root, "aired"),
            "runtime": _int(root, "runtime"),
            "rating": _float(root, "rating"),
            "overview": _text(root, "plot"),
            "directors": _all(root, "director"),
            "writers": _all(root, "writer"),
            "thumb": _text(root, "thumb"),
            "tmdb_id": _int(root, "uniqueid"),
        })
        return "episode", model, _cast(root)

    return None


def for_video(video: Path):
    return read(video.with_suffix(".nfo"))


def for_show(show_root: Path):
    return read(show_root / "tvshow.nfo")
