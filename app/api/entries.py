"""Entry CRUD. On create, auto-fetches weather + environmental data for the
entry's location with graceful fallback (never blocks the save)."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.models.models import Entry, HeadacheType, Location, Medication, PainZone
from app.schemas import EntryCreate, EntryOut
from app.seed import GOOD_DAY_TYPE_NAME
from app.services.environment import fetch_environment
from app.services.geocode import geocode
from app.services.weather import fetch_weather
from app.tz import to_app_date

router = APIRouter(prefix="/api", tags=["entries"])


def _parse_json(value: str | None):
    if not value:
        return None
    try:
        return json.loads(value)
    except (ValueError, TypeError):
        return value


def entry_duration_minutes(entry: Entry) -> int | None:
    """Derived headache duration: minutes between timestamp and end_time, falling
    back to the legacy duration_minutes column when no end_time is recorded."""
    if entry.end_time is not None and entry.timestamp is not None:
        delta = entry.end_time - entry.timestamp
        return max(0, round(delta.total_seconds() / 60))
    return entry.duration_minutes


def serialize_entry(entry: Entry) -> dict:
    """Build an EntryOut-shaped dict, parsing the stored JSON text fields."""
    is_good_day = (
        entry.headache_type is not None
        and entry.headache_type.name == GOOD_DAY_TYPE_NAME
    )
    return {
        "id": entry.id,
        "timestamp": entry.timestamp,
        "headache_type": entry.headache_type,
        "end_time": entry.end_time,
        "is_ongoing": entry.is_ongoing,
        "linked_entry_id": entry.linked_entry_id,
        "duration_minutes": entry_duration_minutes(entry),
        "medications": entry.medications,
        "location": entry.location,
        "pain_zones": entry.pain_zones,
        "weather_data": _parse_json(entry.weather_data),
        "environmental_data": _parse_json(entry.environmental_data),
        "notes": entry.notes,
        "created_at": entry.created_at,
        "is_good_day": is_good_day,
        "auto_generated": bool(entry.auto_generated),
    }


def _load_entry(db: Session, entry_id: int) -> Entry | None:
    return db.scalar(
        select(Entry)
        .where(Entry.id == entry_id)
        .options(
            selectinload(Entry.headache_type),
            selectinload(Entry.medications),
            selectinload(Entry.location),
            selectinload(Entry.pain_zones),
        )
    )


def _remove_auto_good_days_on_date(db: Session, timestamp: datetime | None) -> None:
    """Delete any auto-generated good-day placeholder sharing this entry's local
    day, so a real (or manually logged) entry replaces the filler for that day."""
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)
    target = to_app_date(timestamp)
    autos = db.scalars(select(Entry).where(Entry.auto_generated.is_(True))).all()
    for e in autos:
        if e.timestamp is not None and to_app_date(e.timestamp) == target:
            db.delete(e)


def _get_good_day_type(db: Session) -> HeadacheType:
    """Return the Good Day HeadacheType or raise 500 if missing."""
    ht = db.scalar(select(HeadacheType).where(HeadacheType.name == GOOD_DAY_TYPE_NAME))
    if ht is None:
        raise HTTPException(500, "Good Day type not found in database")
    return ht


def _resolve_episode_fields(
    db: Session, payload: EntryCreate, entry_id: int | None = None
) -> tuple:
    """Normalize and validate (end_time, is_ongoing, linked_entry_id) for a pain
    entry. Returns the values to persist.

    - A real end_time always clears the ongoing flag.
    - An ongoing entry with no end_time gets 23:59 of its onset day (defensive;
      the UI sets this too).
    - linked_entry_id must reference an existing, non-good-day, different entry.
    """
    end_time = payload.end_time
    is_ongoing = payload.is_ongoing
    if end_time is not None:
        is_ongoing = False
    elif is_ongoing:
        onset = payload.timestamp or datetime.now(timezone.utc)
        end_time = onset.replace(hour=23, minute=59, second=0, microsecond=0)

    link_id = payload.linked_entry_id
    if link_id is not None:
        if entry_id is not None and link_id == entry_id:
            raise HTTPException(400, "An entry cannot be linked to itself")
        linked = _load_entry(db, link_id)
        if linked is None:
            raise HTTPException(400, "Invalid linked_entry_id")
        if (
            linked.headache_type is not None
            and linked.headache_type.name == GOOD_DAY_TYPE_NAME
        ):
            raise HTTPException(400, "Cannot link to a good-day entry")

    return end_time, is_ongoing, link_id


@router.get("/entries", response_model=list[EntryOut])
def list_entries(db: Session = Depends(get_db)):
    entries = db.scalars(
        select(Entry)
        .order_by(Entry.timestamp.desc())
        .options(
            selectinload(Entry.headache_type),
            selectinload(Entry.medications),
            selectinload(Entry.location),
            selectinload(Entry.pain_zones),
        )
    ).all()
    return [serialize_entry(e) for e in entries]


@router.get("/entries/{entry_id}", response_model=EntryOut)
def get_entry(entry_id: int, db: Session = Depends(get_db)):
    entry = _load_entry(db, entry_id)
    if entry is None:
        raise HTTPException(404, "Entry not found")
    return serialize_entry(entry)


@router.post("/entries", response_model=EntryOut, status_code=201)
async def create_entry(payload: EntryCreate, db: Session = Depends(get_db)):
    if payload.is_good_day:
        # Good day: override headache type to the special good-day type,
        # clear pain zones and medications.
        htype = _get_good_day_type(db)
        meds = []
        zones = []

        # Still honor location for weather/env fetch.
        location = None
        if payload.location_id is not None:
            location = db.get(Location, payload.location_id)
            if location is None:
                raise HTTPException(400, "Invalid location_id")

        weather = {"temp_c": "N/A", "pressure_hpa": "N/A", "humidity_pct": "N/A",
                   "conditions": "N/A", "source": "N/A"}
        environment = {"pm2_5": "N/A", "pm10": "N/A", "ozone": "N/A",
                       "tree_pollen": "N/A", "grass_pollen": "N/A",
                       "weed_pollen": "N/A", "source": "N/A"}
        if location is not None:
            coords = await geocode(location.city_name, location.state_code)
            lat, lon = coords if coords else (None, None)
            weather = await fetch_weather(lat, lon)
            environment = await fetch_environment(lat, lon, location.city_name, location.state_code)

        # Good days carry no episode fields (end time / ongoing / link).
        entry = Entry(
            headache_type_id=htype.id,
            location_id=payload.location_id,
            notes=payload.notes,
            weather_data=json.dumps(weather),
            environmental_data=json.dumps(environment),
            medications=[],
            pain_zones=[],
        )
        if payload.timestamp is not None:
            entry.timestamp = payload.timestamp

        # A manually logged good day replaces any auto placeholder for that day.
        _remove_auto_good_days_on_date(db, payload.timestamp)
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return serialize_entry(_load_entry(db, entry.id))

    # Normal (pain) entry path.
    if payload.headache_type_id is None:
        raise HTTPException(400, "headache_type_id is required")

    htype = db.get(HeadacheType, payload.headache_type_id)
    if htype is None:
        raise HTTPException(400, "Invalid headache_type_id")

    meds = []
    if payload.medication_ids:
        meds = db.scalars(
            select(Medication).where(Medication.id.in_(payload.medication_ids))
        ).all()
        found = {m.id for m in meds}
        missing = set(payload.medication_ids) - found
        if missing:
            raise HTTPException(400, f"Invalid medication_ids: {sorted(missing)}")

    location = None
    if payload.location_id is not None:
        location = db.get(Location, payload.location_id)
        if location is None:
            raise HTTPException(400, "Invalid location_id")

    zones = []
    if payload.pain_zone_ids:
        zones = db.scalars(
            select(PainZone).where(PainZone.id.in_(payload.pain_zone_ids))
        ).all()
        found = {z.id for z in zones}
        missing = set(payload.pain_zone_ids) - found
        if missing:
            raise HTTPException(400, f"Invalid pain_zone_ids: {sorted(missing)}")

    # Fetch external data (graceful fallback to N/A; never raises).
    weather = {"temp_c": "N/A", "pressure_hpa": "N/A", "humidity_pct": "N/A",
               "conditions": "N/A", "source": "N/A"}
    environment = {"pm2_5": "N/A", "pm10": "N/A", "ozone": "N/A",
                   "tree_pollen": "N/A", "grass_pollen": "N/A",
                   "weed_pollen": "N/A", "source": "N/A"}
    if location is not None:
        coords = await geocode(location.city_name, location.state_code)
        lat, lon = coords if coords else (None, None)
        weather = await fetch_weather(lat, lon)
        environment = await fetch_environment(lat, lon, location.city_name, location.state_code)

    end_time, is_ongoing, link_id = _resolve_episode_fields(db, payload)

    entry = Entry(
        headache_type_id=payload.headache_type_id,
        end_time=end_time,
        is_ongoing=is_ongoing,
        linked_entry_id=link_id,
        location_id=payload.location_id,
        notes=payload.notes,
        weather_data=json.dumps(weather),
        environmental_data=json.dumps(environment),
        medications=list(meds),
        pain_zones=list(zones),
    )
    if payload.timestamp is not None:
        entry.timestamp = payload.timestamp

    # A real pain entry replaces any auto good-day placeholder for that day.
    _remove_auto_good_days_on_date(db, payload.timestamp)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return serialize_entry(_load_entry(db, entry.id))


@router.put("/entries/{entry_id}", response_model=EntryOut)
async def update_entry(entry_id: int, payload: EntryCreate, db: Session = Depends(get_db)):
    # Load the entry; raise 404 if missing.
    entry = _load_entry(db, entry_id)
    if entry is None:
        raise HTTPException(404, "Entry not found")

    if payload.is_good_day:
        # Good day update: set the good-day type, clear zones/meds.
        htype = _get_good_day_type(db)
        entry.headache_type_id = htype.id
        entry.location_id = payload.location_id
        entry.notes = payload.notes
        entry.medications = []
        entry.pain_zones = []
        # Converting to a good day clears any episode fields.
        entry.end_time = None
        entry.is_ongoing = False
        entry.linked_entry_id = None
        if payload.timestamp is not None:
            entry.timestamp = payload.timestamp
        # Preserve weather_data and environmental_data (do NOT refetch).
        db.commit()
        return serialize_entry(_load_entry(db, entry_id))

    # Normal (pain) entry update.
    if payload.headache_type_id is None:
        raise HTTPException(400, "headache_type_id is required")

    htype = db.get(HeadacheType, payload.headache_type_id)
    if htype is None:
        raise HTTPException(400, "Invalid headache_type_id")

    meds = []
    if payload.medication_ids:
        meds = db.scalars(
            select(Medication).where(Medication.id.in_(payload.medication_ids))
        ).all()
        found = {m.id for m in meds}
        missing = set(payload.medication_ids) - found
        if missing:
            raise HTTPException(400, f"Invalid medication_ids: {sorted(missing)}")

    location = None
    if payload.location_id is not None:
        location = db.get(Location, payload.location_id)
        if location is None:
            raise HTTPException(400, "Invalid location_id")

    zones = []
    if payload.pain_zone_ids:
        zones = db.scalars(
            select(PainZone).where(PainZone.id.in_(payload.pain_zone_ids))
        ).all()
        found = {z.id for z in zones}
        missing = set(payload.pain_zone_ids) - found
        if missing:
            raise HTTPException(400, f"Invalid pain_zone_ids: {sorted(missing)}")

    end_time, is_ongoing, link_id = _resolve_episode_fields(db, payload, entry_id)

    # Update entry fields.
    entry.headache_type_id = payload.headache_type_id
    entry.end_time = end_time
    entry.is_ongoing = is_ongoing
    entry.linked_entry_id = link_id
    entry.location_id = payload.location_id
    entry.notes = payload.notes
    entry.medications = list(meds)
    entry.pain_zones = list(zones)
    if payload.timestamp is not None:
        entry.timestamp = payload.timestamp

    # Preserve weather_data and environmental_data (do NOT refetch).

    db.commit()
    return serialize_entry(_load_entry(db, entry_id))


@router.delete("/entries/{entry_id}", status_code=204)
def delete_entry(entry_id: int, db: Session = Depends(get_db)):
    entry = db.get(Entry, entry_id)
    if entry is None:
        raise HTTPException(404, "Entry not found")
    db.delete(entry)
    db.commit()
