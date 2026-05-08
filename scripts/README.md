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

## `invite_admin.py`

Creates (or promotes) a Sovereign Society admin. Sets `is_admin=True`,
`lifetime_access=True`, `email_verified=True`, and issues a 7-day password-reset
token. Prints the reset link AND attempts to send a password-reset email.

```bash
# Local DB:
python scripts/invite_admin.py <email> "<full name>"

# Production DB (recommended — runs locally with prod env injected):
railway run python scripts/invite_admin.py <email> "<full name>"
```

Idempotent — running twice on the same email refreshes the reset token without
disturbing existing data. After running, also add the email to `ADMIN_EMAILS`
env var on Railway to satisfy the defense-in-depth allowlist in `app.py:180`.

## `null_broken_uploads.py`

One-shot — sweeps `User.profile_photo` and nulls any value whose underlying
file is gone (neither in R2 under `uploads/<key>` nor on local disk under
`static/uploads/<key>`). Affected users see avatar placeholders + can
re-upload via `/profile/edit`. Phase 9 cleanup of the 5 users with broken
paths from Railway's ephemeral-disk era — see SoT §9 (2026-05-08).

```bash
# Run against prod with Railway env injected (R2_* + DATABASE_URL):
railway run python scripts/null_broken_uploads.py
```

Idempotent — running twice yields the same end state. Also covers the
local-disk case for dev (no R2 creds) where the file may have been deleted
manually.
