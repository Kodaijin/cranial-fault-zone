"""Gamification endpoint: streaks, XP/levels, stability index, quests."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.entries import entry_duration_minutes
from app.db import get_db
from app.models.models import Entry
from app.seed import GOOD_DAY_TYPE_NAME
from app.services.gamification import compute_gamification
from app.tz import to_app_datetime

router = APIRouter(prefix="/api", tags=["gamification"])


@router.get("/gamification")
def gamification(db: Session = Depends(get_db)) -> dict:
    entries = db.scalars(
        select(Entry).options(
            selectinload(Entry.headache_type),
            selectinload(Entry.medications),
            selectinload(Entry.pain_zones),
            selectinload(Entry.location),
        )
    ).all()

    records = []
    for e in entries:
        if not e.timestamp:
            continue
        local = to_app_datetime(e.timestamp)
        is_good = (
            e.headache_type is not None
            and e.headache_type.name == GOOD_DAY_TYPE_NAME
        )
        records.append(
            {
                "ts": e.timestamp,
                "is_good_day": is_good,
                "is_ongoing": bool(e.is_ongoing),
                "duration_minutes": entry_duration_minutes(e),
                "type_name": e.headache_type.name if e.headache_type else None,
                "med_names": [m.name for m in e.medications],
                "zone_names": [z.zone_name for z in e.pain_zones],
                "num_zones": len(e.pain_zones),
                "location": e.location.city_name if e.location else None,
                "has_notes": bool(e.notes and e.notes.strip()),
                "hour": local.hour,
                "weekday": local.weekday(),  # 0 = Monday
            }
        )
    return compute_gamification(records)
