"""Gamification endpoint: streaks, XP/levels, stability index, quests."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.models import Entry
from app.services.gamification import compute_gamification

router = APIRouter(prefix="/api", tags=["gamification"])


@router.get("/gamification")
def gamification(db: Session = Depends(get_db)) -> dict:
    dates = [e.timestamp for e in db.scalars(select(Entry)).all() if e.timestamp]
    return compute_gamification(dates)
