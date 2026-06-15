"""CRUD APIs for the dynamic reference lists.

Headache types, medications, locations: full add/list/delete.
Pain zones: list + optional add.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.models import HeadacheType, Location, Medication, PainZone
from app.seed import GOOD_DAY_TYPE_NAME
from app.schemas import (
    HeadacheTypeCreate,
    HeadacheTypeOut,
    LocationCreate,
    LocationOut,
    MedicationCreate,
    MedicationOut,
    PainZoneCreate,
    PainZoneOut,
)

router = APIRouter(prefix="/api", tags=["reference-data"])


# --- Headache Types ---
@router.get("/headache_types", response_model=list[HeadacheTypeOut])
def list_headache_types(db: Session = Depends(get_db)):
    return db.scalars(select(HeadacheType).order_by(HeadacheType.name)).all()


@router.post("/headache_types", response_model=HeadacheTypeOut, status_code=201)
def create_headache_type(payload: HeadacheTypeCreate, db: Session = Depends(get_db)):
    obj = HeadacheType(name=payload.name.strip())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/headache_types/{item_id}", status_code=204)
def delete_headache_type(item_id: int, db: Session = Depends(get_db)):
    obj = db.get(HeadacheType, item_id)
    if obj is None:
        raise HTTPException(404, "Headache type not found")
    if obj.name == GOOD_DAY_TYPE_NAME:
        raise HTTPException(400, "Cannot delete the built-in Good Day type")
    db.delete(obj)
    db.commit()


# --- Medications ---
@router.get("/medications", response_model=list[MedicationOut])
def list_medications(db: Session = Depends(get_db)):
    return db.scalars(select(Medication).order_by(Medication.name)).all()


@router.post("/medications", response_model=MedicationOut, status_code=201)
def create_medication(payload: MedicationCreate, db: Session = Depends(get_db)):
    obj = Medication(name=payload.name.strip(), dosage_notes=payload.dosage_notes)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/medications/{item_id}", status_code=204)
def delete_medication(item_id: int, db: Session = Depends(get_db)):
    obj = db.get(Medication, item_id)
    if obj is None:
        raise HTTPException(404, "Medication not found")
    db.delete(obj)
    db.commit()


# --- Locations ---
@router.get("/locations", response_model=list[LocationOut])
def list_locations(db: Session = Depends(get_db)):
    return db.scalars(select(Location).order_by(Location.city_name)).all()


@router.post("/locations", response_model=LocationOut, status_code=201)
def create_location(payload: LocationCreate, db: Session = Depends(get_db)):
    obj = Location(
        city_name=payload.city_name.strip(),
        state_code=payload.state_code.strip().upper(),
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/locations/{item_id}", status_code=204)
def delete_location(item_id: int, db: Session = Depends(get_db)):
    obj = db.get(Location, item_id)
    if obj is None:
        raise HTTPException(404, "Location not found")
    db.delete(obj)
    db.commit()


# --- Pain Zones (list + optional add) ---
@router.get("/pain_zones", response_model=list[PainZoneOut])
def list_pain_zones(db: Session = Depends(get_db)):
    return db.scalars(select(PainZone).order_by(PainZone.id)).all()


@router.post("/pain_zones", response_model=PainZoneOut, status_code=201)
def create_pain_zone(payload: PainZoneCreate, db: Session = Depends(get_db)):
    obj = PainZone(zone_name=payload.zone_name.strip())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj
