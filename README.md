# MediaMeta

> A review-first TMDB scraper for movies and TV shows, built because tinyMediaManager and MediaElch keep guessing wrong and writing the guess anyway.

CustomTkinter UI (WinUI 3 inspired), stdlib HTTP (`urllib`), no Java dependency. Point it at library folders, expand a show/movie, review the match, edit anything off, then press **Save Changes**.

---

## Quick start

```bat
run.bat
```

On first launch the script creates `.venv`, installs `customtkinter` + `pillow`, and opens the app.

Manual route:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe app.py
```

---

## First run

1. Get a key at <https://www.themoviedb.org/settings/api>.
2. **Settings → API key / Read Access Token** → paste → **Test** → **Save**.
   - Both v3 keys and v4 JWT tokens work; the app detects which one you gave it.
3. **Settings → Library roots → Add folder…** and add every folder you browse (e.g. `G:\Movies`, `G:\TV Shows`). Roots persist across launches.
4. The token and roots live in `%APPDATA%\MediaMeta\config.json`; nothing is written to your media folders.

---

## Window layout

| Pane | Purpose |
|---|---|
| **Library tree** (left) | Saved library roots → shows/seasons/movies/episodes. Lazy: only listed when expanded. |
| **Metadata editor** (right) | Poster, title/status header, then tabs: **Details**, **Cast**, **Artwork**, **Files**, **NFO**. |
| **Footer / Activity** | Progress bar, status line, colorised log of every action. |

Status badges on tree rows:

| Badge | Meaning |
|---|---|
| `●` | Staged (scraped, not yet committed) |
| `✎` | Edited (dirty, staged) |
| `✓` | Saved / loaded from NFO |
| `⚠` | Needs review (low-confidence match) |
| `!` | Error / missing video |

---

## Workflow

1. **Browse** a root and expand down to a movie, show, season, or episode.
2. **Scrape selected** (right-click → Scrape) fetches metadata and **stages** it. Nothing writes to disk yet.
   - Scraping a season stages only that season; scraping the show stages all seasons.
3. **Review** on the right. All fields are editable: title, original title, year, dates, runtime, certification, rating, tagline, overview, genres, directors, writers, studios, countries, collection, trailer, network, status, external IDs. Edits stay in memory (`✎`).
4. **Cast** tab: full billing order with headshots. Include/exclude, rename role, reorder (↑ ↓), remove. Season and episode casts are staged (guest stars included).
5. **Artwork** tab: pick a different poster / fanart / logo / episode still from everything TMDB offers, or leave on *Auto*. Preview shows what will be written and whether a file already exists.
6. **Files** tab: exact rename/write plan that **Save Changes** will execute.
7. **NFO** tab: the XML exactly as it will be written.
8. **Save Changes** writes everything staged (NFO, art, renames). First commit shows the plan with confirmation; tick *Don't ask again* to skip later.
9. **Revert last** undoes the most recent run: deletes created files, restores overwritten `.nfo` from `.bak`, reverses renames.

If the automatic match is wrong or below confidence, use **Fix match…** (button or right-click) to search by title or paste a TMDB ID. Low-confidence items stay `⚠` and are excluded from commit until fixed.

---

## Renaming

Renaming is **on by default** (files + folders). Templates in **Settings → Renaming**:

| Template | Default |
|---|---|
| Movie file | `{title} ({year})` |
| Movie folder | `{title} ({year})` |
| Show folder | `{show} ({year})` |
| Season folder | `Season {season:02}` |
| Episode file | `{show} - S{season:02}E{episode:02} - {title}` |

Fields: `{title}`, `{show}`, `{year}`, `{season}`, `{episode}`. Missing values collapse cleanly (`Title ()` → `Title`). Illegal Windows chars (`<>:"/\|?*`) and reserved names (`CON`, `PRN`, etc.) are sanitised; targets that already exist are skipped with a warning.

---

## What gets written

### Movie

```text
Movie Name (2010)/
├─ Movie Name (2010).mkv
├─ Movie Name (2010).nfo       ← <movie> root
├─ poster.jpg
├─ fanart.jpg
├─ banner.jpg                  ← cropped from fanart by Pillow
├─ logo.png
└─ .actors/Ben McKenzie.jpg
```

### TV show

