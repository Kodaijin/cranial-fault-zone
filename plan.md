# Cranial Fault Zone — Execution Plan

A self-contained, Dockerized web app for tracking migraines and headaches, with
automated environmental data fetching, gamification, analytics, and a clinical
PDF export. Built incrementally in the phases below. **Do not start a phase until
the previous phase passes its verification checklist.**

## Tech Stack (Locked Decisions)

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Backend | **Python 3.12 + FastAPI** | Async, easy API integration, clean PDF/data tooling |
| ASGI server | Uvicorn | Standard FastAPI runtime |
| Database | **SQLite** via SQLAlchemy 2.x | Zero-config, relational, stored in a Docker volume |
| Migrations | Alembic (or `Base.metadata.create_all` + seed script) | Schema versioning |
| Frontend | **SPA** — vanilla JS + Tailwind CSS (CDN or build step) | Mobile-first, high-contrast dark theme |
| Charts | Chart.js | Trend graphs |
| PDF | ReportLab (or WeasyPrint for HTML→PDF) | Clinical black-and-white layout |
| Container | Dockerfile + docker-compose.yml | One-command local deploy |

> **Model usage convention** (from the blueprint): Haiku handles CRUD/forms/basic
> routing and gamification; Sonnet handles schema design, the activity grid, charts,
> and PDF logic. Opus (this plan) coordinates and owns the external-API integration
> design.

---

## Phase 1 — Project Setup & Dockerization

**Goal:** A running, empty FastAPI app served from a Docker container with a
persisted SQLite volume.

- [ ] Scaffold project structure:
  ```
  /app
    /api          # route modules
    /models       # SQLAlchemy models
    /services     # weather/environment/pdf/gamification logic
    /static       # SPA assets (JS, CSS)
    /templates    # index.html shell
    main.py       # FastAPI app entrypoint
    db.py         # engine/session/init
    seed.py       # default rows (types, locations, pain zones)
  Dockerfile
  docker-compose.yml
  requirements.txt
  .env.example    # API keys (never commit real keys)
  ```
- [ ] `requirements.txt`: fastapi, uvicorn[standard], sqlalchemy, httpx, reportlab, python-dotenv, jinja2.
- [ ] `Dockerfile`: slim Python base, install deps, copy app, expose 8000, run uvicorn.
- [ ] `docker-compose.yml`: build app, map `8000:8000`, mount named volume at `/data` for `cranial.db`, pass env vars.
- [ ] `db.py`: engine pointed at `/data/cranial.db`; create tables on startup if absent.
- [ ] Health-check route `GET /api/health` returning `{"status":"ok"}`.

---

## Phase 2 — Database & Backend Models

**Goal:** Full relational schema + CRUD APIs for all dynamic lists.

- [ ] SQLAlchemy models (see schema below).
- [ ] Seed defaults on first boot:
  - Headache types: Migraine, Migraine w/Aura, IIH Headache, Occipital Neuralgia, Other
  - Locations: Yakima, WA; Portland, OR
  - Pain zones: Left Eye, Right Eye, Forehead, Occipital/Base of Skull, Crown, Left Temple, Right Temple
- [ ] CRUD APIs (Haiku scope):
  - `Headache_Types`, `Medications`, `Locations` — full add/list/delete
  - `Pain_Zones` — list (add optional)
  - `Entries` — create/list/get/delete, including multi-select pain zones and nullable medication
- [ ] Pydantic schemas for request/response validation.

### Schema

```
Entries ───< Entry_Pain_Locations >─── Pain_Zones
   ├──> Headache_Types
   ├──> Medications (nullable)
   └──> Locations
```

- **Headache_Types**: id, name
- **Medications**: id, name, dosage_notes
- **Locations**: id, city_name, state_code
- **Pain_Zones**: id, zone_name
- **Entries**: id, timestamp/date, headache_type_id, duration_minutes (or start/end),
  medication_id (nullable), location_id, weather_data (JSON), environmental_data (JSON), notes
- **Entry_Pain_Locations**: entry_id, pain_zone_id (composite PK → many-to-many)

---

## Phase 3 — External API Integrations

