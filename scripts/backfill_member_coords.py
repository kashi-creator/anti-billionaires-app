"""Backfill lat/lng for existing members who set a city but never got coords.

DRY-RUN BY DEFAULT. Pass --apply to actually write to the DB.

Reason: before Phase 6 the profile-edit form expected the user (or a JS bit)
to supply lat/lng. Many old profiles have `city` set but `lat`/`lng` null,
so they don't appear in `/find/search` results. This script geocodes their
"{city}, {country}" string via Nominatim and fills in the coords.

Usage (from repo root):
    python scripts/backfill_member_coords.py            # dry-run
    python scripts/backfill_member_coords.py --apply    # write to DB

Polite to Nominatim: sleeps 1.1s between fresh lookups (lru_cache absorbs
repeats within the same run). Safe to re-run — it only touches rows where
lat/lng are still null.
"""
import argparse
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from app import app  # noqa: E402
from models import db, User  # noqa: E402
from lib.geocoding import geocode_city  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply", action="store_true",
        help="Actually write to the DB. Default is dry-run.",
    )
    parser.add_argument(
        "--throttle-s", type=float, default=1.1,
        help="Seconds to sleep between Nominatim calls (default 1.1).",
    )
    args = parser.parse_args()
    dry_run = not args.apply
    label = "DRY-RUN" if dry_run else "APPLY"

    with app.app_context():
        rows = User.query.filter(
            User.city.isnot(None),
            User.city != "",
            User.lat.is_(None),
        ).all()

        print(f"[{label}] {len(rows)} members have city but no coords.")
        filled = 0
        skipped = 0
        for u in rows:
            q = ", ".join(p for p in (u.city, u.country) if p)
            hit = geocode_city(q)
            if not hit:
                print(f"  - id={u.id} {q!r} -> not found")
                skipped += 1
            else:
                print(f"  + id={u.id} {q!r} -> {hit['lat']:.4f}, {hit['lng']:.4f}")
                if not dry_run:
                    u.lat = hit["lat"]
                    u.lng = hit["lng"]
                filled += 1
            time.sleep(args.throttle_s)

        if not dry_run:
            db.session.commit()
            print(f"[{label}] committed {filled} updates.")
        else:
            print(f"[{label}] would update {filled} ({skipped} unresolvable). Re-run with --apply.")


if __name__ == "__main__":
    main()