```text
Show (2019)/
├─ tvshow.nfo
├─ poster.jpg / fanart.jpg / banner.jpg / logo.png
├─ .actors/<Actor>.jpg
└─ Season 01/
   ├─ season.nfo
   ├─ season01-poster.jpg
   ├─ Show - S01E01 - Pilot.mkv
   ├─ Show - S01E01 - Pilot.nfo     ← <episodedetails>
   └─ Show - S01E01 - Pilot-thumb.jpg
```

NFO elements follow Jellyfin / Emby schema (valid for Kodi):
- `<uniqueid type="tmdb">`
- Legacy `<tmdbid>`, `<imdbid>`, `<tvdbid>`
- `<ratings><rating name="tmdb">`
- `<premiered>`, `<mpaa>`, `<trailer>`
- `<actor><name><role><order><thumb>`

Artwork names match Jellyfin expectations: `poster.jpg`, `fanart.jpg`, `banner.jpg`, `logo.png`, `seasonXX-poster.jpg`, `<episode>-thumb.jpg`.

---

## Matching rules

- Filename / folder parsed into title + year; release tags (`1080p`, `BluRay`, `x265`, `HEVC`, `AAC5.1`, group names) ignored.
- Score = title similarity (with original title) + year bonus/penalty.
- Below **Auto-write threshold** (default 80%) → `⚠` review state; not committed until fixed.
- Manual match (`Fix match`) skips scoring (always writes).

---

## Safety checks

| Mechanism | Behaviour |
|---|---|
| Two-phase | Scrape = fetch only; disk writes only on **Save Changes** |
| Confirmation | First commit lists every rename before touching anything |
| Backups | Existing `.nfo` → `.nfo.bak` before overwrite |
| Manifests | `%LOCALAPPDATA%\MediaMeta\manifests\<run>.json` |
| Revert | Deletes created files, restores `.bak`, reverses renames, drops empty `.actors` dirs |
| Collisions | Target-exists and duplicate targets skipped (never overwritten) |
| Cache | TMDB JSON cached 7 days in `%LOCALAPPDATA%\MediaMeta\cache` |

---

## Networking note

`api.themoviedb.org` is DNS-poisoned on some ISPs (local resolver returns a black-hole IP). `net.py` probes, resolves over DNS-over-HTTPS (Cloudflare / Google) if unreachable, connects to the real IP with SNI and cert validation intact. No VPN needed; nothing written to `hosts`.

Some networks also reset TLS for `image.tmdb.org` (the artwork CDN). `net.py` retries via `FALLBACK_HOSTS` (`tmdb-image-prod.b-cdn.net`), which serves identical paths and verifies `200 OK`.

---

## Tree actions

- **Scrape** — fetch metadata for selected item(s).
- **Save Changes** — commit staged items (with confirmation on first run).
- **Revert last** — undo the latest manifest.
- **Fix match…** — manual override / TMDB ID entry.
- **Open folder** — reveal in Explorer.
- **Delete…** (context menu) — removes the entry from the tree / state only (no files deleted from disk).

---

## Limits

- TMDB only. No TVDB/MusicBrainz/OMDb.
- TMDB has no banner/clearart/disc source — `banner.jpg` is generated by cropping fanart with Pillow.
- No subtitle download, no transcoding.
- Episode/season NFOs are written per season; no library-wide background scan.
- `.actors/` is a Kodi convention; Jellyfin reads embedded `<thumb>` URLs instead (toggle in Settings).

---

## File layout

```text
app.py          window shell, nav, background task queue
ag nts.md       session continuity notes (this doc at top)
README.md       this file
theme.py        WinUI3 design tokens
tmdb.py         API client, disk caching, retries
net.py          HTTP + DoH + image-CDN fallback
scanner.py      folder detection, filename parsing, confidence
edit.py         flat editable model (MediaEntry, EntryStore)
library.py      lazy tree nodes, detect_dir, build_roots
rename.py       planning / validation / apply / remap / sanitize
images.py       artwork download + banner generation
pipeline.py     stage() and commit() orchestration
store.py        config, manifests, revert
nfo.py          Jellyfin/Emby XML writers (flat model)
nfo_reader.py   reads existing NFOs into model
imgs.py         thumbnail cache for editor previews
views/          tree, editor, cast, artwork, settings, review, library, logview, widgets
```

---

## Run command reference

```powershell
# compile check
.venv\Scripts\python.exe -m compileall -q .

# run
.venv\Scripts\python.exe app.py
```

Config with working token: `%APPDATA%\MediaMeta\config.json` (`tmdb_token`: `c818c5bfaa4578fe32e0c7a4d70d9f32`).
