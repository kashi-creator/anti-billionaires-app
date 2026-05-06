"""Geocoding + distance helpers for the Find Brothers feature (Phase 6).

- `geocode_city(query)` resolves a free-text city/region string to a dict with
  lat/lng plus the Nominatim `boundingbox` and result `class/type`. Routes use
  `class == 'boundary'` (states/countries) to switch from radius search to
  bounding-box containment, so "Texas" returns everyone in Texas instead of
  everyone within 25mi of the state centroid.
- `haversine_miles(...)` great-circle distance between two coordinates.

Nominatim is keyless with a polite-use rate limit (~1 req/sec). Cached with
`lru_cache` so repeated lookups for the same string don't re-hit the network.
"""
import functools
import math
import requests

NOMINATIM_BASE = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "Sovereign Society/1.0 (kashi@thebreathcoachschool.com)"


@functools.lru_cache(maxsize=1024)
def geocode_city(query: str):
    """Return a dict {lat, lng, bbox, osm_class, osm_type} or None.

    `bbox` is (south, north, west, east) floats when Nominatim provides it,
    else None. `osm_class` is e.g. 'boundary' for administrative regions
    (states/countries) vs 'place' for cities. Cached for the process lifetime.
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
    hit = data[0]
    try:
        lat = float(hit["lat"])
        lng = float(hit["lon"])
    except (KeyError, TypeError, ValueError):
        return None
    bbox = None
    raw_bbox = hit.get("boundingbox")
    if isinstance(raw_bbox, list) and len(raw_bbox) == 4:
        try:
            # Nominatim returns [south, north, west, east] as strings.
            bbox = (
                float(raw_bbox[0]), float(raw_bbox[1]),
                float(raw_bbox[2]), float(raw_bbox[3]),
            )
        except (TypeError, ValueError):
            bbox = None
    return {
        "lat": lat,
        "lng": lng,
        "bbox": bbox,
        "osm_class": hit.get("class"),
        "osm_type": hit.get("type"),
    }


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


def in_bbox(lat, lng, bbox):
    """True if (lat,lng) falls within bbox=(south, north, west, east)."""
    if not bbox:
        return False
    south, north, west, east = bbox
    if lat < south or lat > north:
        return False
    # Handle dateline crossing (west > east means the bbox wraps).
    if west <= east:
        return west <= lng <= east
    return lng >= west or lng <= east
