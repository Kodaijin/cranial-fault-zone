"""Open-Meteo weather fetch with graceful fallback (no API key required).

Always returns a dict. On any failure (network, parse, missing coords) returns
a payload of "N/A" values so an entry save is never blocked.
"""
from __future__ import annotations

from datetime import date as _date
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


def _mean(values) -> Optional[float]:
    """Mean of the non-null numeric values, rounded to 1 decimal, or None."""
    nums = [v for v in (values or []) if isinstance(v, (int, float))]
    if not nums:
        return None
    return round(sum(nums) / len(nums), 1)


def _mode_code(codes) -> Optional[int]:
    """Most frequent non-null weather code across the day."""
    vals = [c for c in (codes or []) if c is not None]
    if not vals:
        return None
    return max(set(vals), key=vals.count)


async def fetch_weather_historical(
    lat: Optional[float], lon: Optional[float], day: _date
) -> dict:
    """Daily-mean weather for a past `day`. Recent days (<= 90d) come from the
    forecast endpoint's past data; older days from the ERA5 archive (which lags
    a few days). Returns the same payload shape as fetch_weather."""
    if lat is None or lon is None:
        return _na_payload()

    age_days = (_date.today() - day).days
    base = (
        "https://api.open-meteo.com/v1/forecast"
        if age_days <= 90
        else "https://archive-api.open-meteo.com/v1/archive"
    )
    ds = day.isoformat()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                base,
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "start_date": ds,
                    "end_date": ds,
                    "hourly": "temperature_2m,relative_humidity_2m,surface_pressure,weather_code",
                },
            )
            resp.raise_for_status()
            hourly = resp.json().get("hourly", {})

            temp = _mean(hourly.get("temperature_2m"))
            pressure = _mean(hourly.get("surface_pressure"))
            humidity = _mean(hourly.get("relative_humidity_2m"))
            code = _mode_code(hourly.get("weather_code"))
            conditions = _WMO_CODES.get(code, "Unknown") if code is not None else NA

            if temp is None and pressure is None and humidity is None:
                return _na_payload()
            return {
                "temp_c": temp if temp is not None else NA,
                "pressure_hpa": pressure if pressure is not None else NA,
                "humidity_pct": round(humidity) if humidity is not None else NA,
                "conditions": conditions,
                "source": "open-meteo-historical",
            }
    except (httpx.HTTPError, KeyError, ValueError):
        return _na_payload()
