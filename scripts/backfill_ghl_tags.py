"""Backfill canonical GHL stage tags + custom fields for every existing user.

DRY-RUN BY DEFAULT. Pass --apply to actually write to GHL.

Reads every `User` from the local DB, computes the canonical stage tag from
`subscription_status` + `lifetime_access` + `payments_made_count`, and calls
`lib.ghl.upsert_contact` with the canonical tag + the 4 standard custom fields.

Idempotent: GHL's contacts/upsert is itself idempotent on email, and stage
tags are atomically replaced when `tags=` is passed. Re-running yields the
same result.

Usage (from repo root):
    python scripts/backfill_ghl_tags.py            # dry-run (default)
    python scripts/backfill_ghl_tags.py --apply    # actually write to GHL

`--apply` requires GHL_API_KEY + GHL_LOCATION_ID to be set in the environment;
otherwise the lib client no-ops silently and you'll see "skipped (env unset)"
in the output.

DO NOT run --apply against the live GHL location without first reviewing the
dry-run output. Kashi runs --apply manually after Bryce shares the live
location creds (post-Phase 1 ship).
"""
import argparse
import os
import sys
import time

# Ensure the repo root is on sys.path when invoked as `python scripts/...`.
_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from app import app  # noqa: E402  (must come after sys.path tweak)
from models import User  # noqa: E402
from lib import ghl  # noqa: E402


def _stage_tag_for(user):
    """Map a User's billing/lifetime state to its canonical stage tag.

    This must mirror the logic the live runtime emits — see app.py call sites
    migrated in Phase 1.
    """
    if user.lifetime_access:
        return "lifetime-qualified"
    if user.subscription_status == "active":
        return "active-member"
    if user.subscription_status == "trialing":
        return "trialing"
    if user.subscription_status == "canceled":
        # Trial-cancelled (never charged) vs paid-then-cancelled — different
        # win-back audiences in GHL.
        return "trial-cancelled" if (user.payments_made_count or 0) == 0 else "cancelled"
    if user.subscription_status == "past_due":
        # Treat as still active until churn finalizes.
        return "active-member"
    if user.subscription_status == "inactive":
        return "prospect"
    # Unknown / null status — pre-payment lead.
    return "prospect"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply", action="store_true",
        help="Actually write to GHL. Default is dry-run (no network calls).",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Explicit dry-run flag (default behavior). Useful for clarity in scripts.",
    )
    parser.add_argument(
        "--throttle-ms", type=int, default=0,
        help="Sleep N milliseconds between writes when --apply is set "
             "(GHL rate-limit cushion). Default 0.",
    )
    args = parser.parse_args()

    dry_run = not args.apply
    label = "DRY-RUN" if dry_run else "APPLY"

    if not dry_run and not (os.environ.get("GHL_API_KEY") and os.environ.get("GHL_LOCATION_ID")):
        print("[backfill] WARNING: GHL_API_KEY / GHL_LOCATION_ID unset — "
              "client will no-op even with --apply.")

    with app.app_context():
        users = User.query.order_by(User.id.asc()).all()
        print(f"[backfill] {label}: {len(users)} users")
        print(f"[backfill] {'-' * 70}")

        counts = {}
        for u in users:
            tag = _stage_tag_for(u)
            counts[tag] = counts.get(tag, 0) + 1
            cf = ghl.custom_fields_from_user(u)
            print(
                f"  id={u.id:>4} email={u.email:<40} "
                f"sub={u.subscription_status or '<null>':<10} "
                f"life={'Y' if u.lifetime_access else 'N'} "
                f"paid={u.payments_made_count or 0} "
                f"refs={u.qualified_referrals_count or 0} "
                f"-> {tag}"
            )
            if not dry_run:
                ghl.upsert_contact(
                    email=u.email,
                    name=u.name,
                    stage_tag=tag,
                    custom_fields=cf,
                )
                if args.throttle_ms:
                    time.sleep(args.throttle_ms / 1000.0)

        print(f"[backfill] {'-' * 70}")
        print(f"[backfill] tag distribution:")
        for tag, n in sorted(counts.items(), key=lambda kv: -kv[1]):
            print(f"  {tag:<20} {n}")
        if dry_run:
            print(f"[backfill] dry-run complete — pass --apply to actually write.")
        else:
            print(f"[backfill] applied {len(users)} upserts (async — give the "
                  f"daemon threads a few seconds to flush before exit).")
            # Tiny pause so daemon threads get a chance to fire before main() returns.
            time.sleep(2)


if __name__ == "__main__":
    main()
