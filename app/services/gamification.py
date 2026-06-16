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


def compute_gamification(records: list, today: date | None = None) -> dict:
    """Build the full gamification payload from per-entry records.

    Each record is a dict with: ts (datetime), is_good_day, is_ongoing,
    duration_minutes, med_names (list), num_zones, hour (local), weekday (local,
    0=Mon). For backward compatibility a list of bare datetimes/dates is also
    accepted (treated as undifferentiated logged days).
    """
    today = today or app_today()
    records = [_normalize_record(r) for r in records]

    logged_dates = {r["date"] for r in records}
    pain_dates = {r["date"] for r in records if not r["is_good_day"]}
    # A day only counts as "good" if nothing painful was logged that day.
    good_dates = {r["date"] for r in records if r["is_good_day"]} - pain_dates

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

    pain_records = [r for r in records if not r["is_good_day"]]

    # Richer stats that power the cheeky quests/achievements.
    stats = {
        "total_logged_days": total_logged_days,
        "total_entries": len(records),
        "total_pain_days": len(pain_dates),
        "total_good_days": len(good_dates),
        "streak": streak,
        "longest_streak": longest,
        "max_pain_run": _max_run(pain_dates),
        "max_good_run": _max_run(good_dates),
        "distinct_meds": len({m for r in records for m in r["med_names"]}),
        "max_meds_single": max((len(r["med_names"]) for r in records), default=0),
        "distinct_types": len({r["type_name"] for r in pain_records if r["type_name"]}),
        "distinct_zones": len({z for r in records for z in r["zone_names"]}),
        "max_zones_single": max((r["num_zones"] for r in records), default=0),
        "distinct_locations": len({r["location"] for r in records if r["location"]}),
        "notes_count": sum(1 for r in records if r["has_notes"]),
        "weekdays_covered": len({r["weekday"] for r in records}),
        "longest_minutes": max((r["duration_minutes"] or 0 for r in records), default=0),
        "cumulative_minutes": sum(r["duration_minutes"] or 0 for r in pain_records),
        "has_ongoing": any(r["is_ongoing"] for r in records),
        "has_night_owl": any(0 <= r["hour"] <= 4 for r in pain_records),
        "has_early_bird": any(r["hour"] < 9 for r in records),
        "has_dawn": any(5 <= r["hour"] <= 7 for r in records),
        "has_midday": any(11 <= r["hour"] <= 13 for r in pain_records),
        "has_midnight": any(r["hour"] == 0 for r in pain_records),
        "has_evening_pain": any(18 <= r["hour"] <= 21 for r in pain_records),
        "has_monday_pain": any(r["weekday"] == 0 for r in pain_records),
        "has_friday_pain": any(r["weekday"] == 4 for r in pain_records),
        "has_weekend_pain": any(r["weekday"] >= 5 for r in pain_records),
        "has_weekend_good": any(r["weekday"] >= 5 for r in records if r["is_good_day"]),
        "has_comeback": any((d - timedelta(days=1)) in pain_dates for d in good_dates),
        "has_notes_entry": any(r["has_notes"] for r in records),
        "level": level_info["level"],
        "logged_today": today in logged_dates,
    }

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
        "quests": _build_quests(stats),
        "achievements": _build_achievements(stats),
    }


def _normalize_record(r) -> dict:
    """Coerce a record into the canonical dict, tolerating bare date/datetime."""
    if isinstance(r, (datetime, date)):
        r = {"ts": r}
    return {
        "date": _to_date(r["ts"]),
        "is_good_day": bool(r.get("is_good_day", False)),
        "is_ongoing": bool(r.get("is_ongoing", False)),
        "duration_minutes": r.get("duration_minutes"),
        "type_name": r.get("type_name"),
        "med_names": list(r.get("med_names", [])),
        "zone_names": list(r.get("zone_names", [])),
        "num_zones": int(r.get("num_zones", 0)),
        "location": r.get("location"),
        "has_notes": bool(r.get("has_notes", False)),
        "hour": int(r.get("hour", 12)),
        "weekday": int(r.get("weekday", 0)),
    }


