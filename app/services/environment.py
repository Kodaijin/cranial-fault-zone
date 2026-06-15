"""Open-Meteo Air Quality fetch with graceful fallback (no API key required).

Always returns a dict. On any failure returns "N/A" values so a save is never
blocked. Note: pollen fields from Open-Meteo are Europe-only and will be null
for US locations. US pollen is supplemented by pollen.com (IQVIA) when a ZIP
code can be resolved from city/state.
"""
from __future__ import annotations

from typing import Optional

import httpx

from app.services.geocode import resolve_zip

NA = "N/A"

_POLLEN_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
}


def _na_payload() -> dict:
    return {
        "pm2_5": NA,
        "pm10": NA,
        "ozone": NA,
        "carbon_monoxide": NA,
        "nitrogen_dioxide": NA,
        "nitrogen_monoxide": NA,
        "sulphur_dioxide": NA,
        "nitrogen_oxides": NA,
        "tree_pollen": NA,
        "grass_pollen": NA,
        "weed_pollen": NA,
        "source": NA,
    }


async def _fetch_us_pollen(zip_code: str) -> dict:
    """Fetch pollen data from pollen.com (IQVIA) for a US ZIP code.

    pollen.com provides a single overall Index for a day plus a list of active
    Triggers (plant categories). Since per-category magnitudes are not exposed,
    we assign the overall Index to each active category. This is an
    approximation — the true per-category values may differ.
    """
    url = f"https://www.pollen.com/api/forecast/current/pollen/{zip_code}"
    headers = {**_POLLEN_HEADERS, "Referer": url}
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        periods = data["Location"]["periods"]
        # Prefer the "Today" period; fall back to the first available period.
        period = next((p for p in periods if p.get("Type") == "Today"), periods[0])

        idx = float(period["Index"])
        types = {t.get("PlantType", "") for t in period.get("Triggers", [])}

        return {
            "tree_pollen": idx if "Tree" in types else 0.0,
            "grass_pollen": idx if "Grass" in types else 0.0,
            "weed_pollen": idx if ("Ragweed" in types or "Weed" in types) else 0.0,
        }
    except Exception:
        return {"tree_pollen": NA, "grass_pollen": NA, "weed_pollen": NA}


async def fetch_environment(
    lat: Optional[float],
    lon: Optional[float],
    city: Optional[str] = None,
    state: Optional[str] = None,
) -> dict:
    """Fetch air quality and pollen data for a coordinate.

    Air quality (pm2_5, pm10, ozone) comes from Open-Meteo and works globally.
    Pollen comes from pollen.com (IQVIA) for US locations when a ZIP code can
    be resolved, overriding the Open-Meteo pollen values which are Europe-only.
    """
    if lat is None or lon is None:
        return _na_payload()

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(
                "https://air-quality-api.open-meteo.com/v1/air-quality",
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "current": (
                        "pm10,pm2_5,ozone,"
                        "carbon_monoxide,nitrogen_dioxide,nitrogen_monoxide,sulphur_dioxide,"
                        "alder_pollen,birch_pollen,grass_pollen,"
                        "mugwort_pollen,olive_pollen,ragweed_pollen"
                    ),
                },
            )
            resp.raise_for_status()
            data = resp.json()
            current = data.get("current", {})

            pm2_5 = current.get("pm2_5")
            pm10 = current.get("pm10")
            ozone = current.get("ozone")
            carbon_monoxide = current.get("carbon_monoxide")
            nitrogen_dioxide = current.get("nitrogen_dioxide")
            nitrogen_monoxide = current.get("nitrogen_monoxide")
            sulphur_dioxide = current.get("sulphur_dioxide")
            grass_pollen = current.get("grass_pollen")

            # Nitrogen oxides: NOx = NO + NO2 (Open-Meteo has no direct NOx variable).
            nitrogen_oxides = None
            if nitrogen_monoxide is not None and nitrogen_dioxide is not None:
                nitrogen_oxides = nitrogen_monoxide + nitrogen_dioxide

            # Tree pollen: sum of birch + alder + olive (Europe-only; null in US).
            tree_parts = [
                current.get("birch_pollen"),
                current.get("alder_pollen"),
                current.get("olive_pollen"),
            ]
            tree_vals = [v for v in tree_parts if v is not None]
            tree_pollen = sum(tree_vals) if tree_vals else None

            # Weed pollen: sum of ragweed + mugwort (Europe-only; null in US).
            weed_parts = [
                current.get("ragweed_pollen"),
                current.get("mugwort_pollen"),
            ]
            weed_vals = [v for v in weed_parts if v is not None]
            weed_pollen = sum(weed_vals) if weed_vals else None

            result = {
                "pm2_5": pm2_5 if pm2_5 is not None else NA,
                "pm10": pm10 if pm10 is not None else NA,
                "ozone": ozone if ozone is not None else NA,
                "carbon_monoxide": carbon_monoxide if carbon_monoxide is not None else NA,
                "nitrogen_dioxide": nitrogen_dioxide if nitrogen_dioxide is not None else NA,
                "nitrogen_monoxide": nitrogen_monoxide if nitrogen_monoxide is not None else NA,
                "sulphur_dioxide": sulphur_dioxide if sulphur_dioxide is not None else NA,
                "nitrogen_oxides": nitrogen_oxides if nitrogen_oxides is not None else NA,
                "tree_pollen": tree_pollen if tree_pollen is not None else NA,
                "grass_pollen": grass_pollen if grass_pollen is not None else NA,
                "weed_pollen": weed_pollen if weed_pollen is not None else NA,
                "source": "open-meteo",
            }
    except (httpx.HTTPError, KeyError, ValueError):
        return _na_payload()

    # If city/state are provided, attempt to override pollen with US pollen.com data.
    if city and state:
        zip_code = await resolve_zip(city, state)
        if zip_code:
            us_pollen = await _fetch_us_pollen(zip_code)
            # Only override if at least one value came back as a number (not all N/A).
            if any(v != NA for v in us_pollen.values()):
                result["tree_pollen"] = us_pollen["tree_pollen"]
                result["grass_pollen"] = us_pollen["grass_pollen"]
                result["weed_pollen"] = us_pollen["weed_pollen"]
                result["source"] = "open-meteo+pollen.com"

    return result
