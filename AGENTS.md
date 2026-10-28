# Agents — Session Continuity Notes

This file lets any session (new agent or resumed worktree) pick up where the
MediaMeta redesign left off.

## Where things are

```
C:\Users\mbgaming\Documents\Experiments\MediaMeta
├── .venv (customtkinter 6.0.0 + pillow 13.0.0, built with py -3.11)
├── app.py              three-view shell, EntryStore, queue, busy state
├── edit.py              flat editable model (MediaEntry, EntryStore)
├── pipeline.py          stage() fetch / commit() write + rename + manifest
├── rename.py            rename planning / apply / remap / sanitize
├── store.py             config, manifest record/revert (incl. renamed)
├── library.py           lazy Node tree, detect_dir, build_roots
├── scanner.py           folder detection, filename parsing, episode_title
├── nfo.py / nfo_reader.py  Jellyfin/Emby XML writers + reader
├── images.py            artwork download + banner generation
├── imgs.py              thumbnail cache
├── theme.py             WinUI3 design tokens
├── tmdb.py              minimal TMDB v3 client (urllib, no requests)
├── net.py               HTTP + DoH fallback + FALLBACK_HOSTS image CDN
├── views/               tree, editor, cast, artwork, settings, review, library, logview, widgets
└── README.md            full workflow doc
```

Real config (with working token) at:
`C:\Users\mbgaming\AppData\Roaming\MediaMeta\config.json`

## What works (verified live)

- Live TMDB token (`c818c5bfaa4578fe32e0c7a4d70d9f32`) — search/movie/season/credits all work
- TV show end-to-end (Gotham S05): stage → commit (NFO, art, rename, season credits) → revert
- Movie end-to-end (Inception): folder rename + art + cast NFO → revert
- Image host fallback (image.tmdb.org TLS-reset → tmdb-image-prod.b-cdn.net 200 OK)
- Three-pane UI: lazy tree with badges (● ✎ ✓ ⚠ !), editor (Details/Cast/Artwork/Files/NFO), split pane, dirty tracking, save/revert
- Multi-video movie folder (primary = largest video; extra videos untouched)
- Tree delete (context menu "Delete…") removes from tree/state only (no disk deletion)
- Settings: library roots, renaming templates, art/actor/embed toggles, confidence threshold
- Compile check passes on all files; GUI smoke test passes (5 tabs, dirty tracking, stage→commit, reveal)

## Key design rules (from earlier decisions)

- No auto-save; everything is staged (`stage`) and committed explicitly (`commit`)
- Empty/unscraped items (`state == "empty"`) are never committed
- Low-confidence (`state == "review"`) excluded from commit until fixed manually
- Rename templates: `{title} ({year})`, `{show} ({year})`, `Season {season:02}`, episode `{show} - S{season:02}E{episode:02} - {title}`
- Empty/unsanitized titles never trigger rename (guarded in rename.py)
- `net.py`: `FALLBACK_HOSTS` rewrites image URLs from `image.tmdb.org` → `tmdb-image-prod.b-cdn.net`
- `store.revert_last()` deletes created files, restores `.bak`, reverses renames, drops empty `.actors` dirs

## What to test before calling done

1. `python -m compileall` passes on all `.py` files.
2. `app.py` launches from `.venv` without `SystemExit` from missing customtkinter.
3. `LibraryView.scrape_nodes()` stages a show/season/movie and `CommitDialog` shows the rename plan.
4. `revert_last()` cleans up created art/NFO and restores `.bak`.
5. For any fix to `library.py` `detect_dir` / `top_of`: verify movie folders (single or multi-video) show `kind == "movie"` and `video` points to the primary file.

## Blocked / known limits

- No subtitle download, no transcoding, no library-wide background scan.
- TMDB only (no TVDB direct integration besides the `tvdbid` field stored in NFO).
- Image CDN relies on the `FALLBACK_HOSTS` rewrite; no persistent image cache between sessions (thumbs cached in `%LOCALAPPDATA%\MediaMeta\thumbs`).

## Quick commands

```powershell
# compile check
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m compileall -q .

# run
.venv\Scripts\python.exe app.py
```
