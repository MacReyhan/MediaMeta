"""Minimal TMDB v3 client built on urllib (no `requests` dependency).

Supports both credential styles:
  * v4 "API Read Access Token"  -> Authorization: Bearer <token>
  * v3 "API Key"                -> ?api_key=<key>

Responses are cached on disk so re-scraping a season is instant.
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.parse
from pathlib import Path

import net
import store

API_ROOT = "https://api.themoviedb.org/3"
IMAGE_ROOT = "https://image.tmdb.org/t/p"

MOVIE_APPEND = "credits,images,videos,external_ids,release_dates"
TV_APPEND = "credits,images,videos,external_ids,content_ratings"

USER_AGENT = "MediaMeta/1.0 (personal library scraper)"


class TMDBError(Exception):
    pass


def image_url(path: str | None, size: str = "w500") -> str:
    if not path:
        return ""
    if path.startswith("http"):
        return path
    return f"{IMAGE_ROOT}/{size}{path}"


def _is_bearer(token: str) -> bool:
    # v4 tokens are JWTs: three dot-separated segments, quite long.
    return token.count(".") == 2 and len(token) > 60


class TMDB:
    def __init__(
        self,
        token: str,
        language: str = "en-US",
        image_language: str = "en,null",
        cache_ttl: int = 7 * 24 * 3600,
    ):
        self.token = (token or "").strip()
        self.language = language or "en-US"
        self.image_language = image_language or "en,null"
        self.cache_ttl = cache_ttl
        self.bearer = _is_bearer(self.token)
        self._mem: dict[str, dict] = {}
        store.ensure_dirs()

    # ------------------------------------------------------------ transport
    def _cache_path(self, url: str) -> Path:
        key = hashlib.sha1(url.encode("utf-8")).hexdigest()
        return store.CACHE_DIR / f"{key}.json"

    def _read_cache(self, url: str):
        if url in self._mem:
            return self._mem[url]
        p = self._cache_path(url)
        if not p.exists():
            return None
        try:
            blob = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None
        if time.time() - blob.get("ts", 0) > self.cache_ttl:
            return None
        self._mem[url] = blob["data"]
        return blob["data"]

    def _write_cache(self, url: str, data: dict) -> None:
        self._mem[url] = data
        try:
            self._cache_path(url).write_text(
                json.dumps({"ts": time.time(), "data": data}), encoding="utf-8"
            )
        except Exception:
            pass

    def _get(self, path: str, params: dict | None = None, ttl: int | None = None) -> dict:
        params = dict(params or {})
        params.setdefault("language", self.language)
        if not self.bearer:
            params["api_key"] = self.token

        url = f"{API_ROOT}{path}?{urllib.parse.urlencode(params)}"
        cached = self._read_cache(url) if (ttl is None or ttl > 0) else None
        if cached is not None:
            return cached

        headers = {"Accept": "application/json", "User-Agent": USER_AGENT}
        if self.bearer:
            headers["Authorization"] = f"Bearer {self.token}"

        last_error = "unknown error"
        for attempt in range(4):
            try:
                status, body, reply = net.fetch(url, headers, timeout=30)
            except net.NetError as exc:
                last_error = str(exc)
                time.sleep(2 ** attempt)
                continue

            if status == 200:
                try:
                    data = json.loads(body.decode("utf-8"))
                except json.JSONDecodeError as exc:
                    raise TMDBError("TMDB returned malformed JSON") from exc
                self._write_cache(url, data)
                return data

            last_error = f"HTTP {status}"
            if status == 401:
                raise TMDBError(
                    "TMDB rejected the credential (401). Check the API key / "
                    "Read Access Token in Settings."
                )
            if status == 404:
                raise TMDBError(f"Not found: {path}")
            if status == 429:
                try:
                    wait = int(reply.get("retry-after", 2) or 2)
                except (TypeError, ValueError):
                    wait = 2
                time.sleep(wait)
                continue
            if 500 <= status < 600:
                time.sleep(2 ** attempt)
                continue
            raise TMDBError(f"HTTP {status} for {path}")

        raise TMDBError(f"{last_error} for {path}")

    # ------------------------------------------------------------ endpoints
    def search_movie(self, query: str, year: int | None = None) -> list[dict]:
        params = {"query": query, "include_adult": "false"}
        if year:
            params["year"] = str(year)
        return self._get("/search/movie", params).get("results", [])

    def search_tv(self, query: str, year: int | None = None) -> list[dict]:
        params = {"query": query, "include_adult": "false"}
        if year:
            params["first_air_date_year"] = str(year)
        return self._get("/search/tv", params).get("results", [])

    def movie(self, tmdb_id: int) -> dict:
        return self._get(f"/movie/{tmdb_id}", {"append_to_response": MOVIE_APPEND})

    def tv(self, tmdb_id: int) -> dict:
        return self._get(f"/tv/{tmdb_id}", {"append_to_response": TV_APPEND})

    def season(self, tmdb_id: int, season_number: int) -> dict:
        return self._get(f"/tv/{tmdb_id}/season/{season_number}")

    def season_credits(self, tmdb_id: int, season_number: int) -> dict:
        return self._get(f"/tv/{tmdb_id}/season/{season_number}/aggregate_credits")

    def collection(self, collection_id: int) -> dict:
        return self._get(f"/collection/{collection_id}")

    # ------------------------------------------------------------ helpers
    @staticmethod
    def pick_image(images: dict, key: str, language: str = "en") -> dict | None:
        """Choose the best image for a language, falling back to art without text."""
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

    @staticmethod
    def trailer_url(data: dict) -> str:
        for video in ((data.get("videos") or {}).get("results") or []):
            if video.get("site") == "YouTube" and video.get("type") == "Trailer":
                return f"https://www.youtube.com/watch?v={video.get('key')}"
        return ""

    @staticmethod
    def certification(data: dict, country: str = "US") -> str:
        for block in ((data.get("release_dates") or {}).get("results") or []):
            if block.get("iso_3166_1") != country:
                continue
            for rd in block.get("release_dates") or []:
                if rd.get("certification"):
                    return rd["certification"]
        return ""

    @staticmethod
    def tv_certification(data: dict, country: str = "US") -> str:
        for block in ((data.get("content_ratings") or {}).get("results") or []):
            if block.get("iso_3166_1") == country:
                return block.get("rating") or ""
        return ""
