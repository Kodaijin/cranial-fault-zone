"""Settings API: good_day_mode (auto | manual)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.models import HeadacheType, Setting
from app.seed import GOOD_DAY_TYPE_NAME

router = APIRouter(prefix="/api", tags=["settings"])


def good_day_type_id(db: Session) -> int | None:
    """Return the id of the 'Good Day (No Pain)' HeadacheType, or None if missing."""
    ht = db.scalar(select(HeadacheType).where(HeadacheType.name == GOOD_DAY_TYPE_NAME))
    return ht.id if ht is not None else None


class SettingsUpdate(BaseModel):
    good_day_mode: str


@router.get("/settings")
def get_settings(db: Session = Depends(get_db)) -> dict:
    row = db.scalar(select(Setting).where(Setting.key == "good_day_mode"))
    mode = row.value if row is not None else "auto"
    return {"good_day_mode": mode, "good_day_type_id": good_day_type_id(db)}


@router.put("/settings")
def update_settings(payload: SettingsUpdate, db: Session = Depends(get_db)) -> dict:
    if payload.good_day_mode not in ("auto", "manual"):
        raise HTTPException(400, "good_day_mode must be 'auto' or 'manual'")
    row = db.scalar(select(Setting).where(Setting.key == "good_day_mode"))
    if row is None:
        db.add(Setting(key="good_day_mode", value=payload.good_day_mode))
    else:
        row.value = payload.good_day_mode
    db.commit()
    return {"good_day_mode": payload.good_day_mode, "good_day_type_id": good_day_type_id(db)}
