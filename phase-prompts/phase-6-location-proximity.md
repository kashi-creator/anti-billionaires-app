# Phase 6 — Member location search + proximity detection

> Paste into a fresh Claude Code session in `/Users/kenneth/anti-billionaires-app`. **Goal:** members can find brothers in their city OR have nearby brothers auto-surfaced when they travel. Extends the existing Leaflet.js Member Map (does not replace it).
>
> Spec lives in memory at `~/.claude/projects/-Users-kenneth-anti-billionaires-app/memory/project_pending_location_feature.md`. Read first.

---

## Step 0 — Pull + read

```bash
git fetch origin && git status
cat ~/.claude/projects/-Users-kenneth-anti-billionaires-app/memory/project_pending_location_feature.md
```

---

## Step 1 — Read first

1. `INTEGRATION-SOURCE-OF-TRUTH.md`.
2. The location memory file (above).
3. `models.py` — `User` location fields: `city`, `country`, `lat`, `lng`, `show_on_map`. **Schema mostly already there** — see step 3.1 for the small additions.
4. `app.py` `/profile/location` route (the existing endpoint that updates `lat`/`lng`).
5. `templates/member_map.html` (Leaflet.js dark theme map). You'll add a sibling search/proximity surface, not replace this.
6. `templates/onboarding.html` step 3 (where city + country get collected). The assessment from Phase 5 lands users here eventually, so location capture is already part of onboarding.
7. `features_routes.py` — existing `/map` and `/members` routes. You'll extend `/members` with a search-by-location surface.

---

## Step 2 — Decisions locked

### 2.1 Two modes

**(a) Search by city/region** — text input, "Find brothers in [Austin, Texas]" → results list (members with matching `city` or with `lat`/`lng` within X miles of the searched location).

**(b) Proximity detection** — opt-in. When member opens `/find-nearby`, browser prompts for geolocation. We compute distance from each visible-on-map member, surface the closest 20.

### 2.2 Privacy model

Three opt-in tiers (one toggle on profile, three values):
- `city_only` (default for new users) — show city/country to other logged-in members. NOT surfaced in proximity search results (members can find you by city search but not by "nearby me").
- `proximity_visible` — appears in proximity results. Implies `city_only` too.
- `hidden` — does not appear in any location surface. Equivalent to existing `show_on_map=False`.

Add to User model:
```python
location_visibility = db.Column(db.String(20), nullable=False, default="city_only")  # 'hidden' | 'city_only' | 'proximity_visible'
```

Map the existing `show_on_map` boolean: `show_on_map=False` ⇒ `location_visibility='hidden'`. Migration sets default `'city_only'` for all current users with `show_on_map=True`. Keep `show_on_map` column for backwards-compat; treat `location_visibility != 'hidden'` as authoritative going forward.

Add a profile-edit UI control: "Who can see your location?" 3-radio. Existing onboarding step 3 (city + country) gets a fourth field below the country input: "Who can see this?" with 3 radios, default `city_only`.

### 2.3 Geocoding

**Use Nominatim (OpenStreetMap-based, free, 1 req/sec).** No API key required. Polite request rate. Sufficient for MVP volume.

Wrapped in `lib/geocoding.py` with a 24-hour in-memory cache (lru_cache or a tiny dict-based TTL cache) so repeated lookups for "Austin, TX" don't hammer Nominatim.

If usage exceeds Nominatim's polite-use threshold (~1 req/sec sustained, or ~10K req/day), switch to Mapbox or Google Places (paid). NOT in scope for this phase — flag it in §10 risks.

User-Agent header per Nominatim's policy: `Sovereign Society/1.0 (kashi@thebreathcoachschool.com)` (or whatever address Kashi prefers).

### 2.4 Distance computation

Haversine formula. Inline helper in `lib/geocoding.py`:
```python
import math
def haversine_miles(lat1, lon1, lat2, lon2):
    R = 3958.8  # earth radius miles
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlon/2)**2
    return 2 * R * math.asin(math.sqrt(a))
```

For SQL filtering when scaling matters: bounding-box pre-filter (cheap on indexed lat/lng), Haversine for the final ranking. Phase-6 implementation can do all-Python (full table scan + filter) — fine for <10K users.

### 2.5 New routes

