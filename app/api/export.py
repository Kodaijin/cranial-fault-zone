"""PDF export endpoint."""
from datetime import datetime, date

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.models.models import Entry
from app.services.pdf import build_pdf
from app.tz import to_app_date

router = APIRouter(prefix="/api/export", tags=["export"])


def _parse_date(s: str | None) -> date | None:
    """Parse a YYYY-MM-DD date string. Return None for invalid/missing input."""
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


@router.get("/pdf")
def export_pdf(
    db: Session = Depends(get_db),
    start: str | None = Query(default=None),
    end: str | None = Query(default=None),
):
    entries = db.scalars(
        select(Entry)
        .order_by(Entry.timestamp.asc())
        .options(
            selectinload(Entry.headache_type),
            selectinload(Entry.medications),
            selectinload(Entry.location),
            selectinload(Entry.pain_zones),
        )
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

    pdf_bytes = build_pdf(filtered_entries, start=start_date, end=end_date)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": "attachment; filename=cranial_fault_zone_report.pdf"
        },
    )
