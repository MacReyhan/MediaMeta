"""Stage (fetch only) and commit (write to disk) pipelines."""

from __future__ import annotations

from pathlib import Path

import edit
import images as art
import nfo
import rename
import scanner
import store
import tmdb
from edit import EntryStore, MediaEntry

ART_KEYS = {"poster": "posters", "fanart": "backdrops", "logo": "logos"}
ART_SIZES = {"poster": "w500", "fanart": "w1280", "logo": "w500"}


# ---------------------------------------------------------------- writer
class Writer:
    def __init__(self, manifest: store.Manifest, log):
        self.manifest = manifest
        self.log = log
        self.count = 0

    def xml(self, root, path: Path) -> None:
        nfo.write_xml(root, path, self.manifest)
        self.log(f"wrote  {path.name}", "ok")
        self.count += 1

    def image(self, url: str, path: Path, overwrite: bool = False) -> bool:
        if not url:
            return False
        existed = path.exists()
        ok = art.save_image(url, path, self.manifest, overwrite=overwrite)
        if ok:
            if not existed:
                self.log(f"fetched  {path.name}", "ok")
            self.count += 1
        else:
            self.log(f"missing  {path.name}", "warn")
        return ok


# ---------------------------------------------------------------- helpers
def _lang(cfg: dict) -> str:
    return (cfg.get("image_language") or "en,null").split(",")[0] or "en"


def _art_url(entry: MediaEntry, key: str, cfg: dict) -> str:
    chosen = (entry.art or {}).get(key)
    if chosen:
        return tmdb.image_url(chosen, ART_SIZES[key])
    best = art.best(entry.data.get("images") or {}, ART_KEYS[key], _lang(cfg))
    return art.url_for(best, ART_SIZES[key])


def _resolve(client: tmdb.TMDB, entry: MediaEntry, kind: str, log) -> tuple[int | None, int]:
    if entry.tmdb_id:
        return entry.tmdb_id, 100

    query = (entry.model.get("title") or "").strip()
    year = entry.model.get("year")
    if not query:
        query, parsed_year, _, _ = scanner.parse_name(entry.path.name)
        year = year or parsed_year

    results = client.search_movie(query, year) if kind == "movie" else client.search_tv(query, year)
    best = scanner.best_match(results, query, year, kind)
    if not best:
        return None, 0

    score = scanner.confidence(query, year, best, kind)
    date = best.get("release_date") if kind == "movie" else best.get("first_air_date")
    entry.tmdb_id = int(best["id"])
    entry.confidence = score
    entry.model["title"] = (best.get("title") if kind == "movie" else best.get("name")) or query
    entry.model["year"] = int(date[:4]) if date and len(date) >= 4 else year
    return entry.tmdb_id, score


def _mark_error(entry: MediaEntry, message: str, log) -> None:
    entry.state = "error"
    entry.error = message
    entry.status = message
    log(f"  {message}", "error")


# ---------------------------------------------------------------- stage
def stage_movie(client: tmdb.TMDB, entry: MediaEntry, cfg: dict, log) -> None:
    log(f"movie: {entry.model.get('title') or entry.path.name}", "info")
    tmdb_id, score = _resolve(client, entry, "movie", log)
    if tmdb_id is None:
        _mark_error(entry, "no TMDB match", log)
        return

    threshold = int(cfg.get("confidence_threshold", 80))
    if score < threshold:
        entry.state = "review"
        entry.status = f"needs review ({score}%)"
        log(f"  best guess only {score}% — review before saving", "warn")
        return

    data = client.movie(tmdb_id)
    entry.data = data
    entry.model = edit.model_from_movie(data)
    entry.cast = edit.cast_from_tmdb((data.get("credits") or {}).get("cast"))
    entry.origin = "tmdb"
    entry.confidence = score
    entry.state = "staged"
    entry.status = "staged"
    if entry.video is None and entry.path.is_file():
        entry.video = entry.path
    log(f"  matched {entry.model['title']} ({entry.model.get('year')}) — {len(entry.cast)} cast", "ok")


def stage_show(client: tmdb.TMDB, entry: MediaEntry, entries: EntryStore,
               cfg: dict, log, seasons: set[int] | None = None) -> None:
    log(f"show: {entry.model.get('title') or entry.path.name}", "info")
    tmdb_id, score = _resolve(client, entry, "tv", log)
    if tmdb_id is None:
        _mark_error(entry, "no TMDB match", log)
        return

    threshold = int(cfg.get("confidence_threshold", 80))
    if score < threshold:
        entry.state = "review"
        entry.status = f"needs review ({score}%)"
        log(f"  best guess only {score}% — review before saving", "warn")
        return

    data = client.tv(tmdb_id)
    entry.data = data
    entry.model = edit.model_from_show(data)
    entry.cast = edit.cast_from_tmdb((data.get("credits") or {}).get("cast"))
    entry.origin = "tmdb"
    entry.confidence = score
    entry.state = "staged"
    entry.status = "staged"

    scanned = scanner.scan(entry.path, "tv")
    if not scanned:
        _mark_error(entry, "no episodes found", log)
        return
    item = scanned[0]
    show_title = entry.model.get("title") or entry.path.name

    by_season: dict[int, list] = {}
    for episode in item.episodes:
        if seasons and episode.season not in seasons:
            continue
        by_season.setdefault(episode.season, []).append(episode)

    total = 0
    for season_no in sorted(by_season):
        try:
            season_data = client.season(tmdb_id, season_no)
            credits = client.season_credits(tmdb_id, season_no)
        except tmdb.TMDBError as exc:
            log(f"  season {season_no}: {exc}", "warn")
            continue

        season_dir = by_season[season_no][0].path.parent
        season_entry = entries.ensure("season", season_dir, season=season_no)
        season_entry.data = season_data
        season_entry.model = edit.empty_model("season")
        season_entry.model.update({
            "title": season_data.get("name") or f"Season {season_no}",
            "overview": season_data.get("overview") or "",
            "premiered": season_data.get("air_date") or "",
            "year": int(season_data["air_date"][:4]) if season_data.get("air_date") else None,
            "season": season_no,
            "tmdb_id": tmdb_id,
        })
        season_entry.state = "staged"
        season_entry.status = "staged"
        season_entry.cast = edit.cast_from_tmdb((credits or {}).get("cast"))

        meta_by_no = {e.get("episode_number"): e for e in season_data.get("episodes") or []}
        for episode in by_season[season_no]:
            meta = meta_by_no.get(episode.episode)
            if not meta:
                continue
            ep_entry = entries.ensure(
                "episode", episode.path, video=episode.path,
                season=season_no, episode=episode.episode,
            )
            ep_entry.data = meta
            ep_entry.model = edit.model_from_episode(meta, show_title, season_no)
            ep_entry.cast = edit.cast_from_tmdb(meta.get("guest_stars"))
            ep_entry.state = "staged"
            ep_entry.status = "staged"
            ep_entry.tmdb_id = meta.get("id")
            total += 1

    entry.status = f"staged · {total} episodes"
    log(f"  matched {entry.model['title']} ({entry.model.get('year')}) — {total} episodes", "ok")


def stage(client: tmdb.TMDB, entry: MediaEntry, entries: EntryStore,
          cfg: dict, log, seasons: set[int] | None = None) -> None:
    try:
        if entry.kind == "movie":
            stage_movie(client, entry, cfg, log)
        elif entry.kind == "show":
            stage_show(client, entry, entries, cfg, log, seasons)
        elif entry.kind == "episode":
            log("episodes are staged with their show", "warn")
        else:
            log(f"cannot scrape a {entry.kind}", "warn")
    except tmdb.TMDBError as exc:
        _mark_error(entry, str(exc), log)
    except Exception as exc:  # noqa: BLE001 - one bad node must not kill the batch
        _mark_error(entry, f"{type(exc).__name__}: {exc}", log)


# ---------------------------------------------------------------- commit
def _commit_movie(entry: MediaEntry, cfg: dict, manifest: store.Manifest,
                  log, overwrite: bool) -> None:
    video = entry.video or (entry.path if entry.path.is_file() else None)
    if not video or not video.exists():
        _mark_error(entry, "video file missing", log)
        return

    plan = rename.validate(rename.plan_movie(entry, cfg), log)
    applied = rename.apply(plan, manifest, log)
    video = rename.remap(video, applied)
    folder = video.parent

    writer = Writer(manifest, log)
    writer.xml(
        nfo.movie_nfo(entry.model, entry.cast, bool(cfg.get("embed_image_urls", True))),
        video.with_suffix(".nfo"),
    )
    writer.image(_art_url(entry, "poster", cfg), folder / art.POSTER, overwrite)
    fanart = folder / art.FANART
    if writer.image(_art_url(entry, "fanart", cfg), fanart, overwrite):
        _banner(writer, fanart, folder / art.BANNER)
    if _art_url(entry, "logo", cfg):
        writer.image(_art_url(entry, "logo", cfg), folder / art.LOGO, overwrite)

    if cfg.get("download_actor_images", True):
        _people(writer, entry.cast, folder)

    entry.video = video
    entry.path = folder
    entry.state = "saved"
    entry.status = f"saved · {writer.count} files"
    log(f"  saved {entry.model.get('title')} — {writer.count} files", "ok")


