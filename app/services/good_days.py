"""Auto good-day backfill.

When good_day_mode is "auto", every calendar day from the first logged entry
through *yesterday* that has no entry of its own is filled with an automatically
generated "good day" entry. These rows exist so we capture the same
environmental data (air quality, allergens, weather) we pull for real entries —
historical values are fetched per day.

Today is intentionally left open so a headache logged later in the day is not
pre-empted by a good-day row. Auto rows are flagged (Entry.auto_generated) so a
real entry logged for the same day later can replace them.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, time, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.models import Entry, HeadacheType, Setting
from app.seed import GOOD_DAY_TYPE_NAME
from app.services.environment import fetch_environment_historical, fetch_us_pollen_history
from app.services.geocode import geocode, resolve_zip
from app.services.weather import fetch_weather_historical
from app.tz import APP_TZ, app_today, to_app_date

# Limits how many days are fetched concurrently so a large first backfill does
# not open hundreds of simultaneous HTTP connections.
_MAX_CONCURRENCY = 8

# How far back pollen.com's daily history reaches (~30 days). Existing auto good
# days inside this window are patched with allergens on each run; older ones have
# no US pollen source and stay N/A.
_POLLEN_HISTORY_DAYS = 31


def _loc_key(loc) -> tuple[str, str]:
    return (loc.city_name.lower(), loc.state_code.lower())


def _safe_json(value) -> dict:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    except (ValueError, TypeError):
        return {}


def _apply_pollen(environment: dict, day_pollen: dict | None) -> bool:
    """Merge pollen.com allergens into an environment payload in place.

    Returns True if anything changed. Tags the source with '+pollen.com' once.
    """
    if not day_pollen:
        return False
    environment.update(day_pollen)
    src = environment.get("source") or ""
    if "pollen.com" not in src:
        environment["source"] = f"{src}+pollen.com" if src and src != "N/A" else "pollen.com"
    return True


async def _ensure_pollen(loc, cache: dict) -> dict:
    """Return (and cache) pollen.com's recent history for a location, keyed by
    ISO date. Empty dict if no ZIP resolves or the fetch fails."""
    key = _loc_key(loc)
    if key not in cache:
        zip_code = await resolve_zip(loc.city_name, loc.state_code)
        cache[key] = await fetch_us_pollen_history(zip_code) if zip_code else {}
    return cache[key]


async def fill_good_days(db: Session) -> int:
    """Create auto good-day entries for empty days (first entry → yesterday) and
    backfill allergens onto existing auto good days that still lack them.

    Returns the number of entries created or updated. Safe to call repeatedly:
    days that already have any entry are not recreated, and an auto good day is
    only patched while its allergens are still missing and within pollen range.
    """
    mode_row = db.scalar(select(Setting).where(Setting.key == "good_day_mode"))
    mode = mode_row.value if mode_row is not None else "auto"
    if mode != "auto":
        return 0

    good_type = db.scalar(
        select(HeadacheType).where(HeadacheType.name == GOOD_DAY_TYPE_NAME)
    )
    if good_type is None:
        return 0

    entries = db.scalars(select(Entry).options(selectinload(Entry.location))).all()
    dated = [(to_app_date(e.timestamp), e) for e in entries if e.timestamp]
    if not dated:
        return 0

    first_date = min(d for d, _ in dated)
    existing_dates = {d for d, _ in dated}
    yesterday = app_today() - timedelta(days=1)
    if yesterday < first_date:
        return 0

    # Real entries that carry a location, used to pick each gap day's location.
    located = [(d, e.location) for d, e in dated if e.location is not None]

    def nearest_location(day):
        if not located:
            return None
        return min(located, key=lambda pair: abs((pair[0] - day).days))[1]

    missing = []
    cursor = first_date
    while cursor <= yesterday:
        if cursor not in existing_dates:
            missing.append(cursor)
        cursor += timedelta(days=1)

    # Existing auto good days within the pollen window that still lack allergens.
    # These were created before allergen backfill existed (or before their day
    # was in range); patch them so the charts fill in retroactively.
    pollen_floor = app_today() - timedelta(days=_POLLEN_HISTORY_DAYS)
    patch_targets = [
        (d, e)
        for d, e in dated
        if e.auto_generated
        and e.location is not None
        and d >= pollen_floor
        and _safe_json(e.environmental_data).get("tree_pollen", "N/A") == "N/A"
    ]

    if not missing and not patch_targets:
        return 0

    # Pre-resolve coordinates and recent pollen history for every distinct
    # location once. Open-Meteo has no US pollen, so allergens come from
    # pollen.com's ~30-day history (keyed by ISO date).
    geo_cache: dict[tuple[str, str], tuple] = {}
    pollen_cache: dict[tuple[str, str], dict] = {}
    for _, loc in located:
        key = _loc_key(loc)
        if key not in geo_cache:
            geo_cache[key] = await geocode(loc.city_name, loc.state_code) or (None, None)
        await _ensure_pollen(loc, pollen_cache)

    sem = asyncio.Semaphore(_MAX_CONCURRENCY)

    async def fetch_for(day):
        loc = nearest_location(day)
        if loc is not None:
            key = _loc_key(loc)
            lat, lon = geo_cache.get(key, (None, None))
            city, state = loc.city_name, loc.state_code
        else:
            key = None
            lat = lon = city = state = None
        async with sem:
            weather = await fetch_weather_historical(lat, lon, day)
            environment = await fetch_environment_historical(lat, lon, day, city, state)

        # Overlay allergens from pollen.com history when this day is in range.
        if key is not None:
            _apply_pollen(environment, pollen_cache.get(key, {}).get(day.isoformat()))
        return day, loc, weather, environment

    created = 0
    if missing:
        results = await asyncio.gather(*(fetch_for(day) for day in missing))
        for day, loc, weather, environment in results:
            # Anchor the timestamp at local noon so day bucketing is unambiguous.
            ts = (
                datetime.combine(day, time(12, 0))
                .replace(tzinfo=APP_TZ)
                .astimezone(timezone.utc)
            )
            entry = Entry(
                headache_type_id=good_type.id,
                location_id=loc.id if loc is not None else None,
                weather_data=json.dumps(weather),
                environmental_data=json.dumps(environment),
                auto_generated=True,
            )
            entry.timestamp = ts
            db.add(entry)
        created = len(results)

    # Patch allergens onto existing auto good days now that history is available.
    patched = 0
    for day, entry in patch_targets:
        history = await _ensure_pollen(entry.location, pollen_cache)
        environment = _safe_json(entry.environmental_data)
        if _apply_pollen(environment, history.get(day.isoformat())):
            entry.environmental_data = json.dumps(environment)
            patched += 1

    db.commit()
    return created + patched
