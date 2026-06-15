"""Gamification engine: streaks, XP/levels, Fault Zone Stability Index, quests.

The conceit: consistent logging "stabilizes the fault zone." Every logged day
(including explicitly pain-free days) builds a streak and earns XP. Gaps in
logging destabilize the fault line.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from app.tz import APP_TZ, app_today, to_app_date

# XP awarded per logged day.
XP_PER_DAY = 10

# Level thresholds (cumulative XP) -> title. Ascending.
LEVELS = [
    (0, "Seismic Observer"),
    (50, "Tremor Tracker"),
    (150, "Fault Surveyor"),
    (350, "Seismologist"),
    (700, "Richter Adept"),
    (1200, "Tectonic Master"),
]


def _to_date(value: datetime | date) -> date:
    if isinstance(value, datetime):
        return to_app_date(value)
    return value


def _level_for_xp(xp: int) -> dict:
    title = LEVELS[0][1]
    level = 1
    next_threshold = None
    for idx, (threshold, name) in enumerate(LEVELS):
        if xp >= threshold:
            title = name
            level = idx + 1
        else:
            next_threshold = threshold
            break
    current_floor = LEVELS[level - 1][0]
    return {
        "level": level,
        "title": title,
        "xp": xp,
        "current_level_floor": current_floor,
        "next_level_xp": next_threshold,
    }


def compute_streak(logged_dates: set[date], today: date) -> int:
    """Count consecutive days with a log ending today or yesterday."""
    if not logged_dates:
        return 0
    # Allow the streak to "still be alive" if today isn't logged yet but
    # yesterday was.
    if today in logged_dates:
        cursor = today
    elif (today - timedelta(days=1)) in logged_dates:
        cursor = today - timedelta(days=1)
    else:
        return 0

    streak = 0
    while cursor in logged_dates:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def compute_gamification(entry_dates: list[datetime | date], today: date | None = None) -> dict:
    """Build the full gamification payload from the dates entries were logged."""
    today = today or app_today()
    logged_dates = {_to_date(d) for d in entry_dates}

    total_logged_days = len(logged_dates)
    xp = total_logged_days * XP_PER_DAY
    streak = compute_streak(logged_dates, today)
    longest = _longest_streak(logged_dates)
    level_info = _level_for_xp(xp)

    # Fault Zone Stability Index (0-100): rewards recent logging consistency over
    # the last 30 days; gaps destabilize it.
    window = 30
    recent_logged = sum(
        1 for i in range(window) if (today - timedelta(days=i)) in logged_dates
    )
    stability = round(100 * recent_logged / window)

    return {
        "xp": xp,
        "level": level_info["level"],
        "title": level_info["title"],
        "next_level_xp": level_info["next_level_xp"],
        "current_level_floor": level_info["current_level_floor"],
        "current_streak": streak,
        "longest_streak": longest,
        "total_logged_days": total_logged_days,
        "stability_index": stability,
        "stability_state": _stability_state(stability),
        "quests": _build_quests(streak, total_logged_days, today in logged_dates),
        "achievements": _build_achievements(streak, longest, total_logged_days, level_info["level"]),
    }


def _longest_streak(logged_dates: set[date]) -> int:
    if not logged_dates:
        return 0
    longest = 0
    for d in logged_dates:
        # Only start counting from the beginning of a run.
        if (d - timedelta(days=1)) in logged_dates:
            continue
        length = 0
        cursor = d
        while cursor in logged_dates:
            length += 1
            cursor += timedelta(days=1)
        longest = max(longest, length)
    return longest


def _stability_state(index: int) -> str:
    if index >= 80:
        return "Stable"
    if index >= 50:
        return "Settling"
    if index >= 20:
        return "Fracturing"
    return "Critical"


def _build_quests(streak: int, total_days: int, logged_today: bool) -> list[dict]:
    return [
        {
            "id": "daily_log",
            "scope": "daily",
            "title": "Log today's status",
            "description": "Record a headache entry or a pain-free day.",
            "complete": logged_today,
        },
        {
            "id": "weekly_streak",
            "scope": "weekly",
            "title": "Hold a 7-day streak",
            "description": "Log every day for a week to reinforce the fault line.",
            "progress": min(streak, 7),
            "target": 7,
            "complete": streak >= 7,
        },
        {
            "id": "foundation",
            "scope": "milestone",
            "title": "Lay the foundation",
            "description": "Log 30 total days.",
            "progress": min(total_days, 30),
            "target": 30,
            "complete": total_days >= 30,
        },
    ]


def _build_achievements(streak: int, longest: int, total_days: int, level: int) -> list[dict]:
    defs = [
        ("first_tremor", "First Tremor", "Log your first day.", total_days >= 1),
        ("week_warrior", "Week Warrior", "Reach a 7-day streak.", longest >= 7),
        ("fortnight", "Fortnight of Faith", "Reach a 14-day streak.", longest >= 14),
        ("monthly_master", "Monthly Master", "Log 30 total days.", total_days >= 30),
        ("tectonic", "Tectonic Master", "Reach the top level.", level >= len(LEVELS)),
    ]
    return [
        {"id": i, "title": t, "description": d, "unlocked": bool(u)}
        for (i, t, d, u) in defs
    ]
