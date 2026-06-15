"""Entry CRUD. On create, auto-fetches weather + environmental data for the
entry's location with graceful fallback (never blocks the save)."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.models.models import Entry, HeadacheType, Location, Medication, PainZone
from app.schemas import EntryCreate, EntryOut
from app.services.environment import fetch_environment
from app.services.geocode import geocode
from app.services.weather import fetch_weather

router = APIRouter(prefix="/api", tags=["entries"])


def _parse_json(value: str | None):
    if not value:
        return None
    try:
        return json.loads(value)
    except (ValueError, TypeError):
        return value


def serialize_entry(entry: Entry) -> dict:
    """Build an EntryOut-shaped dict, parsing the stored JSON text fields."""
    return {
        "id": entry.id,
        "timestamp": entry.timestamp,
        "headache_type": entry.headache_type,
        "duration_minutes": entry.duration_minutes,
        "medications": entry.medications,
        "location": entry.location,
        "pain_zones": entry.pain_zones,
        "weather_data": _parse_json(entry.weather_data),
        "environmental_data": _parse_json(entry.environmental_data),
        "notes": entry.notes,
        "created_at": entry.created_at,
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
    # Validate foreign keys.
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

    entry = Entry(
        headache_type_id=payload.headache_type_id,
        duration_minutes=payload.duration_minutes,
        location_id=payload.location_id,
        notes=payload.notes,
        weather_data=json.dumps(weather),
        environmental_data=json.dumps(environment),
        medications=list(meds),
        pain_zones=list(zones),
    )
    if payload.timestamp is not None:
        entry.timestamp = payload.timestamp

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

    # Validate foreign keys (same patterns as create_entry).
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

    # Update entry fields.
    entry.headache_type_id = payload.headache_type_id
    entry.duration_minutes = payload.duration_minutes
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
