"""Auto good-day fill endpoint.

The frontend calls this once on app open; it backfills any missing days (first
entry → yesterday) with auto-generated good-day entries when good_day_mode is
"auto". See app.services.good_days for the logic.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.good_days import fill_good_days

router = APIRouter(prefix="/api", tags=["good_days"])


@router.post("/good_days/fill")
async def fill(db: Session = Depends(get_db)) -> dict:
    created = await fill_good_days(db)
    return {"created": created}
