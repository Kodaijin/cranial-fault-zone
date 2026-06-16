"""Statistics endpoints: activity grid + trend data."""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone, date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.models.models import Entry, Setting
from app.seed import GOOD_DAY_TYPE_NAME
from app.tz import app_today, to_app_date

router = APIRouter(prefix="/api/stats", tags=["stats"])


def _build_episodes(pain_entries: list[Entry], today: date) -> list[dict]:
    """Group linked pain entries into episodes (connected components over
    linked_entry_id) and reduce each to a date span.

    Returns dicts: {"start": date, "end": date, "ongoing": bool}. An ongoing
    episode's end is extended to today so the heatmap reflects that it is still
    running.
    """
    by_id = {e.id: e for e in pain_entries}

    # Union-find over the undirected "continues" graph.
    parent: dict[int, int] = {e.id: e.id for e in pain_entries}

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for e in pain_entries:
        if e.linked_entry_id is not None and e.linked_entry_id in by_id:
            union(e.id, e.linked_entry_id)

    groups: dict[int, list[Entry]] = defaultdict(list)
    for e in pain_entries:
        groups[find(e.id)].append(e)

    episodes: list[dict] = []
    for members in groups.values():
        starts = [to_app_date(e.timestamp) for e in members]
        ends = [
            to_app_date(e.end_time) if e.end_time else to_app_date(e.timestamp)
            for e in members
        ]
        ongoing = any(bool(e.is_ongoing) for e in members)
        ep_start = min(starts)
        ep_end = max(ends)
        if ongoing:
            ep_end = max(ep_end, today)
        episodes.append({"start": ep_start, "end": ep_end, "ongoing": ongoing})
    return episodes


@router.get("/grid")
def activity_grid(db: Session = Depends(get_db)) -> dict:
    """365-day heatmap with state: 'untracked' | 'good' | 'pain'.

    Pain entries are grouped into episodes and every day an episode spans is
    filled (not just the onset day). Ongoing episodes run through to today and
    flag their trailing day so the UI can mark them as still going.
    """
    today = app_today()
    start = today - timedelta(days=364)

    # Read the mode setting.
    mode_row = db.scalar(select(Setting).where(Setting.key == "good_day_mode"))
    mode = mode_row.value if mode_row is not None else "auto"

    # Load all entries with headache_type.
    entries = db.scalars(
        select(Entry).options(selectinload(Entry.headache_type))
    ).all()

    # Split entries into pain vs good-day.
    pain_entries: list[Entry] = []
    all_dates: list[date] = []
    good_day_set: set[str] = set()

    for e in entries:
        if not e.timestamp:
            continue
        d = to_app_date(e.timestamp)
        all_dates.append(d)
        is_good = (
            e.headache_type is not None
            and e.headache_type.name == GOOD_DAY_TYPE_NAME
        )
        if is_good:
            good_day_set.add(d.isoformat())
        else:
            pain_entries.append(e)

    first_entry_date = min(all_dates) if all_dates else None

    # Build episodes, then fill every covered day in the window.
    episodes = _build_episodes(pain_entries, today)
    pain_counts: dict[str, int] = defaultdict(int)  # overlapping episodes per day
    ongoing_days: set[str] = set()

    for ep in episodes:
        d = max(ep["start"], start)
        last = min(ep["end"], today)
        while d <= last:
            pain_counts[d.isoformat()] += 1
            d += timedelta(days=1)
        # Mark the episode's trailing day (within window) as still going.
        if ep["ongoing"] and start <= ep["end"] <= today:
            ongoing_days.add(ep["end"].isoformat())

    max_pain_count = max(pain_counts.values(), default=0)

    days = []
    for i in range(365):
        d = start + timedelta(days=i)
        key = d.isoformat()
        pain_count = pain_counts.get(key, 0)
        has_good = key in good_day_set
        tracked = first_entry_date is not None and d >= first_entry_date
        ongoing = key in ongoing_days

        # Determine state. A pain span wins over good/untracked.
        if pain_count > 0:
            state = "pain"
            # 0-4 intensity buckets (GitHub-style).
            if max_pain_count <= 1:
                level = 4
            else:
                level = min(4, 1 + int(3 * (pain_count - 1) / max(1, max_pain_count - 1)))
        elif has_good:
            state = "good"
            level = 0
        elif mode == "auto" and tracked:
            state = "good"
            level = 0
        else:
            state = "untracked"
            level = 0

        days.append({
            "date": key,
            "count": pain_count,
            "level": level,
            "state": state,
            "ongoing": ongoing,
        })

    # Episode bars, clipped to the visible window.
    episode_bars = []
    for ep in sorted(episodes, key=lambda x: x["start"]):
        bar_start = max(ep["start"], start)
        bar_end = min(ep["end"], today)
        if bar_end < start or bar_start > today:
            continue
        episode_bars.append({
            "start": bar_start.isoformat(),
            "end": bar_end.isoformat(),
            "ongoing": ep["ongoing"],
        })

    return {
        "start": start.isoformat(),
        "end": today.isoformat(),
        "days": days,
        "max_count": max_pain_count,
        "episodes": episode_bars,
    }


@router.get("/trends")
def trends(
    db: Session = Depends(get_db),
    start: str | None = Query(default=None),
    end: str | None = Query(default=None),
) -> dict:
    """Barometric pressure vs. onset and allergen/mold counts vs. onset."""
    entries = db.scalars(
        select(Entry)
        .order_by(Entry.timestamp.asc())
        .options(selectinload(Entry.headache_type))
    ).all()

    # Parse and filter by date range; exclude good-day entries.
    start_date = _parse_date(start)
    end_date = _parse_date(end)

    filtered_entries = []
    for e in entries:
        # Skip good-day entries — they are not pain onsets.
        if e.headache_type is not None and e.headache_type.name == GOOD_DAY_TYPE_NAME:
            continue
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
