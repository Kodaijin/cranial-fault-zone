"""Seed default rows on first boot. Idempotent: only inserts when a table is empty."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.models import HeadacheType, Location, PainZone, Setting

GOOD_DAY_TYPE_NAME = "Good Day (No Pain)"

DEFAULT_HEADACHE_TYPES = [
    "Migraine",
    "Migraine w/Aura",
    "IIH Headache",
    "Occipital Neuralgia",
    "Other",
]

DEFAULT_LOCATIONS = [
    ("Yakima", "WA"),
    ("Portland", "OR"),
]

DEFAULT_PAIN_ZONES = [
    "Left Eye",
    "Right Eye",
    "Forehead",
    "Occipital/Base of Skull",
    "Crown",
    "Left Temple",
    "Right Temple",
]


def seed_defaults(db: Session) -> None:
    """Insert default reference data exactly once (when each table is empty)."""
    if db.scalar(select(HeadacheType).limit(1)) is None:
        db.add_all(HeadacheType(name=name) for name in DEFAULT_HEADACHE_TYPES)

    if db.scalar(select(Location).limit(1)) is None:
        db.add_all(
            Location(city_name=city, state_code=state)
            for city, state in DEFAULT_LOCATIONS
        )

    if db.scalar(select(PainZone).limit(1)) is None:
        db.add_all(PainZone(zone_name=name) for name in DEFAULT_PAIN_ZONES)

    # Always ensure the good-day type exists (even if other types already seeded).
    existing_good_day = db.scalar(
        select(HeadacheType).where(HeadacheType.name == GOOD_DAY_TYPE_NAME)
    )
    if existing_good_day is None:
        db.add(HeadacheType(name=GOOD_DAY_TYPE_NAME))

    # Ensure a default setting row exists for good_day_mode.
    existing_setting = db.scalar(
        select(Setting).where(Setting.key == "good_day_mode")
    )
    if existing_setting is None:
        db.add(Setting(key="good_day_mode", value="auto"))

    db.commit()
