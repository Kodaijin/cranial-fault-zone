"""SQLAlchemy ORM models for Cranial Fault Zone.

Schema:
    Entries >---< Entry_Pain_Locations >---< Pain_Zones
       |--> Headache_Types
       >---< Entry_Medications >---< Medications  (many-to-many)
       |--> Locations
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class HeadacheType(Base):
    __tablename__ = "headache_types"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    entries: Mapped[list["Entry"]] = relationship(back_populates="headache_type")


class Medication(Base):
    __tablename__ = "medications"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    dosage_notes: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    entries: Mapped[list["Entry"]] = relationship(
        secondary="entry_medications", back_populates="medications"
    )


class Location(Base):
    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(primary_key=True)
    city_name: Mapped[str] = mapped_column(String(120), nullable=False)
    state_code: Mapped[str] = mapped_column(String(10), nullable=False)

    entries: Mapped[list["Entry"]] = relationship(back_populates="location")


class PainZone(Base):
    __tablename__ = "pain_zones"

    id: Mapped[int] = mapped_column(primary_key=True)
    zone_name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)

    entries: Mapped[list["Entry"]] = relationship(
        secondary="entry_pain_locations", back_populates="pain_zones"
    )


class EntryPainLocation(Base):
    """Association table for the Entry <-> PainZone many-to-many."""

    __tablename__ = "entry_pain_locations"

    entry_id: Mapped[int] = mapped_column(
        ForeignKey("entries.id", ondelete="CASCADE"), primary_key=True
    )
    pain_zone_id: Mapped[int] = mapped_column(
        ForeignKey("pain_zones.id", ondelete="CASCADE"), primary_key=True
    )


class EntryMedication(Base):
    """Association table for the Entry <-> Medication many-to-many."""

    __tablename__ = "entry_medications"

    entry_id: Mapped[int] = mapped_column(
        ForeignKey("entries.id", ondelete="CASCADE"), primary_key=True
    )
    medication_id: Mapped[int] = mapped_column(
        ForeignKey("medications.id", ondelete="CASCADE"), primary_key=True
    )


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(50), primary_key=True)
    value: Mapped[str] = mapped_column(String(255))


class Entry(Base):
    __tablename__ = "entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    # When the headache occurred (user-supplied). Defaults to creation time.
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    headache_type_id: Mapped[int] = mapped_column(
        ForeignKey("headache_types.id"), nullable=False
    )
    # Legacy free-form duration (no longer written from the UI; kept for old rows
    # and used as a fallback when end_time is absent). Prefer end_time going forward.
    duration_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # When the headache ended. For a "still going" entry this is set to 23:59 of the
    # onset day and is_ongoing is True until a real end time is recorded.
    end_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_ongoing: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # True for good-day rows created automatically to fill an otherwise-empty day
    # (so we capture environmental data). These are replaced if a real entry is
    # later logged for the same day.
    auto_generated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Self-reference: this entry continues a prior (non-good-day) entry's episode.
    linked_entry_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("entries.id", ondelete="SET NULL"), nullable=True
    )
    location_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("locations.id"), nullable=True
    )
    # Stored as JSON text (SQLite). "N/A" payloads are valid (graceful fallback).
    weather_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    environmental_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    headache_type: Mapped["HeadacheType"] = relationship(back_populates="entries")
    medications: Mapped[list["Medication"]] = relationship(
        secondary="entry_medications", back_populates="entries"
    )
    location: Mapped[Optional["Location"]] = relationship(back_populates="entries")
    pain_zones: Mapped[list["PainZone"]] = relationship(
        secondary="entry_pain_locations", back_populates="entries"
    )
