# Phase 13 — Events cleanup (lock 6 canonical biweekly dates) + RSVP confirmation email with referral link

> Paste into a fresh Claude Code session in `/Users/kenneth/anti-billionaires-app`. **Two coupled goals** in one phase:
>
> 1. Wipe wrong-date duplicate Events from prod, lock the 6 canonical St. Pete chapter biweekly dates Kashi specified.
> 2. When a member RSVPs (going) to any event, send them a confirmation email that includes their personal referral-code invite link so they can invite brothers.

---

## Step 0 — Pull

```bash
git fetch origin && git status
```
Reset hard if behind: `git reset --hard origin/main`.

---

## Step 1 — Read first

1. `INTEGRATION-SOURCE-OF-TRUTH.md` §9 — Phase 3 entry on the events stack rework. Locked vocabulary for `event_type` and `recurrence_rule`. Pay attention: Phase 3 currently uses `first_and_last_thursday_monthly` for the St. Pete chapter biweekly. **Kashi's actual cadence is biweekly every-other-Thursday, NOT first-and-last-monthly.** Those produce different dates. This phase corrects that.
2. `models.py` Event model — fields `event_type`, `chapter`, `recurrence_rule`, `recurrence_parent_id`, `is_recurrence_template`, `date`, `time`, `location`. Plus `EventRSVP`.
3. `app.py` `_seed_content()` — see how Phase 3 currently seeds the St. Pete biweekly + Thursday lunch templates and how `_generate_upcoming_occurrences()` produces child rows.
4. `phase3_routes.py` — find `event_rsvp` handler. This is where you add the email send.
5. `email_send.py` — pattern for `send_password_reset`, `send_lifetime_unlocked`, etc. You'll add `send_event_rsvp_confirmation`.
6. `templates/emails/_layout.html` + an existing email template (e.g. `lifetime_unlocked.html`) — copy the styling shape for the new template.
7. `models.py` — confirm `User.referral_code` field exists. Confirm `User.ensure_referral_code()` method generates one if missing.
8. The existing referral landing route — `grep -rn "referral_landing\|/r/" app.py features_routes.py phase3_routes.py` — find the public route that consumes the referral code (the email link points to this URL).

---

## Step 2 — Decisions locked

### 2.1 Canonical St. Pete chapter dates (locked by Kashi 2026-05-09)

Six occurrences, every other Thursday at 6:30 PM EST, location "The Temple, 155 8th Street North, Saint Petersburg, FL 33701":

1. **Thursday, May 14, 2026** at 6:30 PM EST
2. **Thursday, May 28, 2026** at 6:30 PM EST
3. **Thursday, June 11, 2026** at 6:30 PM EST
4. **Thursday, June 25, 2026** at 6:30 PM EST
5. **Thursday, July 9, 2026** at 6:30 PM EST
6. **Thursday, July 23, 2026** at 6:30 PM EST

Pattern: biweekly every-other-Thursday, NOT first-and-last-monthly. Anchor date: May 14.

### 2.2 Recurrence rule expansion

Phase 3 locked `recurrence_rule` vocabulary at `none | every_thursday | first_and_last_thursday_monthly`. Add a new value: **`manual`**. Templates with `recurrence_rule="manual"` are NOT processed by `_generate_upcoming_occurrences()` — their child occurrences are seeded by hand in `_seed_content()` instead.

This is cleaner than adding `biweekly_thursday_anchored` to the auto-generator: the chapter cadence is short-term (6 dates total through July) and may shift as Kashi schedules future cohorts. Manual occurrences = full editorial control, no surprise auto-spawning.

Update the locked `RECURRENCE_RULES` set in `models.py`:
```python
RECURRENCE_RULES = {"none", "every_thursday", "first_and_last_thursday_monthly", "manual"}
```

Update the `@validates("recurrence_rule")` raise message accordingly.

### 2.3 Wipe + reseed strategy in `_seed_content()`

Modify `_seed_content()`'s events section:

1. **Wipe wrong-date children** of the St. Pete chapter biweekly template:
   ```python
   pete_template = Event.query.filter_by(
       title="St. Petersburg Chapter Biweekly",
       is_recurrence_template=True
   ).first()
   if pete_template:
       # Delete any child occurrences that don't match the canonical 6 dates
       canonical_dates = {date(2026, 5, 14), date(2026, 5, 28), date(2026, 6, 11),
                          date(2026, 6, 25), date(2026, 7, 9), date(2026, 7, 23)}
       stale = Event.query.filter(
           Event.recurrence_parent_id == pete_template.id,
           ~Event.date.in_(canonical_dates),
       ).all()
       for s in stale:
           # Cascade delete EventRSVP rows for stale occurrences (none expected; safe).
           EventRSVP.query.filter_by(event_id=s.id).delete()
           db.session.delete(s)
       # Update template's recurrence_rule from first_and_last_thursday_monthly → manual
       pete_template.recurrence_rule = "manual"
   ```

2. **Idempotently seed the 6 canonical occurrences** — for each date, check if a child Event with that date + parent already exists; create only if missing:
   ```python
   for d in sorted(canonical_dates):
       existing = Event.query.filter_by(
           recurrence_parent_id=pete_template.id,
           date=d,
       ).first()
       if existing:
           # Self-heal: ensure time/location match canonical
           existing.time = "6:30 PM EST"
           existing.location = "The Temple, 155 8th Street North, Saint Petersburg, FL 33701"
           continue
       child = Event(
           title=pete_template.title,
           description=pete_template.description,
           date=d,
           time="6:30 PM EST",
           location="The Temple, 155 8th Street North, Saint Petersburg, FL 33701",
           host_id=pete_template.host_id,
           cover_image=pete_template.cover_image,
           event_type="chapter_recurring",
           chapter=pete_template.chapter,
           recurrence_rule="none",
           recurrence_parent_id=pete_template.id,
           is_recurrence_template=False,
       )
       db.session.add(child)
   ```

3. **Don't touch the Thursday lunch template** (`every_thursday`) — Phase 3's auto-generator handles those correctly. They generate 8 weeks ahead from `date.today()`.

4. **Don't touch any non-recurrence-child Events** (member meetups, etc.).

### 2.4 RSVP confirmation email

When a member POSTs `going` to `/events/<id>/rsvp`:
- Existing flow: creates/updates `EventRSVP` row with status="going"
- NEW: also send a confirmation email to the RSVP'ing user

Email contains:
- Confirmation of which event + date/time/location
- A "bring your brothers" section with their personal referral link
- Reuse `current_user.ensure_referral_code()` to make sure they have one

Subject: `You're going. {event.title}, {event.date strftime "%B %d"}`

### 2.5 Referral link format

The email's referral link points to the existing public referral-landing route (where unsigned-in visitors land before they sign up — they enter the brotherhood "via" the referrer). After Phase 0C, this is the path that pre-fills the founder-code flow OR routes to the Stripe paywall depending on app state.

If the existing route is `/r/<code>`:
```
referral_url = url_for("features.referral_landing", code=current_user.referral_code, _external=True)
```

(Adjust the route name if grep step 1.8 found a different one.)

### 2.6 New email template

`templates/emails/event_rsvp_confirmation.html` and `.txt`. Match the visual pattern of `lifetime_unlocked.html` (centered, gold accents, manifesto voice). Body structure:

```
You're going.

{event.title}
{event.date_long}, {event.time}
{event.location}

[event details paragraph if event.description]

---

Bring your brothers.

The Society grows by one introduction at a time. If you know a man who'd
belong in the room, send him this link. He shows up through your line, you
both move closer to the lifetime threshold.

[ Your invite link ]
{referral_url}

---

See you there.
Sovereign Society
```

Voice rules same as the rest of the app: no em-dashes, no exclamation points, no AI-tells.

### 2.7 What does NOT happen

