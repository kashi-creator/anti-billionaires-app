"""Geocoding + distance helpers for the Find Brothers feature (Phase 6).

- `geocode_city(query)` resolves a free-text city/region string to (lat, lng)
  via Nominatim (OpenStreetMap). Keyless, polite-use rate limit (~1 req/sec).
  Cached with `lru_cache` so repeated lookups for the same string don't
  re-hit the network.
- `haversine_miles(...)` great-circle distance between two coordinates.
"""
import functools
import math
import requests

NOMINATIM_BASE = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "Sovereign Society/1.0 (kashi@thebreathcoachschool.com)"


@functools.lru_cache(maxsize=1024)
def geocode_city(query: str):
    """Return (lat, lng) tuple for a city/region string, or None if not found.

    Cached for the lifetime of the process; sufficient for MVP volume. If we
    ever sustain ~1 req/sec we should switch to Mapbox/Google Places (paid).
    """
    if not query or len(query.strip()) < 2:
        return None
    try:
        r = requests.get(
            NOMINATIM_BASE,
            params={"q": query.strip(), "format": "json", "limit": 1},
            headers={"User-Agent": USER_AGENT},
            timeout=5,
        )
    except requests.RequestException:
        return None
    if r.status_code != 200:
        return None
    try:
        data = r.json()
    except ValueError:
        return None
    if not data:
        return None
    try:
        return float(data[0]["lat"]), float(data[0]["lon"])
    except (KeyError, TypeError, ValueError):
        return None


def haversine_miles(lat1, lon1, lat2, lon2):
    """Great-circle distance between two lat/lng points, in miles."""
    R = 3958.8
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return 2 * R * math.asin(math.sqrt(a))
