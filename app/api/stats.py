"""Statistics endpoints: activity grid + trend data."""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone, date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.models.models import Entry
from app.tz import app_today, to_app_date

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/grid")
def activity_grid(db: Session = Depends(get_db)) -> dict:
    """365-day heatmap. intensity = number of entries that day (0 = pain-free)."""
    today = app_today()
    start = today - timedelta(days=364)

    entries = db.scalars(select(Entry)).all()
    counts: dict[str, int] = defaultdict(int)
    entry_dates = [to_app_date(e.timestamp) for e in entries if e.timestamp]
    for d in entry_dates:
        if start <= d <= today:
            counts[d.isoformat()] += 1

    # "Good" (green) days only count from the first entry forward; days before
    # tracking began (or when there are no entries at all) are untracked.
    first_entry_date = min(entry_dates) if entry_dates else None

    max_count = max(counts.values(), default=0)
    days = []
    for i in range(365):
        d = start + timedelta(days=i)
        key = d.isoformat()
        count = counts.get(key, 0)
        tracked = first_entry_date is not None and d >= first_entry_date
        # 0-4 intensity buckets (GitHub-style); 0 = no pain that day.
        if count == 0:
            level = 0
        elif max_count <= 1:
            level = 4
        else:
            level = min(4, 1 + int(3 * (count - 1) / max(1, max_count - 1)))
        days.append({"date": key, "count": count, "level": level,
                     "tracked": tracked})

    return {"start": start.isoformat(), "end": today.isoformat(), "days": days,
            "max_count": max_count}


@router.get("/trends")
def trends(
    db: Session = Depends(get_db),
    start: str | None = Query(default=None),
    end: str | None = Query(default=None),
) -> dict:
    """Barometric pressure vs. onset and allergen/mold counts vs. onset."""
    entries = db.scalars(
        select(Entry).order_by(Entry.timestamp.asc())
    ).all()

    # Parse and filter by date range
    start_date = _parse_date(start)
    end_date = _parse_date(end)

    filtered_entries = []
    for e in entries:
        if e.timestamp:
            entry_date = to_app_date(e.timestamp)
            if start_date and entry_date < start_date:
                continue
            if end_date and entry_date > end_date:
                continue
        filtered_entries.append(e)

    points = []
    for e in filtered_entries:
        weather = _load(e.weather_data)
        env = _load(e.environmental_data)
        points.append(
            {
                "date": e.timestamp.isoformat() if e.timestamp else None,
                "pressure_hpa": _num(weather.get("pressure_hpa")),
                "humidity_pct": _num(weather.get("humidity_pct")),
                "temp_c": _num(weather.get("temp_c")),
                "pm2_5": _num(env.get("pm2_5")),
                "pm10": _num(env.get("pm10")),
                "ozone": _num(env.get("ozone")),
                "carbon_monoxide": _num(env.get("carbon_monoxide")),
                "nitrogen_dioxide": _num(env.get("nitrogen_dioxide")),
                "nitrogen_monoxide": _num(env.get("nitrogen_monoxide")),
                "sulphur_dioxide": _num(env.get("sulphur_dioxide")),
                "nitrogen_oxides": _num(env.get("nitrogen_oxides")),
                "tree_pollen": _num(env.get("tree_pollen")),
                "grass_pollen": _num(env.get("grass_pollen")),
                "weed_pollen": _num(env.get("weed_pollen")),
            }
        )
    return {"points": points}


def _load(value: str | None) -> dict:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    except (ValueError, TypeError):
        return {}


def _num(value):
    """Return a float for plotting, or None for 'N/A'/non-numeric values."""
    if value is None or value == "N/A":
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _parse_date(s: str | None) -> date | None:
    """Parse a YYYY-MM-DD date string. Return None for invalid/missing input."""
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None