def _max_run(dates: set[date]) -> int:
    """Longest run of consecutive calendar days present in `dates`."""
    if not dates:
        return 0
    longest = 0
    for d in dates:
        if (d - timedelta(days=1)) in dates:
            continue  # not the start of a run
        length = 0
        cursor = d
        while cursor in dates:
            length += 1
            cursor += timedelta(days=1)
        longest = max(longest, length)
    return longest


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


def _quest(qid, scope, title, desc, progress, target, complete) -> dict:
    """Quest with a progress bar. `progress`/`target` drive the bar UI."""
    q = {"id": qid, "scope": scope, "title": title, "description": desc, "complete": complete}
    if target is not None:
        q["progress"] = min(progress, target)
        q["target"] = target
    return q


def _build_quests(s: dict) -> list[dict]:
    streak = s["streak"]
    longest = s["longest_streak"]
    total = s["total_logged_days"]
    entries = s["total_entries"]
    weekend = s["has_weekend_pain"] or s["has_weekend_good"]
    # (id, scope, title, description, progress, target, complete)
    defs = [
        # ── Daily / weekly ──────────────────────────────────────────
        ("daily_log", "daily", "Check in with the fault line",
         "Log a headache or a pain-free day today.",
         int(s["logged_today"]), None, s["logged_today"]),
        ("weekly_streak", "weekly", "Hold a 7-day streak",
         "Log every day for a week to reinforce the fault line.",
         streak, 7, streak >= 7),
        ("comeback_tour", "weekly", "Stage a comeback",
         "Bounce back with a good day right after a rough one.",
         int(s["has_comeback"]), None, s["has_comeback"]),
        ("weekend_checkin", "weekly", "Don't ghost the weekend",
         "Log at least one weekend day.",
         int(weekend), None, weekend),
        ("note_taker", "weekly", "Show your work",
         "Add notes to 3 entries — context is king.",
         s["notes_count"], 3, s["notes_count"] >= 3),

        # ── Total-day milestones ────────────────────────────────────
        ("foundation", "milestone", "Lay the foundation",
         "Log 30 total days.", total, 30, total >= 30),
        ("pillar", "milestone", "Pillar of the community",
         "Log 50 total days.", total, 50, total >= 50),
        ("centurion_quest", "milestone", "The big 1-0-0",
         "Log 100 total days. Your fault line salutes you.",
         total, 100, total >= 100),
        ("double_century_quest", "milestone", "Double century",
         "Log 200 total days. Commitment.", total, 200, total >= 200),
        ("year_one_quest", "milestone", "A year in tremors",
         "Log 365 total days. A full trip around the sun.",
         total, 365, total >= 365),

        # ── Streak milestones ───────────────────────────────────────
        ("two_week_titan", "milestone", "Two-Week Titan",
         "Stretch your logging streak to 14 days.", longest, 14, longest >= 14),
        ("habit_formed", "milestone", "21 and unbreakable",
         "Hit a 21-day streak — officially a habit.", longest, 21, longest >= 21),
        ("streak_of_titans", "milestone", "Streak of the month",
         "Reach a 30-day logging streak.", longest, 30, longest >= 30),
        ("iron_will", "milestone", "Iron will",
         "Reach a 50-day logging streak.", longest, 50, longest >= 50),

        # ── Good-day runs ───────────────────────────────────────────
        ("calm_three", "milestone", "Three days of calm",
         "String together 3 good days in a row.", s["max_good_run"], 3, s["max_good_run"] >= 3),
        ("calm_week", "milestone", "A weather-free week",
         "String together 7 good days in a row.", s["max_good_run"], 7, s["max_good_run"] >= 7),
        ("calm_fortnight", "milestone", "Fortnight of zen",
         "String together 14 good days in a row.", s["max_good_run"], 14, s["max_good_run"] >= 14),

        # ── Variety / collection ────────────────────────────────────
        ("variety_pack", "milestone", "Variety pack",
         "Track 3 different medications.", s["distinct_meds"], 3, s["distinct_meds"] >= 3),
        ("apothecary", "milestone", "Apothecary",
         "Track 5 different medications.", s["distinct_meds"], 5, s["distinct_meds"] >= 5),
        ("cartographer_quest", "milestone", "Map the pain",
         "Log 5 different pain zones.", s["distinct_zones"], 5, s["distinct_zones"] >= 5),
        ("know_enemy_quest", "milestone", "Know your enemy",
         "Log 3 different headache types.", s["distinct_types"], 3, s["distinct_types"] >= 3),

        # ── Volume ──────────────────────────────────────────────────
        ("scribe_quest", "milestone", "Dear diary",
         "Add notes to 10 entries.", s["notes_count"], 10, s["notes_count"] >= 10),
        ("data_entry", "milestone", "Data-entry specialist",
         "Record 50 total entries.", entries, 50, entries >= 50),
        ("power_user_quest", "milestone", "Power user",
         "Record 100 total entries.", entries, 100, entries >= 100),
    ]
    return [_quest(qid, scope, title, desc, prog, tgt, comp)
            for (qid, scope, title, desc, prog, tgt, comp) in defs]


