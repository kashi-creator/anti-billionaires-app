# scripts/

One-off / operational scripts for Sovereign Society. Not run as part of the
normal request lifecycle.

## `backfill_ghl_tags.py`

Sweeps every `User` row, computes the canonical GHL stage tag from billing /
lifetime state, and upserts the contact in GHL with the tag + the 4 standard
custom fields (`payments_made_count`, `qualified_referrals_count`,
`lifetime_access`, `lifetime_qualified_at`).

```bash
# Dry-run (default — prints diff, makes zero network calls):
python scripts/backfill_ghl_tags.py

# Actually write to GHL (requires GHL_API_KEY + GHL_LOCATION_ID in env):
python scripts/backfill_ghl_tags.py --apply

# Throttle between writes (rate-limit cushion):
python scripts/backfill_ghl_tags.py --apply --throttle-ms 200
```

Idempotent — re-running yields the same end state in GHL. See
`INTEGRATION-SOURCE-OF-TRUTH.md` §6 for the canonical tag taxonomy and §9
for the Phase 1 lift that introduced this script.