- `GET /find` — landing page. Tab 1: "Search by city" form. Tab 2: "Find brothers nearby" (browser geolocation button).
- `POST /find/search` — accepts `{ "city": "Austin, TX", "radius_miles": 25 }`. Geocodes the city, returns JSON list of matching `User` rows (respecting `location_visibility`).
- `POST /find/nearby` — accepts `{ "lat": ..., "lng": ... }` (from the browser's `navigator.geolocation`). Returns 20 closest members with `location_visibility='proximity_visible'`.
- Existing `/map` stays as-is. The "Find brothers" feature is a sister page, not a replacement.

### 2.6 Approved copy (verbatim from memory)

Allowed: "Find brothers near you", "Who's in your city", "Members in Austin, TX", "Brothers in your area".
Banned: anything dating/hookup-coded ("find men near you" — no).

### 2.7 What does NOT happen

- Do NOT rip out or modify the existing `/map` route or `member_map.html`.
- Do NOT geocode automatically on every profile save (only when user explicitly searches a city, or when their `city` changes during onboarding/profile-edit).
- Do NOT store geocoded `lat`/`lng` for the user from the city — that's separate from the user's actual coordinates (which they may want to set differently, e.g. travel hub vs. home).
- Do NOT introduce a new map library or upgrade Leaflet.
- Do NOT add native geolocation handling for the Capacitor iOS shell — browser API works inside the WebView; native plugin can come in Phase 7+.
- Do NOT add real-time presence ("X is nearby right now"). Static lookup only.

---

## Step 3 — Implementation

### 3.1 Schema migration

```python
op.add_column("user", sa.Column("location_visibility", sa.String(20), nullable=False, server_default="city_only"))
# Backfill: 'hidden' for users with show_on_map=False
op.execute("UPDATE \"user\" SET location_visibility = 'hidden' WHERE show_on_map = false")
```

### 3.2 `lib/geocoding.py`

```python
import functools, time, math, requests

NOMINATIM_BASE = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "Sovereign Society/1.0 (kashi@thebreathcoachschool.com)"

@functools.lru_cache(maxsize=1024)
def geocode_city(query: str):
    """Return (lat, lng) tuple or None. Cached."""
    if not query or len(query.strip()) < 2:
        return None
    r = requests.get(NOMINATIM_BASE,
                     params={"q": query, "format": "json", "limit": 1},
                     headers={"User-Agent": USER_AGENT},
                     timeout=5)
    if r.status_code != 200:
        return None
    data = r.json()
    if not data:
        return None
    return float(data[0]["lat"]), float(data[0]["lon"])

def haversine_miles(lat1, lon1, lat2, lon2):
    R = 3958.8
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlon/2)**2
    return 2 * R * math.asin(math.sqrt(a))
```

Polite delay: lru_cache plus a sleep in the API call if last call was <1 second ago. Or trust low volume + skip the rate limiter for now. Note in §10 SoT.

### 3.3 Routes (in `features_routes.py`)

```python
@features.route("/find")
@login_required
@paywall_required
def find_brothers():
    return render_template("find.html")

@features.route("/find/search", methods=["POST"])
@login_required
@paywall_required
def find_search():
    data = request.get_json(silent=True) or {}
    city = (data.get("city") or "").strip()
    radius = int(data.get("radius_miles") or 25)
    if not city:
        return jsonify({"error": "city required"}), 400
    coords = geocode_city(city)
    if not coords:
        return jsonify({"error": "could not locate that city"}), 400
    target_lat, target_lng = coords
    candidates = User.query.filter(
        User.location_visibility != "hidden",
        User.lat.isnot(None),
        User.lng.isnot(None),
    ).all()
    results = []
    for u in candidates:
        d = haversine_miles(target_lat, target_lng, u.lat, u.lng)
        if d <= radius:
            results.append({"id": u.id, "name": u.name, "city": u.city, "country": u.country, "miles": round(d, 1), "profile_photo": u.profile_photo})
    results.sort(key=lambda x: x["miles"])
    return jsonify({"results": results, "center": {"lat": target_lat, "lng": target_lng, "city": city}})

@features.route("/find/nearby", methods=["POST"])
@login_required
@paywall_required
def find_nearby():
    data = request.get_json(silent=True) or {}
    lat = data.get("lat")
    lng = data.get("lng")
    if lat is None or lng is None:
        return jsonify({"error": "lat,lng required"}), 400
    candidates = User.query.filter(
        User.location_visibility == "proximity_visible",
        User.lat.isnot(None),
        User.lng.isnot(None),
    ).all()
    results = []
    for u in candidates:
        d = haversine_miles(lat, lng, u.lat, u.lng)
        results.append({"id": u.id, "name": u.name, "city": u.city, "miles": round(d, 1), "profile_photo": u.profile_photo})
    results.sort(key=lambda x: x["miles"])
    return jsonify({"results": results[:20]})
```

### 3.4 Templates

`templates/find.html`: two tabs (CSS toggle), brand-consistent dark + gold. Tab 1 has the city input + 25/50/100mi radius selector + result cards. Tab 2 has a "Use my current location" button that triggers `navigator.geolocation.getCurrentPosition`, then POSTs to `/find/nearby`.

Result cards: avatar, name, city, distance, link to `/profile/<id>`.

### 3.5 Profile + onboarding visibility control

In `templates/edit_profile.html` (or wherever profile edit lives): add a "Who can see your location?" radio set with 3 options (`hidden`, `city_only`, `proximity_visible`) + 1-line explainer per option.

In `templates/onboarding.html` step 3 (the city/country step): add the same radio set below the country input. Default `city_only`.

### 3.6 Nav + checklist integration

Add a "Find brothers" entry to the main nav (next to "Members" / "Map"). Don't add a checklist item for it — that's saturated already after Phase 4.

---

## Step 4 — What NOT to do

- Do NOT geocode at every page load. Cache aggressively.
- Do NOT expose `User.lat`/`lng` raw to other users in JSON responses (only city + miles-from-search-center).
- Do NOT cross over into other phases' files.
- Do NOT track or log geolocation events.

---

## Step 5 — Smoke tests

Local:
1. Migration runs clean. `User.location_visibility` exists, defaults to `city_only`. Users with old `show_on_map=False` are now `'hidden'`.
2. New user signs up, hits onboarding step 3 → 3 radios visible, default `city_only`. Picks `proximity_visible`, saves.
3. Hit `/find` → search "Austin, TX" + 25 mile radius. Empty results expected (no Austin members yet).
4. Seed 2 placeholder users at known coordinates (e.g. Austin lat/lng 30.27,-97.74), `location_visibility='proximity_visible'`. Re-search "Austin, TX" → 2 results, sorted by distance.
5. Search a garbage city ("ksjdhfksjd") → 400 with "could not locate that city".
6. `/find/nearby` POST with mock lat/lng → returns the 2 Austin users.
7. Set one of the Austin users to `'hidden'` → re-search → that user is gone.
8. Set one of the Austin users to `'city_only'` → city search still finds them, `/find/nearby` does NOT.
9. Geocode cache: hit "Austin, TX" twice in <1 sec — second hit returns instantly, no Nominatim call (verify via mock or instrumentation).

Production:
10. After deploy, verify no regressions on `/map`, `/members`, `/profile/edit`. Existing functionality unchanged.

---

## Step 6 — Update SoT

- §3 App Scope: extend the user-area entry to mention location_visibility.
- §5 Env vars: no new env vars (Nominatim is keyless).
- §8 Phase Status: Phase 6 ✅ done.
- §9 Decisions: pillar of decisions captured here (3-tier visibility, Nominatim choice, all-python distance).
- §10 Risks: 
  - Nominatim rate limit (~1 req/sec polite) — flag if usage scales.
  - User search emails/names visible in search results to any logged-in member — confirm this is OK; if not, add a "members can opt out of being findable" toggle.

---

## Step 7 — Commit + push

Two commits:

**Commit 1 — schema + lib + routes:**
```
phase-6: location search + proximity — schema + nominatim geocoding + routes

- migration: User.location_visibility (3-tier: hidden/city_only/proximity_visible)
- lib/geocoding.py: nominatim wrapper with lru_cache + haversine helper
- /find, /find/search, /find/nearby routes (privacy-aware)
- backfills 'hidden' for legacy show_on_map=False users
```

**Commit 2 — templates + sot:**
```
phase-6: find brothers ui + sot — onboarding + profile visibility controls
```

---

## Step 8 — Report back

5 bullets: migration ok, geocoding works on real city query, smoke 4–8 pass, privacy gate verified (smoke 7+8), surprises.

If `User.show_on_map` is referenced from places I didn't anticipate (Leaflet map filter, GHL export, etc.), surface — DO NOT silently rewire those references. Manager decides.