- Do NOT change Phase 3's `every_thursday` Thursday-lunch template — its auto-generated occurrences are correct.
- Do NOT add other event-type templates or new chapters in this phase.
- Do NOT add SMS or calendar (.ics) attachments — those are Phase 4 territory.
- Do NOT touch Phase 4 welcome-checklist auto-checks (they fire on RSVP via `_check_item_by_slug("rsvp-event")` — leave that wiring alone, ADD the email send adjacent to it, don't replace).
- Do NOT touch GHL pushes (Phase 1's GHL writes don't fire on RSVP — that's still Phase 4 scope).

---

## Step 3 — Implementation

### 3.1 `models.py` — extend RECURRENCE_RULES vocab

Find the validates decorator + frozenset for recurrence rules. Add `"manual"`. Update the error message:
```python
raise ValueError(f"recurrence_rule must be in {sorted(RECURRENCE_RULES)}, got {value!r}")
```

### 3.2 `app.py` `_seed_content()` events section — wipe + reseed canonical 6

Per § 2.3 above. Place this AFTER the existing template-creation block and BEFORE the `_generate_upcoming_occurrences(lunch_template, weeks_ahead=8)` call.

Important: the existing `_generate_upcoming_occurrences(pete_template, ...)` call from Phase 3 should now SKIP because the template's `recurrence_rule` is `manual`. Either:
- Modify `_generate_upcoming_occurrences` to early-return on `recurrence_rule == "manual"`, OR
- Just don't call it on the pete template anymore — only call it on `lunch_template`

The first option (skip in the helper) is more defensive — protects against future templates accidentally being set to `manual` without removing the call. Do that.

### 3.3 `phase3_routes.py` `event_rsvp` handler — add email send

Find the existing handler. After the EventRSVP commit + the auto-checklist call, ADD:
```python
if status == "going":
    try:
        from email_send import send_event_rsvp_confirmation
        current_user.ensure_referral_code()
        db.session.commit()
        referral_url = url_for("features.referral_landing", code=current_user.referral_code, _external=True)
        send_event_rsvp_confirmation(current_user, event, referral_url)
    except Exception as e:
        app.logger.warning("RSVP confirmation email failed (non-fatal): %s", e)
```

(Adjust `features.referral_landing` to the actual route name from Step 1.8.)

Wrap in try/except — email failure must NOT block the RSVP. Same graceful-degrade pattern as other email sends.

### 3.4 `email_send.py` — add `send_event_rsvp_confirmation`

```python
def send_event_rsvp_confirmation(user, event, referral_url):
    return send_email(
        to=user.email,
        subject=f"You're going. {event.title}, {event.date.strftime('%B %d')}",
        template="event_rsvp_confirmation",
        context={
            "user": user,
            "event": event,
            "referral_url": referral_url,
            "event_date_long": event.date.strftime("%A, %B %d, %Y"),
        },
    )
```

### 3.5 New email templates

`templates/emails/event_rsvp_confirmation.html` and `.txt` per § 2.6.

---

## Step 4 — What NOT to break

- The existing 3 stale events from Phase 3's bad recurrence (the `first_and_last_thursday_monthly` outputs that don't match Kashi's dates) are exactly what gets wiped — verify in step 5 they're gone.
- `Thursday Group Lunch` template + its weekly-recurring occurrences: untouched. Its 8-week generation continues.
- Member meetups (`event_type="member_meetup"`): untouched.
- RSVP for a `weekly_recurring` (lunch) event also gets the confirmation email — the email send logic isn't gated by event_type. Member RSVPs anything → gets the email.
- If a user RSVPs `interested` or `not_going` (not `going`), no email fires.
- Existing email-render fix from Phase 1 (`SERVER_NAME` env var for `_external=True`) must still hold — verify by smoke test 5 below.

---

## Step 5 — Smoke tests

Local Flask:

1. After app starts, query: `Event.query.filter_by(title="St. Petersburg Chapter Biweekly").filter_by(is_recurrence_template=False).order_by(Event.date).all()` — should return exactly 6 rows with the canonical dates above. No more, no fewer.
2. Each occurrence has `time="6:30 PM EST"`, `location="The Temple, 155 8th Street North, Saint Petersburg, FL 33701"`, `recurrence_parent_id` set, `is_recurrence_template=False`, `recurrence_rule="none"`.
3. Re-run `python app.py` (boots `_seed_content` again). Same query: still exactly 6 rows. Idempotent.
4. Hit `/events` (logged in as a member). The Chapter Events section shows the 6 canonical dates only. No stale dates.
5. RSVP `going` to one of the 6: an email is dispatched. With `RESEND_API_KEY` unset locally, the `[EMAIL STUB]` console prints the rendered text. Verify it contains the event title, the event date, the location, AND the referral link with the user's actual referral_code.
6. RSVP `interested` (not going): no email fires.
7. Member without a `referral_code` set: the handler calls `ensure_referral_code()`, generates one, the email link includes it.
8. RSVP to the Thursday Group Lunch (a different event type): the email still fires correctly, with the lunch's date/time/location.
9. Negative test: try to set a template's `recurrence_rule` to `not_a_real_value` in `flask shell` → ValueError raised (vocab still validated).

Production (after deploy):

10. After Railway redeploys this commit, query prod via the same `railway run` + `DATABASE_PUBLIC_URL` pattern: `Event.query.filter(Event.recurrence_parent_id == pete_template_id).order_by(Event.date)` should return exactly the 6 canonical dates. Manager will verify.
11. RSVP a real test event in prod (Kashi or Bryce). Email lands in inbox from `noreply@sovereignsociety.rich`. Subject is `You're going. {title}, {date}`. Body contains a working referral link.

---

## Step 6 — Update SoT

- §3 App Scope: extend the Events line — "RSVP triggers confirmation email with personal referral link."
- §8 Phase Status: Phase 13 ✅ done with commit SHA.
- §9 Decisions Log: append entry — recurrence_rule vocab extended with `manual`, canonical St. Pete biweekly dates locked at the 6 above (next-cohort scheduling will be manual reseed in `_seed_content` until a chapter-management UI ships in a future phase), RSVP confirmation email format + referral-link insertion.
- §10 Risks: 
  - Add: "Manual chapter-event scheduling will require code edit + redeploy for each new cohort. Acceptable for now (~6 events through July). If chapter cadence stabilizes, build an admin UI for adding chapter occurrences."
  - Add: "RSVP confirmation email reveals member's referral code in plaintext URL. If a member forwards this email, the recipient could pre-load the referrer code on signup. Intended behavior — that's the entire point of referral codes — flagging only because future GDPR-style privacy reviews might surface it."

---

## Step 7 — Commit + push

Three commits:

**Commit 1 — recurrence vocab + seed reset:**
```
phase-13: lock 6 canonical st-pete biweekly dates, add 'manual' recurrence vocab

Phase 3 used first_and_last_thursday_monthly which doesn't match the
actual cadence kashi locked: every-other-thursday biweekly anchored to
may 14. Instead of expanding the auto-generator with a new rule, add
'manual' to the vocabulary and seed the 6 dates by hand in
_seed_content. Cleaner editorial control + no surprise auto-spawning.

Wipes wrong-date children. Idempotent reseed (self-heals time +
location on existing matches, creates missing). Auto-generator early-
returns on recurrence_rule='manual'.
```
Stage exactly: `models.py`, `app.py`.

**Commit 2 — rsvp confirmation email:**
```
phase-13: rsvp confirmation email with personal referral link

When a member rsvps 'going' to any event, dispatch a confirmation email
with event details + their personal referral landing url. Brings new-
member acquisition into the rsvp flow without forcing a UI change.
Wrapped in try/except — email failure doesn't block the rsvp.
```
Stage exactly: `phase3_routes.py`, `email_send.py`, `templates/emails/event_rsvp_confirmation.html`, `templates/emails/event_rsvp_confirmation.txt`.

**Commit 3 — sot:**
```
phase-13: sot — events cleanup + rsvp email
```
Stage exactly: `INTEGRATION-SOURCE-OF-TRUTH.md`.

Push.

---

## Step 8 — Report back to manager

5 bullets:

1. **Vocab + recurrence helper** — manual added, generator early-returns. Validates negative test (smoke 9).
2. **6 canonical dates seeded** — query results from smoke 1+3.
3. **/events render** — Chapter Events section shows exactly 6 dates, no stale.
4. **Email tested** — `[EMAIL STUB]` output verbatim from a local RSVP test (paste it into the report so manager can verify the referral link is correctly formed).
5. **Surprises / blockers** — anything (e.g. `features.referral_landing` route name differs; an existing RSVP exists in prod that referenced one of the wiped dates — escalate before deletion; SERVER_NAME makes external URLs resolve unexpectedly).

If anything is genuinely ambiguous, STOP and report — don't decide.
