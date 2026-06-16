# Cranial Fault Zone

A self-contained, Dockerized web app for tracking migraines and headaches — with
automatic environmental enrichment (weather, air quality, pollen), a GitHub-style
activity grid, a gamification layer, range-filtered analytics, and a clinical PDF
export. **No API keys required** — all environmental data comes from free, keyless
sources.

---

## Features

- **Log entries** with start/end time, headache type, **multiple medications**,
  location, **multi-zone pain mapping**, and notes. Mark a headache **still going**
  (ends at 11:59 PM, flagged ongoing) and **link entries** into one multi-day episode.
  Past entries are fully **editable**.
- **Automatic environmental snapshot** captured at save time for the entry's location:
  - **Weather** (Open-Meteo): temperature, **barometric pressure**, humidity, conditions.
  - **Air quality** (Open-Meteo): PM2.5, PM10, ozone, carbon monoxide, nitrogen
    dioxide, nitrogen monoxide, nitrogen oxides (NOₓ = NO + NO₂), sulphur dioxide.
  - **Pollen** (pollen.com / IQVIA, US): tree, grass, weed.
  - Graceful fallback — if a source is unavailable the value is stored as `N/A` and
    the save is never blocked. Editing an entry **preserves** its original snapshot.
- **Dashboard**: gamification (XP, levels, streaks, quests, achievements), the
  **Fault Zone Stability Index**, and a 365-day **activity grid** with three states —
  untracked (before your first entry), **good day** (green, no pain), and pain days
  (red intensity).
- **Reports**: date-range selector (Week / Month / Year / custom) driving four charts
  (pressure & humidity, major pollutants, trace pollutants, allergens) plus a
  range-aware **clinical PDF export**.
- **Clinical PDF**: total attacks, most-frequent pain locations, medication efficacy,
  an **environmental exposure summary** (averages), and a chronological notes appendix —
  black-on-white and print-friendly.
- **Fixed GMT-8 day boundaries** — "end of day" is midnight GMT-8 regardless of the
  host clock, so grids, streaks, and date ranges are consistent.

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

No configuration is needed. `.env` is optional and unused — weather/air-quality/pollen
are all keyless.

---

## Project structure

```
app/
  api/          # route modules: health, crud, entries, stats, gamification, export
  models/       # SQLAlchemy models
  services/     # weather, environment (air quality), geocode, pdf, gamification
  static/       # SPA assets (app.js, styles.css)
  templates/    # index.html shell
  db.py         # engine/session/init
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
| GET | `/api/stats/grid` | 365-day activity grid (untracked / good / pain) |
| GET | `/api/stats/trends?start=&end=` | time series for charts (GMT-8 day filter) |
| GET | `/api/gamification` | XP, level, streaks, stability, quests, achievements |
| GET | `/api/export/pdf?start=&end=` | clinical PDF for the selected range |

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

### 2. Move the data (optional — only to keep existing entries)

**On the old host** — export the volume to a tarball:

```bash
docker run --rm \
  -v cranialfaultzone_cranial-data:/data \
  -v "$PWD":/backup \
  alpine tar czf /backup/cranial-data.tar.gz -C /data .
```

**On the new host** — restore it (with the app stopped):

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
image recreates the container but **re-attaches the same volume**, so entries
survive. The only thing that wipes data is `docker compose down -v` (the `-v`
deletes volumes) — never use that to update.

Standard data-safe update, run in the project folder on the host:

```bash
git pull origin main          # get the latest code
docker compose up -d --build  # rebuild image + recreate container, keep the volume
```

`--build` is required because the Python and static files are baked into the image
at build time; it's fast (dependency layers are cached). New tables/seed rows added
by an update (e.g. the `settings` table) are created automatically on startup, and a
lightweight migration adds any new columns to existing tables (e.g. the entry
`end_time`, `is_ongoing`, and `linked_entry_id` fields), so data migrates forward
untouched.

**Optional — snapshot the volume before updating** (lets you roll back):

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

Then a `git pull` is picked up live (uvicorn restarts on Python changes; static
files are served fresh on next load). Trade-off: the running app now depends on the
checked-out files on that host, so keep `--build` for a real production box and
reserve the bind-mount for dev/staging.

### Quick reference

| Goal | Command |
|------|---------|
| Update + keep data (normal) | `git pull && docker compose up -d --build` |
| Back up the DB volume | the `alpine tar` one-liner above |
| Restart without rebuild (no code change) | `docker compose restart` |
| ⚠️ Wipes the database — avoid | `docker compose down -v` |

---

## Notes

- **Port**: maps `8000:8000` — change in `docker-compose.yml` if it's taken.
- **Static assets** are baked into the image; after editing `app/static/*` or
  `app/templates/*`, rebuild (`docker compose up -d --build`). Asset URLs are
  versioned (`?v=N`) and the HTML is served `Cache-Control: no-store` so changes show
  without a hard refresh.
- **Data sources**: Open-Meteo (<https://open-meteo.com>) for weather + air quality;
  pollen.com (IQVIA) for US pollen. Open-Meteo's pollen feed is Europe-only, so US
  pollen is sourced from pollen.com (which exposes an overall index plus active plant
  categories rather than per-species magnitudes).
