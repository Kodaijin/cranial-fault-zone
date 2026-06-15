"""Open-Meteo weather fetch with graceful fallback (no API key required).

Always returns a dict. On any failure (network, parse, missing coords) returns
a payload of "N/A" values so an entry save is never blocked.
"""
from __future__ import annotations

from typing import Optional

import httpx

NA = "N/A"

# WMO Weather Interpretation Codes -> human-readable text.
_WMO_CODES: dict[int, str] = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Fog",
    51: "Drizzle",
    53: "Drizzle",
    55: "Drizzle",
    61: "Rain",
    63: "Rain",
    65: "Rain",
    71: "Snow",
    73: "Snow",
    75: "Snow",
    80: "Rain showers",
    81: "Rain showers",
    82: "Rain showers",
    95: "Thunderstorm",
}


def _na_payload() -> dict:
    return {
        "temp_c": NA,
        "pressure_hpa": NA,
        "humidity_pct": NA,
        "conditions": NA,
        "source": NA,
    }


async def fetch_weather(lat: Optional[float], lon: Optional[float]) -> dict:
    """Fetch temp, barometric pressure, humidity, and conditions for a coord."""
    if lat is None or lon is None:
        return _na_payload()

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "current": "temperature_2m,relative_humidity_2m,surface_pressure,weather_code",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            current = data.get("current", {})
            temp = current.get("temperature_2m")
            pressure = current.get("surface_pressure")
            humidity = current.get("relative_humidity_2m")
            code = current.get("weather_code")
            conditions = _WMO_CODES.get(code, "Unknown") if code is not None else NA
            return {
                "temp_c": temp if temp is not None else NA,
                "pressure_hpa": pressure if pressure is not None else NA,
                "humidity_pct": humidity if humidity is not None else NA,
                "conditions": conditions,
                "source": "open-meteo",
            }
    except (httpx.HTTPError, KeyError, ValueError):
        return _na_payload()