def _build_achievements(s: dict) -> list[dict]:
    total = s["total_logged_days"]
    entries = s["total_entries"]
    longest = s["longest_streak"]
    # (id, title, description, unlocked)
    defs = [
        # ── Total-day milestones ─────────────────────────────────────
        ("first_tremor", "First Tremor", "Log your very first day. It begins.", total >= 1),
        ("getting_the_hang", "Getting the Hang of It", "Log 3 total days.", total >= 3),
        ("monthly_master", "Monthly Master", "Log 30 total days.", total >= 30),
        ("fifty_club", "The Fifty Club", "Log 50 total days. Membership has its downsides.", total >= 50),
        ("centurion", "Centurion", "Log 100 total days. Absolute unit.", total >= 100),
        ("sesqui", "Sesquicenturion", "Log 150 total days. Yes, that's a real word.", total >= 150),
        ("double_century", "Double Century", "Log 200 total days. Cricket fans rejoice.", total >= 200),
        ("year_of_faults", "A Full Year of Faults", "Log 365 total days. One whole orbit.", total >= 365),

        # ── Logging-streak milestones ────────────────────────────────
        ("week_warrior", "Week Warrior", "Reach a 7-day logging streak.", longest >= 7),
        ("fortnight", "Fortnight of Faith", "Reach a 14-day logging streak.", longest >= 14),
        ("habit_formed", "21-Day Habit", "Reach a 21-day streak. Science says it's a habit now.", longest >= 21),
        ("streak_titan", "Streak of the Titans", "Reach a 30-day logging streak.", longest >= 30),
        ("unstoppable", "Unstoppable", "Reach a 50-day logging streak.", longest >= 50),
        ("hundred_day_monk", "100-Day Monk", "Reach a 100-day streak. Inner peace unlocked.", longest >= 100),

        # ── Good-day runs (wholesome) ────────────────────────────────
        ("clear_skies", "Clear Skies", "Three good days in a row. Breathe it in.", s["max_good_run"] >= 3),
        ("serenity_now", "Serenity Now", "Seven good days in a row. Suspiciously calm.", s["max_good_run"] >= 7),
        ("certified_zen", "Certified Zen Master", "Fourteen good days in a row. Who ARE you?", s["max_good_run"] >= 14),
        ("fully_enlightened", "Fully Enlightened", "Thirty good days in a row. Ascend.", s["max_good_run"] >= 30),
        ("weekend_off", "Weekend Off", "Log a good day on a weekend. As nature intended.", s["has_weekend_good"]),
        ("ray_of_sunshine", "A Ray of Sunshine", "Log your first good day.", s["total_good_days"] >= 1),
        ("fair_weather_fan", "Fair-Weather Fan", "Rack up 30 good days total.", s["total_good_days"] >= 30),
        ("mostly_sunny", "Mostly Sunny", "Have more good days than bad (and at least 10 good).",
         s["total_good_days"] >= 10 and s["total_good_days"] >= s["total_pain_days"]),

        # ── Pain-run commiseration (cheeky) ──────────────────────────
        ("and_so_it_begins", "And So It Begins", "Log your first painful day. We're with you.", s["total_pain_days"] >= 1),
        ("hat_trick", "Hat Trick of Hurt", "Three bad days in a row. Brutal. We see you.", s["max_pain_run"] >= 3),
        ("brain_ablaze", "Brain Ablaze", "Five bad days in a row. Genuinely, ouch.", s["max_pain_run"] >= 5),
        ("week_of_woe", "A Week of Woe", "Seven bad days in a row. Take it easy on yourself.", s["max_pain_run"] >= 7),
        ("ten_day_siege", "The Ten-Day Siege", "Ten bad days in a row. That's a campaign, not a headache.", s["max_pain_run"] >= 10),
        ("storm_chaser", "Storm Chaser", "Rack up 30 painful days total. Unwillingly.", s["total_pain_days"] >= 30),

        # ── Duration ─────────────────────────────────────────────────
        ("the_long_haul", "The Long Haul", "Endure a single headache lasting over 24 hours.", s["longest_minutes"] >= 24 * 60),
        ("the_marathoner", "The Marathoner", "Endure a single headache over 48 hours. Why is this happening.", s["longest_minutes"] >= 48 * 60),
        ("energizer_headache", "The Energizer Headache", "Mark an entry as 'still going.' It just keeps going.", s["has_ongoing"]),
        ("lost_a_day", "Lost a Whole Day", "Accumulate 24 hours of total logged pain.", s["cumulative_minutes"] >= 24 * 60),
        ("time_sink", "Time Sink", "Accumulate 100 hours of total logged pain. We're so sorry.", s["cumulative_minutes"] >= 100 * 60),

        # ── Medications ──────────────────────────────────────────────
        ("better_living", "Better Living Through Chemistry", "Log a medication for the first time.", s["distinct_meds"] >= 1),
        ("variety_spice", "Variety Is the Spice", "Track 3 different medications.", s["distinct_meds"] >= 3),
        ("pharmacy_loyalty", "Pharmacy Loyalty Card", "Track 5 different medications. They know you by name.", s["distinct_meds"] >= 5),
        ("walking_pharmacy", "Walking Pharmacy", "Track 10 different medications. The CVS receipt of a person.", s["distinct_meds"] >= 10),
        ("double_dose", "Double Dose", "Take 2 meds for a single headache.", s["max_meds_single"] >= 2),
        ("kitchen_sink", "The Kitchen Sink", "Throw 3+ meds at a single headache. Desperate times.", s["max_meds_single"] >= 3),
        ("shotgun_approach", "Shotgun Approach", "Throw 5+ meds at a single headache. Pick a lane!", s["max_meds_single"] >= 5),

        # ── Pain zones ───────────────────────────────────────────────
        ("two_front_war", "Two-Front War", "A headache in 2 zones at once.", s["max_zones_single"] >= 2),
        ("full_helmet", "Full Helmet", "One headache lighting up 4+ zones at once. Yikes.", s["max_zones_single"] >= 4),
        ("total_eclipse", "Total Eclipse of the Head", "One headache across 6+ zones. The whole skull.", s["max_zones_single"] >= 6),
        ("cartographer", "Pain Cartographer", "Map out 5 different pain zones over time.", s["distinct_zones"] >= 5),
        ("atlas_of_agony", "Atlas of Agony", "Map out 8 different pain zones. Full coverage.", s["distinct_zones"] >= 8),

        # ── Headache types ───────────────────────────────────────────
        ("know_your_enemy", "Know Your Enemy", "Log 3 different headache types.", s["distinct_types"] >= 3),
        ("connoisseur", "Headache Connoisseur", "Log 5 different headache types. A refined palate of pain.", s["distinct_types"] >= 5),

        # ── Timing (cheeky) ──────────────────────────────────────────
        ("night_shift", "Night Shift", "Log a headache between midnight and 5am. Sleep is for the stable.", s["has_night_owl"]),
        ("witching_hour", "The Witching Hour", "Log a headache at the stroke of midnight. Spooky.", s["has_midnight"]),
        ("dawn_patrol", "Dawn Patrol", "Log a headache at dawn (5–7am). The sun betrayed you.", s["has_dawn"]),
        ("rise_and_grind", "Rise & Grind", "Log something before 9am. Look at you go.", s["has_early_bird"]),
        ("lunchtime_letdown", "Lunchtime Letdown", "Log a headache around midday. Ruined a perfectly good lunch.", s["has_midday"]),
        ("happy_hour_ruined", "Happy Hour, Ruined", "Log a headache in the evening (6–9pm).", s["has_evening_pain"]),
        ("case_of_the_mondays", "A Case of the Mondays", "Log pain on a Monday. Of course it was a Monday.", s["has_monday_pain"]),
        ("so_close", "So Close to the Weekend", "Log pain on a Friday. The cruelest timing.", s["has_friday_pain"]),
        ("weekend_ruiner", "Weekend Ruiner", "Log pain on a weekend. The audacity.", s["has_weekend_pain"]),
        ("seven_day_forecast", "Seven-Day Forecast", "Log on all 7 days of the week (over time).", s["weekdays_covered"] >= 7),

        # ── Notes / journaling ───────────────────────────────────────
        ("self_aware", "Self-Aware", "Write a note on an entry. Reflection is healthy.", s["has_notes_entry"]),
        ("dear_diary", "Dear Diary", "Add notes to 10 entries.", s["notes_count"] >= 10),
        ("the_scribe", "The Scribe", "Add notes to 25 entries.", s["notes_count"] >= 25),
        ("headache_novelist", "Headache Novelist", "Add notes to 50 entries. Consider a memoir.", s["notes_count"] >= 50),

        # ── Entry volume ─────────────────────────────────────────────
        ("data_nerd", "Seismic Data Nerd", "Log 50 total entries. The science thanks you.", entries >= 50),
        ("power_user", "Power User", "Log 100 total entries.", entries >= 100),
        ("the_archivist", "The Archivist", "Log 200 total entries. A true historian of your own skull.", entries >= 200),

        # ── Locations ────────────────────────────────────────────────
        ("out_of_town", "Out-of-Town Trouble", "Log pain in 2 different cities.", s["distinct_locations"] >= 2),
        ("jet_setter", "Jet-Setter", "Log entries from 3 different cities.", s["distinct_locations"] >= 3),
        ("frequent_flyer", "Frequent Flyer", "Log entries from 5 different cities. Your head travels well.", s["distinct_locations"] >= 5),

        # ── Resilience & progression ─────────────────────────────────
        ("comeback_kid", "Comeback Kid", "Log a good day right after a rough one. Rise!", s["has_comeback"]),
        ("halfway_up", "Halfway Up the Richter Scale", "Reach the middle level tier.", s["level"] >= (len(LEVELS) + 1) // 2),
        ("tectonic", "Tectonic Master", "Reach the top level. The plates obey you.", s["level"] >= len(LEVELS)),
    ]
    return [
        {"id": i, "title": t, "description": d, "unlocked": bool(u)}
        for (i, t, d, u) in defs
    ]