def _banner(writer: Writer, fanart: Path, dest: Path) -> None:
    existed = dest.exists()
    if art.make_banner(fanart, dest) and not existed:
        writer.manifest.record(dest, "created")
        writer.count += 1
        writer.log(f"generated  {dest.name}", "ok")


def _people(writer: Writer, cast, folder: Path, limit: int = 15) -> None:
    target = art.actor_dir(folder)
    for person in (cast or [])[:limit]:
        if not person.include or not person.profile_path:
            continue
        writer.image(person.thumb_url(), target / f"{art._safe(person.name)}.jpg")


def _commit_show(entry: MediaEntry, entries: EntryStore, cfg: dict,
                 manifest: store.Manifest, log, overwrite: bool) -> None:
    season_entries = {
        e.season: e for e in entries.entries.values()
        if e.kind == "season" and e.path.parent == entry.path
    }
    episode_entries = [
        e for e in entries.entries.values()
        if e.kind == "episode" and e.video and entry.path in e.video.parents
    ]

    plan = rename.validate(rename.plan_show(entry, season_entries, episode_entries, cfg), log)
    applied = rename.apply(plan, manifest, log)

    root = rename.remap(entry.path, applied)
    writer = Writer(manifest, log)
    embed = bool(cfg.get("embed_image_urls", True))

    if entry.state != "empty":
        writer.xml(nfo.show_nfo(entry.model, entry.cast, embed), root / "tvshow.nfo")
        writer.image(_art_url(entry, "poster", cfg), root / art.POSTER, overwrite)
        fanart = root / art.FANART
        if writer.image(_art_url(entry, "fanart", cfg), fanart, overwrite):
            _banner(writer, fanart, root / art.BANNER)
        if _art_url(entry, "logo", cfg):
            writer.image(_art_url(entry, "logo", cfg), root / art.LOGO, overwrite)
        if cfg.get("download_actor_images", True):
            _people(writer, entry.cast, root)

    for number, season_entry in sorted(season_entries.items()):
        folder = rename.remap(season_entry.path, applied)
        season_entry.path = folder
        if season_entry.state != "empty":
            writer.xml(nfo.season_nfo(number, season_entry.model), folder / "season.nfo")
            poster_path = (season_entry.data or {}).get("poster_path")
            if poster_path:
                writer.image(tmdb.image_url(poster_path, "w500"),
                             folder / art.season_poster_name(number), overwrite)
        season_entry.state = "saved"
        season_entry.status = "saved"

    for episode in episode_entries:
        video = rename.remap(episode.video, applied)
        if episode.state != "empty":
            writer.xml(nfo.episode_nfo(episode.model, episode.cast, embed), video.with_suffix(".nfo"))
            if episode.model.get("thumb"):
                writer.image(
                    tmdb.image_url(episode.model["thumb"], "w780"),
                    video.parent / art.episode_thumb_name(video),
                    overwrite,
                )
        episode.path = video
        episode.video = video
        episode.state = "saved"
        episode.status = "saved"

    entry.path = root
    entry.state = "saved"
    entry.status = f"saved · {writer.count} files"
    log(f"  saved {entry.model.get('title')} — {len(episode_entries)} episodes, {writer.count} files", "ok")


def commit(top_entries: list[MediaEntry], entries: EntryStore, cfg: dict,
           manifest: store.Manifest, log, progress=None) -> int:
    overwrite = bool(cfg.get("overwrite_art", False))
    done = 0
    total = max(1, len(top_entries))

    for entry in top_entries:
        try:
            if entry.kind == "movie":
                _commit_movie(entry, cfg, manifest, log, overwrite)
            elif entry.kind == "show":
                _commit_show(entry, entries, cfg, manifest, log, overwrite)
        except Exception as exc:  # noqa: BLE001
            _mark_error(entry, f"{type(exc).__name__}: {exc}", log)
        done += 1
        if progress:
            progress(done / total, f"{done}/{total} · {entry.path.name}")
    return done