**Goal:** On entry save, auto-fetch weather + environmental data for the entry's location.

- [ ] `services/weather.py` — OpenWeatherMap: temp, **barometric pressure**, humidity, conditions.
- [ ] `services/environment.py` — pollen/mold via Tomorrow.io or Ambee (free tier).
- [ ] Geocode location city/state → lat/lon (OpenWeatherMap geocoding or cached static map for defaults).
- [ ] Use `httpx.AsyncClient` with timeouts; store results as JSON on the entry.
- [ ] **Graceful fallback:** on rate-limit/error/missing key, store `"N/A"` and never block the save.
- [ ] Keys read from env (`OWM_API_KEY`, `AMBEE_API_KEY`); document in `.env.example`.

---

## Phase 4 — Frontend UI Construction

**Goal:** Mobile-first SPA, strict high-contrast dark theme.

- [ ] SPA shell `index.html` + Tailwind; client router (hash-based) for Dashboard / Log Entry / Manage / Reports.
- [ ] **Log Entry form:** date/time, headache type, duration, medication (optional),
      location, **multi-select pain mapping** (checklist or interactive head map), notes.
- [ ] **Manage screen:** add/delete Medications, Locations, Custom Headache Types.
- [ ] Responsive, touch-friendly controls; dark theme with strong contrast for accessibility.
- [ ] Wire all forms to Phase 2/3 APIs; show fetched weather/environment after save.

---

## Phase 5 — Visualization & Gamification Engines

**Goal:** Dashboard with activity grid, trend charts, and the gamification layer.

- [ ] **GitHub-style activity grid** (Sonnet): 365-day heatmap; color intensity = pain frequency/intensity; empty = pain-free.
- [ ] **Trend graphs** (Chart.js): barometric pressure vs. onset; mold/allergy counts vs. onset.
- [ ] **Fault Zone Stability Index:** visual "fault line" that stabilizes with logging, destabilizes when undocumented.
- [ ] **Streak tracking:** consecutive logged days (incl. "No Pain") → XP/levels (Seismic Observer → Tectonic Master).
- [ ] **Quest system:** daily/weekly prompts + retro-game achievement reveals.
- [ ] Backend endpoints: `GET /api/stats/grid`, `GET /api/stats/trends`, `GET /api/gamification`.

---

## Phase 6 — PDF Generation Module

**Goal:** Clean, black-and-white clinical PDF export.

- [ ] `services/pdf.py` (Sonnet) → `GET /api/export/pdf`.
- [ ] Contents: total attacks, most frequent pain locations, medication efficacy summary,
      chronological appendix of all logged notes.
- [ ] High-legibility, print-friendly layout (no dark theme — black text on white).

---

## Verification Checklist (run at the end of each phase)

**Phase 1**
- [ ] `docker compose up` builds and serves; `GET /api/health` returns ok.
- [ ] `cranial.db` persists across container restarts (volume works).

**Phase 2**
- [ ] Defaults seeded exactly once on first boot.
- [ ] CRUD works for types/meds/locations; entries persist with multi-zone selection and nullable medication.

**Phase 3**
- [ ] Saving an entry attaches real weather + environment JSON when keys present.
- [ ] With no/invalid key or rate limit, entry still saves with `"N/A"` data (no crash).

**Phase 4**
- [ ] Layout is usable on a phone-width viewport; dark theme meets high-contrast.
- [ ] Multi-select pain mapping records multiple zones per entry.
- [ ] Manage screen add/delete reflects immediately in form dropdowns.

**Phase 5**
- [ ] Grid renders 365 days with correct intensity coloring and pain-free gaps.
- [ ] Trend charts plot pressure/allergen correlations from real entries.
- [ ] Streak/XP/level and Stability Index update correctly after logging.

**Phase 6**
- [ ] PDF downloads, is black-and-white and legible, and contains all four required sections.

---

## Suggested Build Order

1 → 2 → 3 → 4 → 5 → 6, verifying after each. Phases 3 and 5 can begin partial work
once Phase 2 entries exist. Defer real API keys until Phase 3 (Phases 1–2 need none).
