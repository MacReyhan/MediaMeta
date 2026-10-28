"""Folder detection and filename parsing.

Turns an arbitrary media folder into a list of `Item`s: either one TV show
(with its episode files) or a set of movies.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path

VIDEO_EXTS = {
    ".mkv", ".mp4", ".avi", ".m4v", ".ts", ".mov", ".wmv", ".mpg", ".mpeg", ".flv", ".webm"
}

SXXEXX = re.compile(r"[sS](\d{1,2})[\s._-]?[eE](\d{1,3})")
SEASON_DIR = re.compile(r"^(season|series|stagione|staffel|temporada)\s*(\d{1,2})$", re.I)
SPECIALS_DIR = re.compile(r"^(specials|extras)$", re.I)
YEAR_RE = re.compile(r"(?<!\d)(19\d{2}|20\d{2})(?!\d)")

# Tokens that mark the end of the title in a release-style filename.
STOP_TOKENS = {
    "1080p", "720p", "2160p", "480p", "4k", "uhd", "hdr", "hdr10", "dv", "dolby",
    "bluray", "blu-ray", "brrip", "bdrip", "webrip", "web-dl", "webdl", "web",
    "hdrip", "dvdrip", "dvd", "remux", "hdtv", "pdtv",
    "x264", "x265", "h264", "h265", "hevc", "avc", "av1", "10bit", "8bit",
    "aac", "aac5", "ac3", "eac3", "dts", "ddp", "dd", "flac", "truehd", "atmos",
    "proper", "repack", "extended", "uncut", "remastered", "esubs", "subs",
    "english", "eng", "ita", "multi", "dual", "audio",
}

BRACKETS = re.compile(r"[\[\(\{][^\]\)\}]*[\]\)\}]")


@dataclass
class EpisodeFile:
    path: Path
    season: int
    episode: int

    @property
    def tag(self) -> str:
        return f"S{self.season:02d}E{self.episode:02d}"


@dataclass
class Item:
    kind: str                      # "movie" | "tv"
    root: Path                     # folder the item belongs to
    title_hint: str = ""
    year_hint: int | None = None
    season: int | None = None
    episodes: list[EpisodeFile] = field(default_factory=list)
    video: Path | None = None      # movies only
    # results
    tmdb_id: int | None = None
    matched_title: str = ""
    matched_year: int | None = None
    confidence: int = 0
    status: str = "pending"
    selected: bool = True
    forced: bool = False
    details: dict | None = None
    season_details: dict[int, dict] = field(default_factory=dict)

    @property
    def label(self) -> str:
        if self.kind == "tv":
            seasons = sorted({e.season for e in self.episodes})
            extra = f" · {len(self.episodes)} eps"
            if seasons:
                extra += f" · S{seasons[0]:02d}" + (f"-S{seasons[-1]:02d}" if len(seasons) > 1 else "")
            return f"{self.root.name}{extra}"
        return self.video.name if self.video else self.root.name

    @property
    def target_folder(self) -> Path:
        return self.root


# ---------------------------------------------------------------- parsing
def clean_title(raw: str) -> str:
    text = raw.replace("_", " ").replace(".", " ")
    text = BRACKETS.sub(" ", text)
    text = re.sub(r"\s*-\s*[A-Za-z0-9]+$", "", text)  # trailing release group
    words = text.split()
    kept: list[str] = []
    for word in words:
        token = re.sub(r"[^a-z0-9]", "", word.lower())
        if token in STOP_TOKENS:
            break
        kept.append(word)
    title = " ".join(kept).strip(" -_.")
    title = re.sub(r"\s{2,}", " ", title)
    return title or raw.strip()


def parse_name(raw: str) -> tuple[str, int | None, int | None, int | None]:
    """Return (title, year, season, episode) from a file or folder name."""
    name = Path(raw).name
    stem = name[: -len(Path(name).suffix)] if Path(name).suffix.lower() in VIDEO_EXTS else name
    season = episode = None
    m = SXXEXX.search(stem)
    if m:
        season, episode = int(m.group(1)), int(m.group(2))
        stem = stem[: m.start()]

    year = None
    matches = list(YEAR_RE.finditer(stem))
    if matches:
        last = matches[-1]
        # Only treat a trailing year as the release year.
        if not stem[last.end():].strip(" -_.()[]{}"):
            year = int(last.group(1))
            stem = stem[: last.start()].strip(" -_.([{")

    if year is None:
        # Release-style names put the year before the quality tags.
        cleaned = clean_title(stem)
        trailing = re.search(r"(?:^|\s)((?:19|20)\d{2})$", cleaned)
        if trailing:
            return cleaned[: trailing.start()].strip(), int(trailing.group(1)), season, episode
        return cleaned, None, season, episode

    return clean_title(stem), year, season, episode


def episode_title(raw: str) -> str:
    """Title part after the SxxExx tag, e.g. 'Gotham - S05E01 - Year Zero'."""
    name = Path(raw).name
    stem = name[: -len(Path(name).suffix)] if Path(name).suffix.lower() in VIDEO_EXTS else name
    match = SXXEXX.search(stem)
    if not match:
        return parse_name(raw)[0]
    rest = stem[match.end():].strip(" -_.")
    return clean_title(rest) if rest else parse_name(raw)[0]


def _videos(folder: Path) -> list[Path]:
    try:
        return sorted(
            p for p in folder.iterdir()
            if p.is_file() and p.suffix.lower() in VIDEO_EXTS and not p.name.startswith(".")
        )
    except (PermissionError, FileNotFoundError):
        return []


def _subdirs(folder: Path) -> list[Path]:
    try:
        return sorted(
            d for d in folder.iterdir()
            if d.is_dir() and not d.name.startswith((".", "@", "$"))
        )
    except (PermissionError, FileNotFoundError):
        return []


def _looks_like_show(folder: Path) -> bool:
    for d in _subdirs(folder):
        if SEASON_DIR.match(d.name) or SPECIALS_DIR.match(d.name):
            return True
    return any(SXXEXX.search(p.name) for p in _videos(folder))


def _season_number(folder: Path) -> int:
    if SPECIALS_DIR.match(folder.name):
        return 0
    m = SEASON_DIR.match(folder.name)
    if m:
        return int(m.group(2))
    m = re.search(r"(\d{1,2})", folder.name)
    return int(m.group(1)) if m else 1


def _tv_item(show_root: Path) -> Item:
    # If the user pointed at "Season 5", the show lives one level up.
    library_root = show_root
    if SEASON_DIR.match(show_root.name) or SPECIALS_DIR.match(show_root.name):
        library_root = show_root.parent
    title, year, _, _ = parse_name(library_root.name)
    item = Item(kind="tv", root=library_root, title_hint=title, year_hint=year)

    def add(path: Path, season: int) -> None:
        m = SXXEXX.search(path.name)
        if not m:
            return
        item.episodes.append(
            EpisodeFile(path=path, season=int(m.group(1)), episode=int(m.group(2)))
        )

    for video in _videos(show_root):
        add(video, 1)
    for sub in _subdirs(show_root):
        if not (SEASON_DIR.match(sub.name) or SPECIALS_DIR.match(sub.name)):
            continue
        season = _season_number(sub)
        for video in _videos(sub):
            add(video, season)

    item.episodes.sort(key=lambda e: (e.season, e.episode))
    return item


def _movie_item(folder: Path, video: Path) -> Item:
    file_title, file_year, _, _ = parse_name(video.name)
    dir_title, dir_year, _, _ = parse_name(folder.name)
    # Prefer "Movie Name (2010)" folders, otherwise trust the file name.
    use_dir = bool(dir_year) or (not file_year and len(dir_title) >= len(file_title) and len(dir_title) > 2)
    return Item(
        kind="movie",
        root=folder,
        video=video,
        title_hint=dir_title if use_dir else file_title,
        year_hint=dir_year or file_year,
    )


def scan(root: str | Path, mode: str = "auto") -> list[Item]:
    """Detect movies and/or a TV show under `root`."""
    root = Path(root)
    if not root.exists():
        return []

    if mode == "tv":
        return [_tv_item(root)]

    if mode == "movie":
        return _scan_movies(root)

    # auto
    if _looks_like_show(root):
        return [_tv_item(root)]

    subs = _subdirs(root)
    if subs:
        items: list[Item] = []
        for sub in subs:
            if _looks_like_show(sub):
                items.append(_tv_item(sub))
                continue
            videos = _videos(sub)
            if videos:
                items.append(_movie_item(sub, videos[0]))
        if items:
            return items

    return _scan_movies(root)


def _scan_movies(root: Path) -> list[Item]:
    items = [_movie_item(root, v) for v in _videos(root)]
    if items:
        return items
    # fall back to one level of sub-folders holding a single video each
    for sub in _subdirs(root):
        videos = _videos(sub)
        if len(videos) == 1:
            items.append(_movie_item(sub, videos[0]))
    return items


# ---------------------------------------------------------------- matching
def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def confidence(hint_title: str, hint_year: int | None, result: dict, kind: str) -> int:
    """Score a TMDB search result against our filename hint (0-100)."""
    title = result.get("title") if kind == "movie" else result.get("name")
    original = result.get("original_title") if kind == "movie" else result.get("original_name")
    date = result.get("release_date") if kind == "movie" else result.get("first_air_date")
    year = int(date[:4]) if date and len(date) >= 4 else None

    a = _norm(hint_title)
    b = _norm(title or "")
    c = _norm(original or "")
    ratio = max(SequenceMatcher(None, a, b).ratio(), SequenceMatcher(None, a, c).ratio())
    score = ratio * 100.0

    if hint_year and year:
        delta = abs(hint_year - year)
        if delta == 0:
            score = min(100.0, score + 12)
        elif delta <= 1:
            score += 2
        else:
            score -= 30

    return max(0, min(100, round(score)))


def best_match(results: list[dict], hint_title: str, hint_year: int | None, kind: str) -> dict | None:
    if not results:
        return None
    scored = [(confidence(hint_title, hint_year, r, kind), r) for r in results]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return scored[0][1] if scored else None
