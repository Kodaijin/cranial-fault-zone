"""City/state -> lat/lon geocoding.

Uses a static cache for the app's default locations so the common cases work
instantly with no API call. Falls back to Open-Meteo geocoding (free, no key)
for any city not in the cache.
"""
from __future__ import annotations

from typing import Optional
from urllib.parse import quote

import httpx

# Static coordinates for the seeded default locations (no API key needed).
STATIC_GEOCODE: dict[tuple[str, str], tuple[float, float]] = {
    ("yakima", "wa"): (46.6021, -120.5059),
    ("portland", "or"): (45.5152, -122.6784),
}

# Static ZIP codes for the seeded default locations.
STATIC_ZIP: dict[tuple[str, str], str] = {
    ("yakima", "wa"): "98901",
    ("portland", "or"): "97201",
}


async def resolve_zip(city: str, state: str) -> Optional[str]:
    """Return a US ZIP code for the given city/state, or None on failure."""
    key = (city.strip().lower(), state.strip().lower())
    if key in STATIC_ZIP:
        return STATIC_ZIP[key]

    state_lower = key[1]
    city_encoded = quote(key[0])

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(
                f"https://api.zippopotam.us/us/{state_lower}/{city_encoded}"
            )
            resp.raise_for_status()
            data = resp.json()
            places = data.get("places") or []
            if not places:
                return None
            return places[0].get("post code") or None
    except Exception:
        return None

# Map US state codes to full admin1 names used by Open-Meteo / Nominatim.
_STATE_NAMES: dict[str, str] = {
    "al": "Alabama", "ak": "Alaska", "az": "Arizona", "ar": "Arkansas",
    "ca": "California", "co": "Colorado", "ct": "Connecticut", "de": "Delaware",
    "fl": "Florida", "ga": "Georgia", "hi": "Hawaii", "id": "Idaho",
    "il": "Illinois", "in": "Indiana", "ia": "Iowa", "ks": "Kansas",
    "ky": "Kentucky", "la": "Louisiana", "me": "Maine", "md": "Maryland",
    "ma": "Massachusetts", "mi": "Michigan", "mn": "Minnesota", "ms": "Mississippi",
    "mo": "Missouri", "mt": "Montana", "ne": "Nebraska", "nv": "Nevada",
    "nh": "New Hampshire", "nj": "New Jersey", "nm": "New Mexico", "ny": "New York",
    "nc": "North Carolina", "nd": "North Dakota", "oh": "Ohio", "ok": "Oklahoma",
    "or": "Oregon", "pa": "Pennsylvania", "ri": "Rhode Island", "sc": "South Carolina",
    "sd": "South Dakota", "tn": "Tennessee", "tx": "Texas", "ut": "Utah",
    "vt": "Vermont", "va": "Virginia", "wa": "Washington", "wv": "West Virginia",
    "wi": "Wisconsin", "wy": "Wyoming", "dc": "District of Columbia",
}


async def geocode(city: str, state: str) -> Optional[tuple[float, float]]:
    """Return (lat, lon) for a city/state, or None if it cannot be resolved."""
    key = (city.strip().lower(), state.strip().lower())
    if key in STATIC_GEOCODE:
        return STATIC_GEOCODE[key]

    state_lower = key[1]
    state_full = _STATE_NAMES.get(state_lower, state.upper())

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={"name": city.strip(), "count": 5, "country": "US"},
            )
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results") or []
            if not results:
                return None
            # Prefer a result whose admin1 matches our state name.
            for r in results:
                admin1 = (r.get("admin1") or "").lower()
                if admin1 == state_full.lower():
                    return float(r["latitude"]), float(r["longitude"])
            # Fall back to first result.
            return float(results[0]["latitude"]), float(results[0]["longitude"])
    except (httpx.HTTPError, KeyError, ValueError, IndexError):
        return None
