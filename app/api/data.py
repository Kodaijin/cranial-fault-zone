"""Full-database JSON export/import for moving data between deployments.

Export returns every table as one JSON document the browser downloads. Import
replaces the entire database with that document, preserving primary keys so all
foreign keys (locations, episode links, medication/pain-zone associations)
round-trip exactly. Import is transactional: the file is fully parsed in memory
first, and any failure rolls back so the existing data is left untouched.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.models.models import (
    Entry,
    EntryMedication,
    EntryPainLocation,
    HeadacheType,
    Location,
    Medication,
    PainZone,
    Setting,
)

router = APIRouter(prefix="/api/data", tags=["data"])

# Bump when the export shape changes incompatibly so importers can react.
EXPORT_VERSION = 1


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt is not None else None


def _parse_dt(value) -> datetime | None:
    """Parse an ISO timestamp from the export. Tolerates a trailing 'Z'."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    s = str(value).strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s)


def _build_export(db: Session) -> dict:
    entries = db.scalars(
        select(Entry)
        .order_by(Entry.id.asc())
        .options(selectinload(Entry.medications), selectinload(Entry.pain_zones))
    ).all()
    return {
        "version": EXPORT_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "headache_types": [
            {"id": t.id, "name": t.name}
            for t in db.scalars(select(HeadacheType).order_by(HeadacheType.id)).all()
        ],
        "medications": [
            {"id": m.id, "name": m.name, "dosage_notes": m.dosage_notes}
            for m in db.scalars(select(Medication).order_by(Medication.id)).all()
        ],
        "locations": [
            {"id": loc.id, "city_name": loc.city_name, "state_code": loc.state_code}
            for loc in db.scalars(select(Location).order_by(Location.id)).all()
        ],
        "pain_zones": [
            {"id": z.id, "zone_name": z.zone_name}
            for z in db.scalars(select(PainZone).order_by(PainZone.id)).all()
        ],
        "settings": [
            {"key": s.key, "value": s.value}
            for s in db.scalars(select(Setting)).all()
        ],
        "entries": [
            {
                "id": e.id,
                "timestamp": _iso(e.timestamp),
                "headache_type_id": e.headache_type_id,
                "duration_minutes": e.duration_minutes,
                "end_time": _iso(e.end_time),
                "is_ongoing": bool(e.is_ongoing),
                "auto_generated": bool(e.auto_generated),
                "linked_entry_id": e.linked_entry_id,
                "location_id": e.location_id,
                "weather_data": e.weather_data,
                "environmental_data": e.environmental_data,
                "notes": e.notes,
                "created_at": _iso(e.created_at),
                "medication_ids": sorted(m.id for m in e.medications),
                "pain_zone_ids": sorted(z.id for z in e.pain_zones),
            }
            for e in entries
        ],
    }


@router.get("/export")
def export_data(db: Session = Depends(get_db)):
    """Download the entire database as a single JSON backup file."""
    body = json.dumps(_build_export(db), indent=2)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return Response(
        content=body,
        media_type="application/json",
        headers={
            "Content-Disposition": (
                f"attachment; filename=cranial_fault_zone_backup_{stamp}.json"
            )
        },
    )


@router.post("/import")
def import_data(payload: dict = Body(...), db: Session = Depends(get_db)) -> dict:
    """Replace the entire database with an exported backup file.

    Destructive: every existing row is removed and replaced by the file's
    contents (ids preserved). Parses everything up front so a malformed file is
    rejected before anything is deleted; the swap itself runs in one
    transaction and rolls back on any error.
    """
    if not isinstance(payload, dict) or "entries" not in payload:
        raise HTTPException(400, "Not a valid Cranial Fault Zone backup file")

    # --- Phase 1: parse the whole file into ORM rows (no DB writes yet). ---
    try:
        types = [
            HeadacheType(id=t["id"], name=t["name"])
            for t in payload.get("headache_types", [])
        ]
        meds = [
            Medication(id=m["id"], name=m["name"], dosage_notes=m.get("dosage_notes"))
            for m in payload.get("medications", [])
        ]
        locs = [
            Location(id=loc["id"], city_name=loc["city_name"], state_code=loc["state_code"])
            for loc in payload.get("locations", [])
        ]
        zones = [
            PainZone(id=z["id"], zone_name=z["zone_name"])
            for z in payload.get("pain_zones", [])
        ]
        settings = [
            Setting(key=s["key"], value=s["value"])
            for s in payload.get("settings", [])
        ]

        entries: list[Entry] = []
        assoc_meds: list[dict] = []
        assoc_zones: list[dict] = []
        for e in payload["entries"]:
            ts = _parse_dt(e.get("timestamp"))
            if ts is None:
                raise ValueError(f"entry {e.get('id')} is missing a timestamp")
            entries.append(
                Entry(
                    id=e["id"],
                    timestamp=ts,
                    headache_type_id=e["headache_type_id"],
                    duration_minutes=e.get("duration_minutes"),
                    end_time=_parse_dt(e.get("end_time")),
                    is_ongoing=bool(e.get("is_ongoing", False)),
                    auto_generated=bool(e.get("auto_generated", False)),
                    linked_entry_id=e.get("linked_entry_id"),
                    location_id=e.get("location_id"),
                    weather_data=e.get("weather_data"),
                    environmental_data=e.get("environmental_data"),
                    notes=e.get("notes"),
                    created_at=_parse_dt(e.get("created_at")) or datetime.now(timezone.utc),
                )
            )
            for mid in e.get("medication_ids", []):
                assoc_meds.append({"entry_id": e["id"], "medication_id": mid})
            for zid in e.get("pain_zone_ids", []):
                assoc_zones.append({"entry_id": e["id"], "pain_zone_id": zid})
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(400, f"Malformed backup file: {exc}")

    # --- Phase 2: wipe and re-insert in one transaction. ---
    try:
        # Associations first, then entries, then the reference tables they point to.
        db.execute(delete(EntryMedication))
        db.execute(delete(EntryPainLocation))
        db.execute(delete(Entry))
        db.execute(delete(Setting))
        db.execute(delete(HeadacheType))
        db.execute(delete(Medication))
        db.execute(delete(Location))
        db.execute(delete(PainZone))
        db.flush()

        db.add_all(types + meds + locs + zones + settings)
        db.flush()
        db.add_all(entries)
        db.flush()
        if assoc_meds:
            db.execute(insert(EntryMedication), assoc_meds)
        if assoc_zones:
            db.execute(insert(EntryPainLocation), assoc_zones)
        db.commit()
    except Exception as exc:  # noqa: BLE001 — surface any DB error as a clean 500
        db.rollback()
        raise HTTPException(500, f"Import failed, no changes applied: {exc}")

    return {
        "ok": True,
        "counts": {
            "entries": len(entries),
            "headache_types": len(types),
            "medications": len(meds),
            "locations": len(locs),
            "pain_zones": len(zones),
            "settings": len(settings),
        },
    }
