"""Editable metadata model shared by the scraper, the editor and the writers.

TMDB responses are normalised into a flat `model` dict so the UI can bind to it
directly, and so user overrides are just dict updates.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from pathlib import Path

import tmdb

MODEL_KEYS = (
    "title", "original_title", "year", "premiered", "runtime", "certification",
    "rating", "votes", "tagline", "overview", "genres", "directors", "writers",
    "studios", "countries", "collection", "trailer", "tmdb_id", "imdb_id",
    "tvdb_id", "network", "status", "show_title", "season", "episode", "thumb",
)


def _year(date: str | None) -> int | None:
    if date and len(date) >= 4 and date[:4].isdigit():
        return int(date[:4])
    return None


def _names(items, key: str = "name") -> list[str]:
    return [i.get(key) for i in items or [] if i.get(key)]


def _crew(crew: list[dict], jobs: tuple[str, ...]) -> list[str]:
    out: list[str] = []
    for member in crew or []:
        if member.get("job") in jobs and member.get("name") not in out:
            out.append(member["name"])
    return out


def empty_model(kind: str) -> dict:
    model = {key: "" for key in MODEL_KEYS}
    model.update({"genres": [], "directors": [], "writers": [], "studios": [],
                  "countries": [], "year": None, "runtime": None, "rating": None,
                  "votes": None, "tmdb_id": None, "tvdb_id": None})
    if kind in ("episode", "season"):
        model["season"] = None
        model["episode"] = None
    return model


def model_from_movie(data: dict) -> dict:
    model = empty_model("movie")
    credits = data.get("credits") or {}
    model.update({
        "title": data.get("title") or "",
        "original_title": data.get("original_title") or "",
        "year": _year(data.get("release_date")),
        "premiered": data.get("release_date") or "",
        "runtime": data.get("runtime"),
        "certification": tmdb.TMDB.certification(data),
        "rating": round(float(data.get("vote_average") or 0), 1) or None,
        "votes": data.get("vote_count"),
        "tagline": data.get("tagline") or "",
        "overview": data.get("overview") or "",
        "genres": _names(data.get("genres")),
        "directors": _crew(credits.get("crew"), ("Director",)),
        "writers": _crew(credits.get("crew"), ("Writer", "Screenplay", "Story")),
        "studios": _names(data.get("production_companies")),
        "countries": _names(data.get("production_countries")),
        "collection": (data.get("belongs_to_collection") or {}).get("name") or "",
        "trailer": tmdb.TMDB.trailer_url(data),
        "tmdb_id": data.get("id"),
        "imdb_id": (data.get("external_ids") or {}).get("imdb_id") or "",
    })
    return model


def model_from_show(data: dict) -> dict:
    model = empty_model("show")
    runtimes = data.get("episode_run_time") or []
    networks = data.get("networks") or []
    model.update({
        "title": data.get("name") or "",
        "original_title": data.get("original_name") or "",
        "year": _year(data.get("first_air_date")),
        "premiered": data.get("first_air_date") or "",
        "runtime": runtimes[0] if runtimes else None,
        "certification": tmdb.TMDB.tv_certification(data),
        "rating": round(float(data.get("vote_average") or 0), 1) or None,
        "votes": data.get("vote_count"),
        "tagline": data.get("tagline") or "",
        "overview": data.get("overview") or "",
        "genres": _names(data.get("genres")),
        "studios": _names(data.get("production_companies")),
        "countries": list(data.get("origin_country") or []),
        "trailer": tmdb.TMDB.trailer_url(data),
        "tmdb_id": data.get("id"),
        "imdb_id": (data.get("external_ids") or {}).get("imdb_id") or "",
        "tvdb_id": (data.get("external_ids") or {}).get("tvdb_id"),
        "network": networks[0].get("name") if networks else "",
        "status": data.get("status") or "",
    })
    return model


def model_from_episode(data: dict, show_title: str, season: int) -> dict:
    model = empty_model("episode")
    crew = data.get("crew") or []
    model.update({
        "title": data.get("name") or "",
        "show_title": show_title,
        "season": season,
        "episode": data.get("episode_number"),
        "premiered": data.get("air_date") or "",
        "year": _year(data.get("air_date")),
        "runtime": data.get("runtime"),
        "rating": round(float(data.get("vote_average") or 0), 1) or None,
        "votes": data.get("vote_count"),
        "overview": data.get("overview") or "",
        "directors": _crew(crew, ("Director",)),
        "writers": _crew(crew, ("Writer", "Screenplay", "Story")),
        "tmdb_id": data.get("id"),
        "thumb": data.get("still_path") or "",
    })
    return model


# ---------------------------------------------------------------- cast
@dataclass
class CastMember:
    name: str
    role: str = ""
    order: int = 0
    profile_path: str = ""
    include: bool = True

    def thumb_url(self) -> str:
        return tmdb.image_url(self.profile_path, "w185") if self.profile_path else ""


def cast_from_tmdb(cast: list[dict]) -> list[CastMember]:
    out: list[CastMember] = []
    for idx, person in enumerate(cast or []):
        if not person.get("name"):
            continue
        role = person.get("character") or ""
        roles = person.get("roles")
        if not role and roles:
            role = roles[0].get("character") or ""
        out.append(
            CastMember(
                name=person["name"],
                role=role,
                order=person.get("order", idx),
                profile_path=person.get("profile_path") or "",
            )
        )
    out.sort(key=lambda c: c.order)
    return out


# ---------------------------------------------------------------- entries
@dataclass
class MediaEntry:
    kind: str                      # movie | show | season | episode
    path: Path                     # folder (movie/show/season) or video file
    video: Path | None = None
    season: int | None = None
    episode: int | None = None
    data: dict = field(default_factory=dict)      # raw TMDB payload
    model: dict = field(default_factory=dict)     # flat editable metadata
    cast: list[CastMember] = field(default_factory=list)
    art: dict = field(default_factory=dict)       # key -> TMDB file_path override
    state: str = "empty"                          # empty|staged|saved|dirty|error
    status: str = ""
    confidence: int = 0
    tmdb_id: int | None = None
    origin: str = ""                              # tmdb | nfo
    error: str = ""

    def __post_init__(self) -> None:
        if not self.model:
            self.model = empty_model(self.kind)

    # -- convenience -------------------------------------------------
    def get(self, key: str, default=""):
        value = self.model.get(key, default)
        return default if value is None else value

    def set(self, key: str, value) -> None:
        if self.model.get(key) != value:
            self.model[key] = value
            self.touch()

    def touch(self) -> None:
        if self.state in ("saved", "staged", "review"):
            self.state = "dirty"
        self.status = "edited"

    @property
    def display_title(self) -> str:
        if self.kind == "episode":
            return f"S{self.season or 0:02d}E{self.episode or 0:02d} · {self.get('title')}"
        return self.get("title") or self.path.name

    @property
    def editable(self) -> bool:
        return self.state in ("staged", "saved", "dirty", "review")

    def clone_model(self) -> dict:
        return copy.deepcopy(self.model)


class EntryStore:
    """All metadata known for the current tree, keyed by path."""

    def __init__(self) -> None:
        self.entries: dict[str, MediaEntry] = {}

    def key(self, path: Path) -> str:
        return str(path).lower()

    def get(self, path: Path) -> MediaEntry | None:
        return self.entries.get(self.key(path))

    def ensure(self, kind: str, path: Path, **kwargs) -> MediaEntry:
        entry = self.get(path)
        if entry is None:
            entry = MediaEntry(kind=kind, path=path, **kwargs)
            self.entries[self.key(path)] = entry
        return entry

    def put(self, entry: MediaEntry) -> MediaEntry:
        self.entries[self.key(entry.path)] = entry
        return entry

    def remove(self, path: Path) -> bool:
        """Drop an entry from the store. Returns True if something was removed."""
        return self.entries.pop(self.key(path), None) is not None

    def staged(self) -> list[MediaEntry]:
        return [e for e in self.entries.values() if e.state in ("staged", "dirty")]

    def children(self, parent: MediaEntry) -> list[MediaEntry]:
        prefix = str(parent.path).lower()
        return [e for e in self.entries.values() if str(e.path).lower().startswith(prefix)]

    def clear(self) -> None:
        self.entries.clear()
