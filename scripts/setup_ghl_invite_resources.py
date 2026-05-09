#!/usr/bin/env python3
"""Idempotently create the GHL Custom Values + Custom Fields needed by the
invite-page RSVP flow.

Custom Values (location-wide, used as merge tags in workflow templates):
  - meeting_date
  - meeting_time
  - meeting_location

Custom Fields (per-contact data populated by /invite/<code> POST):
  - sms_opt_in
  - rsvp_source
  - invited_by                  (inviter's first name — human-readable)
  - invited_by_referral_code    (machine-friendly inviter id for reverse-lookup)

Reads GHL_API_KEY and GHL_LOCATION_ID from the environment. Prints what
exists, what it would create, and (on the live run) what it actually created.

Usage:
    # Dry run — no writes, shows what would change.
    railway run sh -c ".venv/bin/python scripts/setup_ghl_invite_resources.py --dry-run"

    # Live run.
    railway run sh -c ".venv/bin/python scripts/setup_ghl_invite_resources.py"

Idempotent: existing entries (matched by name) are skipped, not duplicated.
"""

import os
import sys
import argparse
import requests

GHL_BASE = "https://services.leadconnectorhq.com"
GHL_VERSION = "2021-07-28"

DESIRED_CUSTOM_VALUES = [
    {
        "name": "meeting_date",
        "value": "TBD — update in GHL Settings → Custom Values",
    },
    {
        "name": "meeting_time",
        "value": "TBD — update in GHL Settings → Custom Values",
    },
    {
        "name": "meeting_location",
        "value": "TBD — update in GHL Settings → Custom Values",
    },
]

DESIRED_CUSTOM_FIELDS = [
    {"name": "sms_opt_in",                 "dataType": "TEXT", "model": "contact"},
    {"name": "rsvp_source",                "dataType": "TEXT", "model": "contact"},
    {"name": "invited_by",                 "dataType": "TEXT", "model": "contact"},
    {"name": "invited_by_referral_code",   "dataType": "TEXT", "model": "contact"},
]


def banner():
    print("=" * 72, file=sys.stderr)
    print("⚠  DO NOT SHARE ANY OUTPUT FROM THIS SCRIPT.", file=sys.stderr)
    print("⚠  Errors may include partial API responses; treat as sensitive.", file=sys.stderr)
    print("=" * 72, file=sys.stderr)


