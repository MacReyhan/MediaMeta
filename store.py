"""Config, caches, manifests and revert support.

Nothing here touches the user's media; it only manages app state under
%APPDATA% / %LOCALAPPDATA% so scraped folders stay clean.
"""

from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path

APP_NAME = "MediaMeta"

CONFIG_DIR = Path(os.environ.get("APPDATA", Path.home())) / APP_NAME
LOCAL_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / APP_NAME
CONFIG_PATH = CONFIG_DIR / "config.json"
MANIFEST_DIR = LOCAL_DIR / "manifests"
CACHE_DIR = LOCAL_DIR / "cache"
LOG_DIR = LOCAL_DIR / "logs"

DEFAULTS: dict = {
    "tmdb_token": "",
    "language": "en-US",
    "image_language": "en,null",
    "overwrite_art": False,
    "download_actor_images": True,
    "embed_image_urls": True,
    "dry_run": True,
    "threads": 4,
    "confidence_threshold": 80,
    "appearance": "dark",
    "last_folder": "",
    # library
    "library_roots": [],
    "tree_width": 300,
    "expanded": [],
    # renaming
    "rename_files": True,
    "rename_folders": True,
    "rename_movie_file": "{title} ({year})",
    "rename_movie_folder": "{title} ({year})",
    "rename_show_folder": "{show} ({year})",
    "rename_season_folder": "Season {season:02}",
    "rename_episode_file": "{show} - S{season:02}E{episode:02} - {title}",
    "confirm_first_commit": True,
}


def ensure_dirs() -> None:
    for d in (CONFIG_DIR, MANIFEST_DIR, CACHE_DIR, LOG_DIR):
        d.mkdir(parents=True, exist_ok=True)


def load_config() -> dict:
    ensure_dirs()
    cfg = dict(DEFAULTS)
    if CONFIG_PATH.exists():
        try:
            cfg.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
        except Exception:
            pass  # corrupt config -> fall back to defaults
    return cfg


def save_config(cfg: dict) -> None:
    ensure_dirs()
    tmp = CONFIG_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    tmp.replace(CONFIG_PATH)


# ---------------------------------------------------------------- manifests
class Manifest:
    """Records every file we create or modify so a run can be undone."""

    def __init__(self, run_id: str | None = None):
        self.run_id = run_id or time.strftime("%Y%m%d-%H%M%S")
        self.actions: list[dict] = []

    def record(self, path: Path, action: str, backup: Path | None = None,
               previous: Path | None = None) -> None:
        self.actions.append(
            {
                "path": str(path),
                "action": action,  # created | modified | renamed
                "backup": str(backup) if backup else None,
                "previous": str(previous) if previous else None,
            }
        )

    @property
    def path(self) -> Path:
        base = MANIFEST_DIR / f"{self.run_id}.json"
        if not base.exists():
            return base
        n = 2
        while (candidate := MANIFEST_DIR / f"{self.run_id}-{n}.json").exists():
            n += 1
        return candidate

    def save(self) -> Path | None:
        if not self.actions:
            return None
        ensure_dirs()
        payload = {
            "run_id": self.run_id,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "actions": self.actions,
        }
        target = self.path
        target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return target


def latest_manifest() -> Path | None:
    if not MANIFEST_DIR.exists():
        return None
    files = [
        p for p in MANIFEST_DIR.glob("*.json")
        if not p.name.endswith(".reverted.json")
    ]
    files.sort(key=lambda p: (p.stat().st_mtime, p.name))
    return files[-1] if files else None


def revert_last(log=print) -> tuple[int, int]:
    """Undo the most recent run. Returns (restored, removed)."""
    mf = latest_manifest()
    if not mf:
        log("No manifest found — nothing to revert.")
        return (0, 0)

    data = json.loads(mf.read_text(encoding="utf-8"))
    restored = removed = renamed = 0
    created_parents: set[Path] = set()
    for entry in reversed(data.get("actions", [])):
        path = Path(entry["path"])
        action = entry.get("action")
        if action == "created":
            if path.exists():
                created_parents.add(path.parent)
                path.unlink()
                removed += 1
        elif action == "modified" and entry.get("backup"):
            bak = Path(entry["backup"])
            if bak.exists():
                shutil.copy2(bak, path)
                restored += 1
        elif action == "renamed" and entry.get("previous"):
            original = Path(entry["previous"])
            if path.exists() and not original.exists():
                path.rename(original)
                renamed += 1

    # Drop folders that only existed to hold generated files (e.g. .actors).
    for folder in sorted(created_parents, key=lambda p: len(p.parts), reverse=True):
        try:
            folder.rmdir()
        except OSError:
            pass

    mf.rename(mf.with_suffix(".reverted.json"))
    log(f"Reverted {data.get('run_id')}: {removed} removed, {restored} restored, {renamed} renamed back.")
    return (removed, restored)


def backup(path: Path) -> Path | None:
    """Copy an existing file to <name>.bak before we overwrite it."""
    if not path.exists():
        return None
    bak = path.with_name(path.name + ".bak")
    shutil.copy2(path, bak)
    return bak


def log_line(message: str) -> None:
    ensure_dirs()
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    try:
        with (LOG_DIR / "app.log").open("a", encoding="utf-8") as fh:
            fh.write(f"[{stamp}] {message}\n")
    except Exception:
        pass
