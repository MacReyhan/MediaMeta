"""Rename planning and application.

Two phases on purpose: build and validate the whole plan first, then move
things deepest-first. Every move is recorded in the manifest as `renamed`
(new path + previous path), so Revert puts the original names back.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import store

ILLEGAL = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
SIDECAR_EXTS = {".nfo", ".srt", ".ass", ".ssa", ".sub", ".idx", ".vtt", ".sup", ".smi"}
MAX_PATH = 250


def sanitize(name: str, fallback: str = "Untitled") -> str:
    text = ILLEGAL.sub("", name or "")
    text = re.sub(r"\s+", " ", text).strip(" .")
    text = text.rstrip(".")
    if not text:
        text = fallback
    if text.split(".")[0].upper() in RESERVED:
        text = "_" + text
    return text


class _Safe(dict):
    def __missing__(self, key):  # unknown placeholder -> empty, never KeyError
        return ""


def fmt(template: str, **values) -> str:
    try:
        text = template.format_map(_Safe(values))
    except Exception:
        text = ""
    text = re.sub(r"\(\s*\)", "", text)
    text = re.sub(r"\[\s*\]", "", text)
    text = re.sub(r"\s+", " ", text).strip(" -_.")
    return text


def movie_name(model: dict, cfg: dict) -> str:
    if not (model.get("title") or "").strip():
        return ""
    return sanitize(
        fmt(
            cfg.get("rename_movie_file", "{title} ({year})"),
            title=model.get("title") or "",
            year=model.get("year") or "",
        )
    )


def movie_folder(model: dict, cfg: dict) -> str:
    if not (model.get("title") or "").strip():
        return ""
    return sanitize(
        fmt(
            cfg.get("rename_movie_folder", "{title} ({year})"),
            title=model.get("title") or "",
            year=model.get("year") or "",
        )
    )


def show_folder(model: dict, cfg: dict) -> str:
    if not (model.get("title") or "").strip():
        return ""
    return sanitize(
        fmt(
            cfg.get("rename_show_folder", "{show} ({year})"),
            show=model.get("title") or "",
            title=model.get("title") or "",
            year=model.get("year") or "",
        )
    )


def season_folder(number: int, cfg: dict) -> str:
    if number == 0:
        return "Specials"
    return sanitize(
        fmt(cfg.get("rename_season_folder", "Season {season:02}"), season=number),
        fallback=f"Season {number:02d}",
    )


def episode_name(show: str, season: int, episode: int, title: str, cfg: dict) -> str:
    if not (show or "").strip():
        return ""
    text = fmt(
        cfg.get("rename_episode_file", "{show} - S{season:02}E{episode:02} - {title}"),
        show=show or "",
        season=season,
        episode=episode,
        title=title or "",
    )
    if not text:
        text = f"{show} - S{season:02}E{episode:02}"
    return sanitize(text)


# ---------------------------------------------------------------- plan
@dataclass
class Rename:
    src: Path
    dst: Path
    kind: str  # file | folder


def sidecars(video: Path) -> list[Path]:
    """Sibling files that belong to a video: .nfo, -thumb.jpg, subtitles…"""
    out: list[Path] = []
    stem = video.stem
    try:
        siblings = list(video.parent.iterdir())
    except OSError:
        return out
    for item in siblings:
        if item == video or not item.is_file():
            continue
        name = item.name
        if not (name.startswith(stem + ".") or name.startswith(stem + "-")):
            continue
        if item.suffix.lower() in SIDECAR_EXTS or "-thumb" in name.lower():
            out.append(item)
    return out


def _file_plan(video: Path, new_stem: str) -> list[Rename]:
    plan = [Rename(video, video.with_name(new_stem + video.suffix), "file")]
    for extra in sidecars(video):
        suffix = extra.name[len(video.stem):]
        plan.append(Rename(extra, extra.with_name(new_stem + suffix), "file"))
    return plan


def plan_movie(entry, cfg: dict) -> list[Rename]:
    plan: list[Rename] = []
    if not entry.video or not entry.video.exists():
        return plan

    folder = entry.video.parent
    if cfg.get("rename_folders", True) and entry.path.is_dir():
        wanted = movie_folder(entry.model, cfg)
        if wanted and wanted != folder.name:
            plan.append(Rename(folder, folder.with_name(wanted), "folder"))

    if cfg.get("rename_files", True):
        stem = movie_name(entry.model, cfg)
        if stem:
            plan.extend(_file_plan(entry.video, stem))
    return plan


def plan_show(show_entry, season_entries: dict, episode_entries: list, cfg: dict) -> list[Rename]:
    plan: list[Rename] = []
    root = show_entry.path

    if cfg.get("rename_folders", True):
        wanted = show_folder(show_entry.model, cfg)
        if wanted and wanted != root.name:
            plan.append(Rename(root, root.with_name(wanted), "folder"))

        for number, season_entry in season_entries.items():
            folder = season_entry.path
            if not folder.is_dir():
                continue
            wanted_season = season_folder(number, cfg)
            if wanted_season and wanted_season != folder.name:
                plan.append(Rename(folder, folder.with_name(wanted_season), "folder"))

    if cfg.get("rename_files", True):
        show_name = show_entry.model.get("title") or root.name
        for episode in episode_entries:
            if not episode.video or not episode.video.exists():
                continue
            stem = episode_name(
                show_name,
                episode.season or 0,
                episode.episode or 0,
                episode.model.get("title") or "",
                cfg,
            )
            if stem:
                plan.extend(_file_plan(episode.video, stem))
    return plan


# ---------------------------------------------------------------- apply
def validate(plan: list[Rename], log) -> list[Rename]:
    seen: set[str] = set()
    valid: list[Rename] = []
    for ren in plan:
        if ren.src == ren.dst or not ren.src.exists():
            continue
        key = str(ren.dst).lower()
        if key in seen:
            log(f"rename conflict (duplicate target): {ren.dst.name}", "warn")
            continue
        if ren.dst.exists() and str(ren.dst).lower() != str(ren.src).lower():
            log(f"rename skipped (target exists): {ren.dst.name}", "warn")
            continue
        if len(str(ren.dst)) > MAX_PATH:
            log(f"rename skipped (path too long): {ren.dst.name}", "warn")
            continue
        seen.add(key)
        valid.append(ren)
    return valid


def apply(plan: list[Rename], manifest: store.Manifest, log) -> list[Rename]:
    applied: list[Rename] = []
    for ren in sorted(plan, key=lambda r: len(r.src.parts), reverse=True):
        try:
            if ren.src.name.lower() == ren.dst.name.lower() and ren.src != ren.dst:
                # case-only rename needs a detour on NTFS
                temp = ren.src.with_name(ren.src.name + ".mm-tmp")
                ren.src.rename(temp)
                temp.rename(ren.dst)
            else:
                ren.src.rename(ren.dst)
        except OSError as exc:
            log(f"rename failed: {ren.src.name} -> {exc}", "error")
            continue
        manifest.record(ren.dst, "renamed", previous=ren.src)
        applied.append(ren)
        log(f"renamed  {ren.src.name}  ->  {ren.dst.name}", "ok")
    return applied


def remap(path: Path, applied: list[Rename]) -> Path:
    """Translate an original path through the renames that were applied."""
    folders = [(r.src, r.dst) for r in applied if r.kind == "folder"]
    files = {r.src: r.dst for r in applied if r.kind == "file"}

    # File renames happen first: their source paths still sit in the old folders.
    result = files.get(path, path)
    # Then rewrite folder prefixes, deepest first, so nested renames compose.
    for src, dst in sorted(folders, key=lambda pair: len(pair[0].parts), reverse=True):
        try:
            relative = result.relative_to(src)
        except ValueError:
            continue
        result = dst / relative
    return result