def headers(api_key):
    return {
        "Authorization": f"Bearer {api_key}",
        "Version": GHL_VERSION,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def list_custom_values(api_key, location_id):
    url = f"{GHL_BASE}/locations/{location_id}/customValues"
    r = requests.get(url, headers=headers(api_key), timeout=15)
    r.raise_for_status()
    data = r.json()
    return data.get("customValues", []) or data.get("data", []) or []


def list_custom_fields(api_key, location_id):
    url = f"{GHL_BASE}/locations/{location_id}/customFields"
    r = requests.get(url, headers=headers(api_key), timeout=15)
    r.raise_for_status()
    data = r.json()
    return data.get("customFields", []) or data.get("data", []) or []


def create_custom_value(api_key, location_id, name, value):
    url = f"{GHL_BASE}/locations/{location_id}/customValues"
    r = requests.post(url, headers=headers(api_key), json={"name": name, "value": value}, timeout=15)
    if r.status_code >= 400:
        raise RuntimeError(f"createCustomValue {name!r}: HTTP {r.status_code} — {r.text[:200]}")
    return r.json()


def create_custom_field(api_key, location_id, name, dataType, model):
    url = f"{GHL_BASE}/locations/{location_id}/customFields"
    payload = {"name": name, "dataType": dataType, "model": model}
    r = requests.post(url, headers=headers(api_key), json=payload, timeout=15)
    if r.status_code >= 400:
        raise RuntimeError(f"createCustomField {name!r}: HTTP {r.status_code} — {r.text[:200]}")
    return r.json()


def name_of(entity):
    return (entity.get("name") or "").strip().lower()


def fieldkey_of(entity):
    return entity.get("fieldKey") or entity.get("key") or "(no fieldKey returned)"


def main():
    parser = argparse.ArgumentParser(description="Set up GHL invite-flow resources")
    parser.add_argument("--dry-run", action="store_true",
                        help="List current state and what would change. No writes.")
    args = parser.parse_args()

    banner()

    api_key = os.environ.get("GHL_API_KEY")
    location_id = os.environ.get("GHL_LOCATION_ID")
    if not api_key or not location_id:
        print("ERROR: GHL_API_KEY and GHL_LOCATION_ID must be set in env.", file=sys.stderr)
        print("       Run via `railway run` so the prod values are inherited,", file=sys.stderr)
        print("       or export them locally before invoking.", file=sys.stderr)
        sys.exit(2)

    mode = "DRY RUN" if args.dry_run else "LIVE"
    print(f"\n[{mode}] Location: {location_id[:6]}…   Version: {GHL_VERSION}\n")

    # --- CUSTOM VALUES ---
    print("CUSTOM VALUES")
    print("-" * 72)
    try:
        existing_values = list_custom_values(api_key, location_id)
    except Exception as e:
        print(f"  failed to list custom values: {e}")
        sys.exit(1)
    existing_value_names = {name_of(v) for v in existing_values}
    print(f"  existing on location: {sorted(existing_value_names) or '[]'}")
    for cv in DESIRED_CUSTOM_VALUES:
        if name_of(cv) in existing_value_names:
            print(f"  ✓ exists: {cv['name']}")
            continue
        if args.dry_run:
            print(f"  + would create: {cv['name']}  (placeholder value)")
        else:
            try:
                resp = create_custom_value(api_key, location_id, cv["name"], cv["value"])
                created = resp.get("customValue") or resp
                print(f"  + created: {cv['name']}  → id={created.get('id', '?')}")
            except Exception as e:
                print(f"  ✗ failed: {cv['name']}  — {e}")

    # --- CUSTOM FIELDS ---
    print("\nCUSTOM FIELDS (contact model)")
    print("-" * 72)
    try:
        existing_fields = list_custom_fields(api_key, location_id)
    except Exception as e:
        print(f"  failed to list custom fields: {e}")
        sys.exit(1)
    existing_field_names = {name_of(f) for f in existing_fields}
    print(f"  existing on location: {sorted(existing_field_names) or '[]'}")
    print()
    for cf in DESIRED_CUSTOM_FIELDS:
        if name_of(cf) in existing_field_names:
            match = next(f for f in existing_fields if name_of(f) == name_of(cf))
            print(f"  ✓ exists: {cf['name']}  → fieldKey={fieldkey_of(match)}")
            continue
        if args.dry_run:
            print(f"  + would create: {cf['name']}  ({cf['dataType']}, {cf['model']})")
        else:
            try:
                resp = create_custom_field(api_key, location_id, cf["name"], cf["dataType"], cf["model"])
                created = resp.get("customField") or resp
                print(f"  + created: {cf['name']}  → fieldKey={fieldkey_of(created)}  id={created.get('id','?')}")
            except Exception as e:
                print(f"  ✗ failed: {cf['name']}  — {e}")

    print("\nDONE.")
    if not args.dry_run:
        print("\nNEXT STEPS:")
        print("  1. In GHL Settings → Custom Values, edit meeting_date / meeting_time / ")
        print("     meeting_location with the real next-meeting details.")
        print("  2. Verify the custom field fieldKeys above match what lib/ghl.py sends:")
        print("     'sms_opt_in', 'rsvp_source', 'invited_by', 'invited_by_referral_code'.")
        print("     If GHL prefixed them (e.g. 'contact.sms_opt_in'), tell Kashi —")
        print("     register_meeting_rsvp() will need the prefixed keys.")


if __name__ == "__main__":
    main()
