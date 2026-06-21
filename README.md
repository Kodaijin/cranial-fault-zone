# Cranial Fault Zone

A self-contained, Dockerized web app for tracking migraines and headaches. It
attaches environmental data (weather, air quality, pollen) to every entry, shows a
GitHub-style activity grid, adds a gamification layer, runs range-filtered analytics,
and produces a clinical PDF export. **No API keys required**: all environmental data
comes from free, keyless sources.

## Table of contents

- [Features](#features)
- [Tech stack](#tech-stack)
- [Quick start](#quick-start)
- [Project structure](#project-structure)
- [API overview](#api-overview)
- [Deploying to another Docker host](#deploying-to-another-docker-host)
- [Updating a deployed instance](#updating-a-deployed-instance-without-losing-data)
- [Notes](#notes)
- [Changelog](#changelog)

---

## Features

- **Log entries** with start and end time, headache type, multiple medications,
  location, multi-zone pain mapping, and notes. Mark a headache **still going** (it
  ends at 11:59 PM and stays flagged as ongoing) and **link entries** into one
  multi-day episode. Past entries stay fully editable.
- **Entries tab**: a dedicated navigation tab that lists your full log history, with
  edit and delete buttons on each row. The edit button uses a distinct pencil icon so
  it reads clearly next to delete.
- **Automatic environmental snapshot** captured at save time for the entry's location:
  - **Weather** (Open-Meteo): temperature, barometric pressure, humidity, conditions.
  - **Air quality** (Open-Meteo): PM2.5, PM10, ozone, carbon monoxide, nitrogen
    dioxide, nitrogen monoxide, nitrogen oxides (NOₓ = NO + NO₂), sulphur dioxide.
  - **Pollen** (pollen.com / IQVIA, US): tree, grass, weed. Open-Meteo's pollen feed
    is Europe-only, so US allergens come from pollen.com instead.
  - If a source is unavailable the value is stored as `N/A` and the save still goes
    through. Editing an entry keeps its original snapshot.
- **Automatic good days**: in Auto mode, any day with no entry (from your first entry
  through yesterday) is filled with a good-day record, so it captures the same weather
  and air-quality data as a logged day. Past days pull historical weather and air
  quality from Open-Meteo; allergens for days within the last ~30 come from pollen.com's
  history (older days have none, since no historical US pollen source exists). The
  backfill runs when you open the app, and logging a real entry for a day replaces its
  placeholder. Manual mode turns this off and counts only the good days you log yourself.
- **Dashboard**: gamification (XP, levels, streaks, quests, achievements), the **Fault
  Zone Stability Index**, and an **activity grid** of the last 4 months with three
  states: untracked (before your first entry), good day (green, no pain), and pain days
  (red intensity). Tap the grid to open the full 365-day view, which adds month labels
  and good/pain/tracked totals.
- **Reports**: a date-range selector (Week, Month, Year, or custom) drives four charts
  (pressure and humidity, major pollutants, trace pollutants, allergens) plus a
  range-aware **clinical PDF export**. The charts plot both pain days and good days so
  the environmental record stays continuous — pain days show as diamonds, good days as
  small dots. Backfilled days within the last ~30 carry allergens from pollen.com
  history; older ones don't, as no historical US pollen source exists.
- **Backup & restore**: from the Manage page, export your entire history to a JSON file
  and import it on another deployment. The backup carries everything — entries,
  reference lists, settings, episode links, and environmental snapshots — and importing
  replaces the target's data with an exact copy (ids preserved).
- **Clinical PDF**: total attacks, most-frequent pain locations, medication efficacy,
  an environmental exposure summary (averages), and a chronological notes appendix. It
  is black-on-white and print-friendly.
- **Fixed GMT-8 day boundaries**: "end of day" is midnight GMT-8 no matter the host
  clock, so grids, streaks, and date ranges stay consistent.

## Tech stack

| Layer | Choice |
|-------|--------|
| Backend | Python 3.12 + FastAPI (Uvicorn) |
| Database | SQLite via SQLAlchemy 2.x (stored in a Docker volume) |
| Frontend | Vanilla-JS SPA (hash router) + Tailwind (CDN) + Chart.js |
| PDF | ReportLab |
| Container | Dockerfile + docker-compose |

---

## Quick start

Requires Docker + Docker Compose.

```bash
docker compose up -d --build
```

Then open <http://localhost:8000>. Stop with `docker compose down` (data is kept in
the volume) or `docker compose down -v` to also wipe the database.

No configuration is needed. `.env` is optional and unused; weather, air quality, and
pollen are all keyless.

---

## Project structure

```
app/
  api/          # route modules: health, crud, entries, stats, settings,
                #   gamification, good_days, export
  models/       # SQLAlchemy models
  services/     # weather, environment (air quality), geocode, good_days, pdf,
                #   gamification
  static/       # SPA assets (app.js, styles.css)
  templates/    # index.html shell
  db.py         # engine/session/init + lightweight column migrations
  seed.py       # default headache types, locations, pain zones
  tz.py         # fixed GMT-8 timezone + day-bucketing helpers
  main.py       # FastAPI entrypoint
Dockerfile
docker-compose.yml
requirements.txt
```

## API overview

| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/health` | `{"status":"ok"}` |
| GET/POST/DELETE | `/api/headache_types`, `/api/medications`, `/api/locations` | reference-data CRUD |
| GET | `/api/pain_zones` | list (POST optional) |
| GET | `/api/entries` | list |
| POST | `/api/entries` | create (fetches environmental snapshot) |
| GET | `/api/entries/{id}` | fetch one |
| PUT | `/api/entries/{id}` | edit (preserves the original snapshot) |
| DELETE | `/api/entries/{id}` | delete |
| GET/PUT | `/api/settings` | good-day mode (`auto` / `manual`) |
| POST | `/api/good_days/fill` | backfill auto good days (Auto mode only); called on app open |
| GET | `/api/stats/grid` | 365-day activity grid (untracked / good / pain) |
| GET | `/api/stats/trends?start=&end=` | time series for charts (GMT-8 day filter) |
| GET | `/api/gamification` | XP, level, streaks, stability, quests, achievements |
| GET | `/api/export/pdf?start=&end=` | clinical PDF for the selected range |
| GET | `/api/data/export` | download the full database as a JSON backup |
| POST | `/api/data/import` | restore from a JSON backup (replaces all data) |

Date-range params (`start`, `end`) are `YYYY-MM-DD`, both optional, inclusive, and
evaluated against the entry's **GMT-8** calendar day.

---

## Deploying to another Docker host

The app rebuilds from source; the only stateful piece is the named volume
`cranialfaultzone_cranial-data` holding `/data/cranial.db`.

### 1. Move the app

```bash
git clone https://github.com/Kodaijin/cranial-fault-zone.git
cd cranial-fault-zone
docker compose up -d --build
```

> The Compose volume name is derived from the project (folder) name. Keep the folder
> named so the project is `cranialfaultzone` (or pass `-p cranialfaultzone`) if you
> intend to restore an existing data volume by name.

### 2. Move the data (optional, only to keep existing entries)

The simplest way is from the app itself: on the old deployment open **Manage → Backup &
Restore → Export data** to download a JSON file, then on the new deployment use **Import
data** to load it (this replaces whatever is there). That moves your whole history without
touching Docker volumes. The volume tarball method below is the alternative when you'd
rather copy the database file directly.

**On the old host**, export the volume to a tarball:

```bash
docker run --rm \
  -v cranialfaultzone_cranial-data:/data \
  -v "$PWD":/backup \
  alpine tar czf /backup/cranial-data.tar.gz -C /data .
```

**On the new host**, restore it (with the app stopped):

```bash
docker volume create cranialfaultzone_cranial-data
docker run --rm \
  -v cranialfaultzone_cranial-data:/data \
  -v "$PWD":/backup \
  alpine sh -c "rm -rf /data/* && tar xzf /backup/cranial-data.tar.gz -C /data"
docker compose up -d
```

---

## Updating a deployed instance (without losing data)

Your code lives in the Docker **image**; your database lives in the separate named
**volume** (`cranialfaultzone_cranial-data` → `/data/cranial.db`). Rebuilding the
image recreates the container but re-attaches the same volume, so entries survive. The
only thing that wipes data is `docker compose down -v` (the `-v` deletes volumes), so
never use it to update.

Standard data-safe update, run in the project folder on the host:

```bash
git pull origin main          # get the latest code
docker compose up -d --build  # rebuild image + recreate container, keep the volume
```

`--build` is required because the Python and static files are baked into the image at
build time. It is fast because dependency layers are cached. New tables and seed rows
from an update (for example the `settings` table) are created on startup, and a
lightweight migration adds any new columns to existing tables (for example the entry
`end_time`, `is_ongoing`, `linked_entry_id`, and `auto_generated` fields), so data
moves forward untouched.

**Optional: snapshot the volume before updating** (lets you roll back):

```bash
docker run --rm \
  -v cranialfaultzone_cranial-data:/data \
  -v "$PWD":/backup \
  alpine tar czf /backup/cranial-data-$(date +%F).tar.gz -C /data .
```

### Avoiding rebuilds (dev/staging only)

To make `git pull` take effect with no rebuild, bind-mount the source and enable
auto-reload in `docker-compose.yml`:

```yaml
    volumes:
      - cranial-data:/data
      - ./app:/app/app          # live-mount the code over the image's copy
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Then a `git pull` is picked up live (uvicorn restarts on Python changes; static files
are served fresh on next load). The trade-off is that the running app now depends on
the checked-out files on that host, so keep `--build` for a real production box and
reserve the bind-mount for dev/staging.

### Quick reference

| Goal | Command |
|------|---------|
| Update + keep data (normal) | `git pull && docker compose up -d --build` |
| Back up the DB volume | the `alpine tar` one-liner above |
| Restart without rebuild (no code change) | `docker compose restart` |
| Wipes the database (avoid) | `docker compose down -v` |

---

## Notes

- **Port**: maps `8000:8000`; change it in `docker-compose.yml` if it's taken.
- **Static assets** are baked into the image; after editing `app/static/*` or
  `app/templates/*`, rebuild (`docker compose up -d --build`). Asset URLs are versioned
  (`?v=N`) and the HTML is served `Cache-Control: no-store` so changes show without a
  hard refresh.
- **Data sources**: Open-Meteo (<https://open-meteo.com>) for weather and air quality;
  pollen.com (IQVIA) for US pollen. Open-Meteo's pollen feed is Europe-only, so US
  pollen comes from pollen.com (which exposes an overall index plus active plant
  categories rather than per-species magnitudes).
- **Backfilled good days** read historical weather and air quality from Open-Meteo
  (recent days from the forecast API's past data, older days from the ERA5 archive).
  Historical pollen has no source, so backfilled days show pollen as `N/A`.

---

## Changelog

History before this entry is not captured here.

### 2026-06-21

- Fixed the environmental report charts: good days were being dropped, so the four
  charts (pressure/humidity, major and trace pollutants, allergens) showed almost
  nothing once most of your days were auto-filled good days. They now include good
  days, drawn as small dots to set them apart from pain days (diamonds).
- Fixed entries saved without a location storing an outdated, short environmental
  snapshot that was missing the carbon monoxide, nitrogen, and sulphur fields. Every
  entry now stores the full set of keys (as `N/A` when there's no location) so nothing
  silently disappears from the charts.
- Auto good days now backfill **allergens** for recent days from pollen.com's ~30-day
  history (Open-Meteo has no US pollen). Days older than that still have no allergen
  reading, since no historical US pollen source exists.
- Added **backup & restore** on the Manage page: export the whole database to a JSON
  file and import it on another deployment. Import replaces all existing data and
  preserves ids, so episode links and associations move intact. New endpoints
  `GET /api/data/export` and `POST /api/data/import`.

### 2026-06-19

- Added an **Entries** tab that lists your full log history, with a clearer pencil
  edit button on each row.
- Added **automatic good days**. In Auto mode, empty days from your first entry through
  yesterday are filled with good-day records that pull historical weather and air
  quality. The fill runs when you open the app, and logging a real entry replaces that
  day's placeholder. Manual mode turns it off.
- Reworked the dashboard heatmap to show the last 4 months so it fits on a phone
  without sideways scrolling. Tapping it opens the full 365-day view with month labels
  and good, pain, and tracked totals.
- Added the `auto_generated` column on entries (applied on startup) and a
  `POST /api/good_days/fill` endpoint.
