"""Clinical PDF export — black text on white, print-friendly, no color theme.

Sections:
  1. Summary: total attacks
  2. Most frequent pain locations
  3. Medication efficacy summary
  4. Environmental exposure summary
  5. Chronological appendix of all logged notes
"""
from __future__ import annotations

import io
import json
from collections import Counter
from datetime import datetime, date

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.api.entries import entry_duration_minutes
from app.models.models import Entry
from app.seed import GOOD_DAY_TYPE_NAME


def _styles():
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="CFZTitle",
            parent=styles["Title"],
            textColor=colors.black,
            fontSize=18,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CFZHeading",
            parent=styles["Heading2"],
            textColor=colors.black,
            spaceBefore=14,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CFZBody",
            parent=styles["BodyText"],
            textColor=colors.black,
            alignment=TA_LEFT,
            fontSize=10,
            leading=13,
        )
    )
    return styles


def _table(rows: list[list[str]]) -> Table:
    t = Table(rows, hAlign="LEFT")
    t.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return t


def build_pdf(entries: list[Entry], start: date | None = None, end: date | None = None) -> bytes:
    """Render the clinical report for the given entries and return PDF bytes."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        title="Cranial Fault Zone — Clinical Report",
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )
    s = _styles()
    flow = []

    # Split pain entries from good-day entries.
    pain_entries = [
        e for e in entries
        if not (e.headache_type and e.headache_type.name == GOOD_DAY_TYPE_NAME)
    ]
    good_day_count = len(entries) - len(pain_entries)

    flow.append(Paragraph("Cranial Fault Zone — Headache Report", s["CFZTitle"]))
    flow.append(
        Paragraph(
            f"Generated {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
            s["CFZBody"],
        )
    )

    # Report range line
    if start or end:
        start_str = start.isoformat() if start else "earliest"
        end_str = end.isoformat() if end else "latest"
        flow.append(
            Paragraph(
                f"Report range: {start_str} to {end_str}",
                s["CFZBody"],
            )
        )
    else:
        flow.append(
            Paragraph(
                "Report range: All time",
                s["CFZBody"],
            )
        )

    # --- Section 1: Summary ---
    flow.append(Paragraph("1. Summary", s["CFZHeading"]))
    flow.append(Paragraph(f"Total attacks logged: <b>{len(pain_entries)}</b>", s["CFZBody"]))
    if good_day_count > 0:
        flow.append(Paragraph(f"Good (no-pain) days logged: <b>{good_day_count}</b>", s["CFZBody"]))
    if pain_entries:
        ordered = sorted(pain_entries, key=lambda e: e.timestamp)
        span = (
            f"{ordered[0].timestamp.strftime('%Y-%m-%d')} to "
            f"{ordered[-1].timestamp.strftime('%Y-%m-%d')}"
        )
        flow.append(Paragraph(f"Date range: {span}", s["CFZBody"]))
        type_counts = Counter(e.headache_type.name for e in pain_entries)
        rows = [["Headache Type", "Count"]] + [
            [name, str(n)] for name, n in type_counts.most_common()
        ]
        flow.append(Spacer(1, 6))
        flow.append(_table(rows))

    # --- Section 2: Most frequent pain locations ---
    flow.append(Paragraph("2. Most Frequent Pain Locations", s["CFZHeading"]))
    zone_counts: Counter = Counter()
    for e in pain_entries:
        for z in e.pain_zones:
            zone_counts[z.zone_name] += 1
    if zone_counts:
        rows = [["Pain Zone", "Occurrences"]] + [
            [name, str(n)] for name, n in zone_counts.most_common()
        ]
        flow.append(_table(rows))
    else:
        flow.append(Paragraph("No pain locations recorded.", s["CFZBody"]))

    # --- Section 3: Medication efficacy summary ---
    # Each entry may have multiple medications. Attribute the entry's duration to
    # EACH medication used. Entries with no medications bucket as "None / Untreated".
    flow.append(Paragraph("3. Medication Efficacy Summary", s["CFZHeading"]))
    med_durations: dict[str, list[int]] = {}
    for e in pain_entries:
        dur = entry_duration_minutes(e)
        if e.medications:
            for med in e.medications:
                if dur is not None:
                    med_durations.setdefault(med.name, []).append(dur)
                else:
                    med_durations.setdefault(med.name, [])
        else:
            bucket = "None / Untreated"
            if dur is not None:
                med_durations.setdefault(bucket, []).append(dur)
            else:
                med_durations.setdefault(bucket, [])
    if med_durations:
        rows = [["Medication", "Uses", "Avg Duration (min)"]]
        for med, durations in sorted(med_durations.items()):
            avg = (
                str(round(sum(durations) / len(durations))) if durations else "N/A"
            )
            rows.append([med, str(len(durations)), avg])
        flow.append(_table(rows))
        flow.append(
            Paragraph(
                "Lower average duration may indicate higher efficacy.",
                s["CFZBody"],
            )
        )
    else:
        flow.append(Paragraph("No medication data recorded.", s["CFZBody"]))

    # --- Section 4: Environmental Exposure Summary ---
    flow.append(Paragraph("4. Environmental Exposure Summary", s["CFZHeading"]))
    if pain_entries:
        # Build metrics table with averages
        metrics = [
            ("Barometric Pressure (hPa)", "weather", "pressure_hpa"),
            ("Humidity (%)", "weather", "humidity_pct"),
            ("Temperature (C)", "weather", "temp_c"),
            ("PM2.5 (ug/m3)", "env", "pm2_5"),
            ("PM10 (ug/m3)", "env", "pm10"),
            ("Ozone (ug/m3)", "env", "ozone"),
            ("Carbon Monoxide (ug/m3)", "env", "carbon_monoxide"),
            ("Nitrogen Dioxide (ug/m3)", "env", "nitrogen_dioxide"),
            ("Nitrogen Monoxide (ug/m3)", "env", "nitrogen_monoxide"),
            ("Nitrogen Oxides (ug/m3)", "env", "nitrogen_oxides"),
            ("Sulphur Dioxide (ug/m3)", "env", "sulphur_dioxide"),
            ("Tree Pollen", "env", "tree_pollen"),
            ("Grass Pollen", "env", "grass_pollen"),
            ("Weed Pollen", "env", "weed_pollen"),
        ]

        rows = [["Metric", "Average", "Samples"]]
        for label, source, key in metrics:
            values = []
            for e in pain_entries:
                if source == "weather":
                    data_str = e.weather_data
                else:
                    data_str = e.environmental_data

                data = _parse_json_data(data_str)
                val = data.get(key)
                num_val = _convert_to_float(val)
                if num_val is not None:
                    values.append(num_val)

            if values:
                avg = round(sum(values) / len(values), 1)
                rows.append([label, str(avg), str(len(values))])
            else:
                rows.append([label, "N/A", "0"])

        flow.append(_table(rows))
    else:
        flow.append(Paragraph("No environmental data recorded.", s["CFZBody"]))

    # --- Section 5: Chronological appendix of notes ---
    flow.append(Paragraph("5. Chronological Appendix", s["CFZHeading"]))
    if pain_entries:
        for e in sorted(pain_entries, key=lambda x: x.timestamp):
            zones = ", ".join(z.zone_name for z in e.pain_zones) or "—"
            med = ", ".join(m.name for m in e.medications) if e.medications else "—"
            if e.is_ongoing:
                dur = "ongoing"
            else:
                dur_min = entry_duration_minutes(e)
                dur = f"{dur_min} min" if dur_min is not None else "—"
            header = (
                f"<b>{e.timestamp.strftime('%Y-%m-%d %H:%M')}</b> — "
                f"{e.headache_type.name} | Zones: {zones} | Med: {med} | Duration: {dur}"
            )
            flow.append(Paragraph(header, s["CFZBody"]))
            if e.notes:
                flow.append(Paragraph(f"Notes: {e.notes}", s["CFZBody"]))
            flow.append(Spacer(1, 4))
    else:
        flow.append(Paragraph("No entries logged.", s["CFZBody"]))

    doc.build(flow)
    return buf.getvalue()


def _parse_json_data(data_str: str | None) -> dict:
    """Parse JSON string into a dict. Return empty dict on failure."""
    if not data_str:
        return {}
    try:
        parsed = json.loads(data_str)
        return parsed if isinstance(parsed, dict) else {}
    except (ValueError, TypeError):
        return {}


def _convert_to_float(value) -> float | None:
    """Convert a value to float. Return None for 'N/A'/non-numeric values."""
    if value is None or value == "N/A":
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None
