# Phase 1 — Lift GHL Client + Standardize Tag Taxonomy + Fix `cron.py` Field Bugs

> Paste this entire prompt into a fresh Claude Code session opened in `~/anti-billionaires-app`. **Prerequisite: production must be live** (Phase 0 audit found Railway returning 404 fallback; manager session has confirmed it's restored before firing this prompt — if `curl -I https://onepercentmensclub.up.railway.app/` is still 404, STOP and tell the manager).
>
> One narrow goal: refactor inline GHL into a real client, lock down a single tag taxonomy aligned with §7 of the SoT, sync the lifetime/referral state into GHL custom fields, and fix three model-field bugs in `cron.py` that share the same code-touch blast radius.

---

## Step 0 — Pull before reading

```bash
git fetch origin && git status
```

If `main` is behind origin: `git reset --hard origin/main` (after confirming no uncommitted local work).

---

## Step 1 — Read first (mandatory)

1. `INTEGRATION-SOURCE-OF-TRUTH.md` — full file. Pay close attention to **§6 (GHL state, including the `ghl_upsert_contact()` shape and the 4 call sites)**, **§7 (Customer Journey Stages — this is the canonical tag list)**, **§13.3 (Phase 0 audit findings on GHL)**, **§9 Decisions Log** for the locked business model + lifetime mechanic. The whole §13 audit is short — read it.
2. `app.py:227-258` (`ghl_upsert_contact` function) and the four call sites: `app.py:799` (signup), `app.py:1348` (subscription_success), `app.py:1435` (subscription.deleted webhook), `app.py:1499` (payment_succeeded → lifetime branch).
3. `models.py` lines 60-67 — the `payments_made_count`, `qualified_referrals_count`, `lifetime_access`, `lifetime_qualified_at` fields. These are what get synced to GHL custom fields in this phase.
4. `cron.py` — full file (~135 lines). Note the three field-name bugs flagged in §10: `cron.py:64` references `Win.content` (should be `Win.title` + `Win.description`), `cron.py:75-77,82` reference `Event.starts_at` (should be `Event.date` + `Event.time`), `cron.py:133` does `(User.query.filter_by(is_admin=True).first() or {}).email` which `AttributeError`s on no admin.

---

## Step 2 — The decisions this phase encodes (the manager has already locked these)

### 2.1 Tag taxonomy — single source

**Kill the brand-tag inconsistency.** Today the GHL pushes apply mixed tags: `"ABMC"` (legacy), `"Sovereign Society"` (new), `"Founder"` (mentioned in old code, no longer applied), `"Paid Member"`, `"Churned"`, `"Lifetime"`. From this phase forward, the canonical tags are EXACTLY the §7 stage tags, lowercase-with-hyphens. Brand identity is implicit (every contact in this GHL location is a Sovereign Society contact by definition — the location itself is the brand boundary). Stage tags only:

| Stage | Canonical tag |
|-------|---------------|
| 1 — Prospect | `prospect` |
| 2 — Trialing | `trialing` |
| 3 — Active Member | `active-member` |
| 4 — Power Member | `power-member` |
| 5 — Lifetime-Qualified | `lifetime-qualified` |
| 6 — At-Risk | `at-risk` |
| 7a — Trial-Cancelled | `trial-cancelled` |
| 7b — Member-Cancelled | `cancelled` |
| 8 — Reactivated | `reactivated` |

A contact carries exactly ONE current-stage tag at any time. Transitions remove the previous stage tag and add the new one (GHL's tag API supports this in a single upsert call).

### 2.2 Custom fields synced to GHL

Four custom fields, mapped from `models.py` columns. Names are GHL field keys (snake_case, not the column name — GHL UI shows "Display Name" separately):

| Custom field key | Source column | Type |
|------------------|---------------|------|
| `payments_made_count` | `User.payments_made_count` | Number |
| `qualified_referrals_count` | `User.qualified_referrals_count` | Number |
| `lifetime_access` | `User.lifetime_access` | Boolean (sent as `"true"`/`"false"` string per GHL convention) |
| `lifetime_qualified_at` | `User.lifetime_qualified_at` | Date (ISO 8601, `YYYY-MM-DD`; null if never qualified) |

These get pushed on every meaningful event (signup, payment_succeeded, subscription_updated, lifetime unlock). They allow GHL workflows to filter on "members with 5 paid months" or "referrers with 2 qualified refs" without round-tripping back to the app DB.

### 2.3 Pipeline scope (named only, IDs come later)

Define ONE pipeline in code: **Sovereign Society — Member Lifecycle**. Stages (in order): Prospect → Trialing → Active → Power → Lifetime → At-Risk → Cancelled. Implementation in this phase: env-var-driven stage IDs (`GHL_STAGE_<NAME>_ID`) referenced from the helper but allowed to be unset (helper no-ops on opportunity creation if env is empty). Kashi creates the pipeline + stages in GHL UI separately and feeds the IDs into Railway env. **Do not block this phase on those IDs being set.**

### 2.4 What does NOT happen in this phase

- No new GHL workflows are created (those live in GHL UI; Kashi sets up).
- No webhook coverage widening (that's Phase 2).
- No engagement-tagging on post created / win posted / etc. (that's Phase 4).
- No backfill of legacy contacts in the live GHL location — write the backfill script but do NOT run it from this session. Kashi runs it manually after reviewing.
- No deletion of `app.py:227-258` until every call site has been migrated and tests/smoke pass.

---

## Step 3 — Implementation

### 3.1 Create `lib/__init__.py` and `lib/ghl.py`

`lib/__init__.py`: empty file (makes `lib/` a Python package).

`lib/ghl.py`: contains the GHL client. Required surface:

```python
# lib/ghl.py
"""GHL (LeadConnector / GoHighLevel) client — Sovereign Society lifecycle integration.

Single canonical entry point for all GHL writes. Stage tags only (no brand tags).
Custom fields sync the lifetime/referral state.

Env vars consumed (all optional — client no-ops if any required var is missing):
    GHL_API_KEY              — Bearer token
    GHL_LOCATION_ID          — location to write into
    GHL_STAGE_PROSPECT_ID    — pipeline stage IDs (optional, used by upsert_opportunity)
    GHL_STAGE_TRIALING_ID
    GHL_STAGE_ACTIVE_ID
    GHL_STAGE_POWER_ID
    GHL_STAGE_LIFETIME_ID
    GHL_STAGE_AT_RISK_ID
    GHL_STAGE_CANCELLED_ID
    GHL_PIPELINE_ID          — pipeline ID (required for opportunity writes; client skips if unset)
"""
import os
import threading
import logging
from typing import Optional, Iterable
import requests

log = logging.getLogger(__name__)

GHL_BASE = "https://services.leadconnectorhq.com"
GHL_VERSION = "2021-07-28"

# Canonical stage tags — these are the ONLY tags this client emits.
STAGE_TAGS = {
    "prospect", "trialing", "active-member", "power-member",
    "lifetime-qualified", "at-risk", "trial-cancelled", "cancelled",
    "reactivated",
}


def _enabled() -> bool:
    return bool(os.environ.get("GHL_API_KEY") and os.environ.get("GHL_LOCATION_ID"))


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {os.environ.get('GHL_API_KEY', '')}",
        "Version": GHL_VERSION,
        "Content-Type": "application/json",
    }


def upsert_contact(
    *,
    email: str,
    name: str,
    phone: Optional[str] = None,
    stage_tag: Optional[str] = None,
    custom_fields: Optional[dict] = None,
    extra_tags: Optional[Iterable[str]] = None,
) -> None:
    """Upsert a contact. Fail-silent. Runs in a daemon thread.

    stage_tag: one of STAGE_TAGS. If provided, becomes the contact's sole
        current-stage tag (we DO NOT remove old stage tags here — the GHL
        upsert API replaces tags atomically when `tags` is passed; pass
        ONLY the new stage tag plus any extra_tags caller supplies).
    custom_fields: dict of {field_key: value}. Stringified before send.
    extra_tags: any tags outside the lifecycle stages (rarely used; reserved
        for things like 'beta-cohort'). Brand tags ('Sovereign Society',
        'ABMC') must NOT appear here.
    """
    if not _enabled():
        log.debug("ghl.upsert_contact skipped: env unset")
        return

    if stage_tag and stage_tag not in STAGE_TAGS:
        raise ValueError(f"stage_tag must be one of {STAGE_TAGS}, got {stage_tag!r}")

    tags = []
    if stage_tag:
        tags.append(stage_tag)
    if extra_tags:
        for t in extra_tags:
            if t in STAGE_TAGS:
                # Caller mistake: stage tags belong in stage_tag, not extra_tags
                raise ValueError(f"{t!r} is a stage tag — pass via stage_tag=")
            tags.append(t)

    payload = {
        "email": email.lower().strip(),
        "name": name,
        "locationId": os.environ["GHL_LOCATION_ID"],
    }
    if phone:
        payload["phone"] = phone
    if tags:
        payload["tags"] = tags
    if custom_fields:
        # GHL accepts customField as a list of {id|key, field_value} pairs.
        payload["customField"] = [
            {"key": k, "field_value": "" if v is None else str(v)}
            for k, v in custom_fields.items()
        ]

    def _send():
        try:
            r = requests.post(
                f"{GHL_BASE}/contacts/upsert",
                headers=_headers(),
                json=payload,
                timeout=10,
            )
            if r.status_code >= 400:
                log.warning("ghl.upsert_contact %s: %s", r.status_code, r.text[:200])
        except Exception as e:
            log.warning("ghl.upsert_contact failed: %s", e)

    threading.Thread(target=_send, daemon=True).start()


def upsert_opportunity(
    *,
    contact_email: str,
    stage_tag: str,
    monetary_value: float = 99.0,
) -> None:
    """No-op if pipeline/stage IDs are unset. Called from Phase 2 webhook handlers."""
    pipeline_id = os.environ.get("GHL_PIPELINE_ID")
    stage_id_env = f"GHL_STAGE_{stage_tag.upper().replace('-', '_')}_ID"
    stage_id = os.environ.get(stage_id_env)
    if not (_enabled() and pipeline_id and stage_id):
        return
    # Implementation deferred to Phase 2 — stub for now.
    log.info("ghl.upsert_opportunity stub: %s → %s", contact_email, stage_tag)


def custom_fields_from_user(user) -> dict:
    """Build the standard 4-field dict from a User row."""
    return {
        "payments_made_count": user.payments_made_count or 0,
        "qualified_referrals_count": user.qualified_referrals_count or 0,
        "lifetime_access": "true" if user.lifetime_access else "false",
        "lifetime_qualified_at": (
            user.lifetime_qualified_at.date().isoformat()
            if user.lifetime_qualified_at else ""
        ),
    }
```

### 3.2 Migrate the four call sites in `app.py`

Replace the inline `ghl_upsert_contact()` definition at `app.py:227-258` AND every call site to use `lib/ghl.py`. The call mapping:

| Old call (line) | New call |
|---|---|
| `app.py:799` (signup, free path) | `ghl.upsert_contact(email=..., name=..., stage_tag="prospect")` *(NOT `trialing` — free signup path has no card; pure prospect)* |
| `app.py:1348` (subscription_success after Stripe checkout creates account) | `ghl.upsert_contact(email=..., name=..., stage_tag="trialing", custom_fields=ghl.custom_fields_from_user(u))` |
| `app.py:1435` (subscription.deleted webhook — `_handle_subscription_deleted`) | Branch on `u.payments_made_count`: 0 → `stage_tag="trial-cancelled"`, ≥1 → `stage_tag="cancelled"`. Always pass `custom_fields=ghl.custom_fields_from_user(u)`. |
| `app.py:1499` (payment_succeeded → lifetime branch — `_handle_payment_succeeded` lifetime block) | `ghl.upsert_contact(email=..., name=..., stage_tag="lifetime-qualified", custom_fields=ghl.custom_fields_from_user(u))` |

Also: in `_handle_payment_succeeded` non-lifetime branch (the path that just increments `payments_made_count`), add a NEW call: `ghl.upsert_contact(email=..., name=..., stage_tag="active-member", custom_fields=ghl.custom_fields_from_user(u))`. This is the Phase 0 "Stripe webhook does not push to GHL on payment_succeeded non-lifetime" gap closure — minimal scope, just keeps the custom fields fresh. Phase 2 will widen further (checkout.completed, sub.updated, payment_failed).

Replace the import in `app.py`: `from lib import ghl` near the top. Remove the inline `ghl_upsert_contact` def + the duplicate `requests` import if it became orphaned.

### 3.3 Fix `cron.py` field bugs

Three fixes, same file:

1. **`cron.py:64`** — `Win` model has no `content`. Replace `w.content` with `f"{w.title} — {w.description}"` (or whatever rendering makes sense given the surrounding template; verify by reading the digest template at `templates/emails/weekly_digest.html` first).
2. **`cron.py:75-77, 82`** — `Event` model has no `starts_at`. Replace with `Event.date` (and `Event.time` for sort/display where needed). Confirm sort is `Event.date.asc()` not `Event.starts_at.asc()`.
3. **`cron.py:133`** — replace `(User.query.filter_by(is_admin=True).first() or {}).email` with the safe form:
   ```python
   admin = User.query.filter_by(is_admin=True).first()
   if not admin:
       click.echo("No admin user found — set ADMIN_EMAILS or create one.")
       return
   admin_email = admin.email
   ```

### 3.4 Fix `_external=True` email rendering in threaded context

Surfaced by Phase 0C: `email_send.py` renders templates inside background threads. Templates use `url_for(..., _external=True)` which raises `RuntimeError` without a request context unless `SERVER_NAME` is configured.

In `app.py` startup config (near the other `app.config[...]` lines around line 65-80), add:

```python
app.config["SERVER_NAME"] = os.environ.get("SERVER_NAME") or (
    "anti-billionaires-app-production.up.railway.app" if ENV == "production" else None
)
app.config["PREFERRED_URL_SCHEME"] = "https"
```

Set `SERVER_NAME` in Railway env to the canonical URL — when custom domain locks (Q7 → `app.sovereignsociety.com`), update this env var.

**Caveat:** `SERVER_NAME` affects cookie domain matching and blueprint URL generation. Verify locally:
- `python app.py` starts (no error about Flask URL routing)
- `/feed` still loads when logged in (cookie still binds correctly)
- `/api/notifications/unread-count` still returns 200 (sub-domain edge case)

### 3.5 Standardize `STRIPE_PRICE_ID` and trial confirmation (informational, no code change)

Run: `grep -n "trial_period_days\|subscription_data" app.py` to confirm the checkout creation passes `subscription_data={"trial_period_days": 30}`. If it doesn't, that's a separate launch blocker — STOP and tell the manager. (Per Phase 0 audit, the trial decision is locked but the executor noted it could not verify the actual `STRIPE_PRICE_ID` is configured with the trial. This is a quick code check that doesn't touch code.)

### 3.6 Backfill script (write but DO NOT run)

Create `scripts/backfill_ghl_tags.py`. Reads every `User` from the local DB, computes their canonical stage tag from `subscription_status` + `lifetime_access` + `payments_made_count`, calls `ghl.upsert_contact` with the canonical tag + custom fields. Idempotent.

The mapping logic (this is the same logic the live code uses):
```python
def _stage_tag_for(user):
    if user.lifetime_access:
        return "lifetime-qualified"
    if user.subscription_status == "active":
        return "active-member"
    if user.subscription_status == "trialing":
        return "trialing"
    if user.subscription_status == "canceled":
        return "trial-cancelled" if user.payments_made_count == 0 else "cancelled"
    if user.subscription_status == "past_due":
        return "active-member"  # treat as still active until churn
    if user.subscription_status == "inactive":
        return "prospect"
    return "prospect"
```

Hardcode a `--dry-run` flag (default true). Actual run requires `--apply`. This way Kashi can preview the diff before any GHL writes hit the live location.

Add a one-line entry to `scripts/README.md` (create the file if it doesn't exist) explaining what the script does and how to run it.

---

## Step 4 — What NOT to do

- Do NOT touch `models.py` — schema is fine as-is. The custom fields sync FROM model columns; no new columns needed.
- Do NOT add new webhook handlers (Phase 2 scope).
- Do NOT add engagement-tagging on post/win/event (Phase 4 scope).
- Do NOT delete `BRYCE-HANDOFF.md` (kept for future hires per SoT §10).
- Do NOT print or log API keys, webhook secrets, or contact data with email addresses at INFO level (DEBUG is fine in dev).
- Do NOT run `scripts/backfill_ghl_tags.py` against the live GHL location.
- Do NOT modify `templates/` or `static/`.

---

## Step 5 — Smoke tests

Local-only. The point is "code didn't break"; full integration verification needs prod env which Kashi does separately.

1. `python -c "from lib import ghl; print(sorted(ghl.STAGE_TAGS))"` — should print the 9 canonical tags.
2. `python -c "from lib import ghl; ghl.upsert_contact(email='test@example.com', name='Test', stage_tag='prospect')"` — should silently no-op (env unset locally) and print no errors.
3. Negative: `python -c "from lib import ghl; ghl.upsert_contact(email='x@x.com', name='X', stage_tag='ABMC')"` — should raise `ValueError` (rejects non-canonical tag).
4. Negative: `python -c "from lib import ghl; ghl.upsert_contact(email='x@x.com', name='X', extra_tags=['active-member'])"` — should raise `ValueError` (stage tag misrouted to extra_tags).
5. `python app.py` — server starts cleanly, no import errors.
6. Hit `/signup`, `/pricing`, `/feed`, `/admin` (logged in as a placeholder) — all 200.
7. `flask cron digest` — runs to completion without `AttributeError`. May still no-op on email send if no users have engagement to digest, but should not crash.
8. `flask cron test-email` — runs to completion. With no admin user, prints the friendly message. With an admin (placeholder users have `is_admin=False` — log into shell and flip one if you want to actually test the email path).
9. `python scripts/backfill_ghl_tags.py --dry-run` — prints the tag-assignment diff for every user, makes zero network calls.

---

## Step 6 — Update SoT

In `INTEGRATION-SOURCE-OF-TRUTH.md`:

- **§5 Environment Variables** — add the new GHL stage/pipeline IDs to "Likely needed in later phases" → move to "Currently expected" if confirmed set in Railway.
- **§6 GHL Integration** — overwrite the "What IS missing (confirmed)" section to reflect Phase 1's resolutions. The remaining gaps after Phase 1: webhook coverage widening (Phase 2), engagement-tagging (Phase 4), no live workflows yet (Kashi GHL UI).
- **§6** — add a new sub-section "**Canonical Tag Taxonomy (locked Phase 1)**" containing the 9-tag table + the rule "stage tags only; brand tags forbidden."
- **§8 Phase Status** — Phase 1 ⬜ → ✅ with commit short SHA + the date.
- **§9 Decisions Log** — append a Phase 1 entry: what was lifted, what tag taxonomy was locked, what custom fields are now syncing, the cron.py bugs fixed.
- **§10 Risks** — strike-through (with `~~ ~~ (resolved 2026-MM-DD by phase-1, commit XXXX)` suffix) the resolved entries: GHL inline function, GHL tag taxonomy split, `cron.py` field bugs (lines 64, 75-77, 82, 133). Leave the others.

---

## Step 7 — Commits

Three commits, atomic:

**Commit 1 — GHL client + tag taxonomy:**
```
phase-1: lift ghl client to lib/ghl.py + lock stage-tag taxonomy

- new lib/ghl.py: stage tags only, custom fields sync, upsert_contact + upsert_opportunity stub
- migrate 4 call sites in app.py to use lib.ghl
- add active-member tag push on payment_succeeded non-lifetime branch
```
Stage exactly: `lib/__init__.py`, `lib/ghl.py`, `app.py`.

**Commit 2 — cron.py field-name bugs:**
```
phase-1: fix cron.py model-field bugs (digest + test-email)

- Win has title/description not content
- Event has date+time not starts_at
- guard admin-lookup against missing admin user
```
Stage exactly: `cron.py`.

**Commit 3 — backfill script + SoT update:**
```
phase-1: backfill script + sot — ghl client + taxonomy locked
```
Stage exactly: `scripts/backfill_ghl_tags.py`, `scripts/README.md`, `INTEGRATION-SOURCE-OF-TRUTH.md`.

Push after each commit (or batch at end — either is fine).

---

## Step 8 — Report back to manager

7-bullet summary:

1. **Lift status** — `lib/ghl.py` shipped, all 4 call sites migrated, `app.py` inline def removed (commit SHA).
2. **Tag taxonomy** — 9 stage tags locked, `ValueError` on any non-canonical tag, brand tags rejected.
3. **Custom fields** — 4 fields sync from `User` columns; confirm via `/admin` view of any test user.
4. **`cron.py`** — 3 bugs fixed; `flask cron digest` and `flask cron test-email` both run clean (commit SHA).
5. **Backfill script** — written + dry-run-tested; NOT executed against live GHL. Kashi runs `--apply` separately.
6. **Smoke tests** — all 9 from Step 5 pass.
7. **Surprises / new launch blockers** — anything found that demands a manager decision.

If any step requires an architectural decision (especially around tag mapping for an edge case the manager hasn't pre-decided), STOP and report — do not decide.
