"""Pydantic request/response schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


# --- Headache Types ---
class HeadacheTypeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class HeadacheTypeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str


# --- Medications ---
class MedicationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    dosage_notes: Optional[str] = Field(default=None, max_length=255)


class MedicationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    dosage_notes: Optional[str] = None


# --- Locations ---
class LocationCreate(BaseModel):
    city_name: str = Field(min_length=1, max_length=120)
    state_code: str = Field(min_length=1, max_length=10)


class LocationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    city_name: str
    state_code: str


# --- Pain Zones ---
class PainZoneCreate(BaseModel):
    zone_name: str = Field(min_length=1, max_length=80)


class PainZoneOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    zone_name: str


# --- Entries ---
class EntryCreate(BaseModel):
    timestamp: Optional[datetime] = None
    headache_type_id: int
    duration_minutes: Optional[int] = Field(default=None, ge=0)
    medication_ids: list[int] = Field(default_factory=list)
    location_id: Optional[int] = None
    pain_zone_ids: list[int] = Field(default_factory=list)
    notes: Optional[str] = None


class EntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    timestamp: datetime
    headache_type: HeadacheTypeOut
    duration_minutes: Optional[int] = None
    medications: list[MedicationOut] = Field(default_factory=list)
    location: Optional[LocationOut] = None
    pain_zones: list[PainZoneOut] = Field(default_factory=list)
    weather_data: Optional[Any] = None
    environmental_data: Optional[Any] = None
    notes: Optional[str] = None
    created_at: datetime
