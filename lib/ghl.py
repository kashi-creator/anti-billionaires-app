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
import time
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
    # Validate inputs FIRST so misuse fails loudly even when env is unset.
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

    if not _enabled():
        log.debug("ghl.upsert_contact skipped: env unset")
        return

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
        # GHL v2 expects `customFields` (plural). Each entry: {id|key, value}.
        # The legacy `customField` (singular) + `field_value` shape returns 422.
        payload["customFields"] = [
            {"key": k, "value": "" if v is None else str(v)}
            for k, v in custom_fields.items()
        ]

    def _send():
        # Retry transient failures (timeouts, network errors, 5xx, 429) with
        # backoff so a momentary GHL hiccup doesn't permanently drop a contact —
        # the silent-drop that left paying members out of the CRM. A 4xx other
        # than 429 is a permanent payload/auth error, so we don't retry those.
        backoffs = [0, 2, 5, 12]  # 4 attempts spanning ~19s total
        email_for_log = payload.get("email")
        last = "unknown error"
        for attempt, wait in enumerate(backoffs):
            if wait:
                time.sleep(wait)
            try:
                r = requests.post(
                    f"{GHL_BASE}/contacts/upsert",
                    headers=_headers(),
                    json=payload,
                    timeout=15,
                )
                if r.status_code < 400:
                    if attempt:
                        log.info("ghl.upsert_contact recovered on attempt %d for %s",
                                 attempt + 1, email_for_log)
                    return
                if 400 <= r.status_code < 500 and r.status_code != 429:
                    log.warning("ghl.upsert_contact %s (permanent, no retry) for %s: %s",
                                r.status_code, email_for_log, r.text[:200])
                    return
                last = f"HTTP {r.status_code}: {r.text[:150]}"
            except Exception as e:
                last = repr(e)
            log.warning("ghl.upsert_contact attempt %d/%d failed for %s: %s",
                        attempt + 1, len(backoffs), email_for_log, last)
        # Exhausted all attempts. The nightly `flask cron reconcile` re-pushes
        # every active member, so this is recoverable within a day even now.
        log.error("ghl.upsert_contact GAVE UP after %d attempts for %s: %s",
                  len(backoffs), email_for_log, last)

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
    log.info("ghl.upsert_opportunity stub: %s -> %s", contact_email, stage_tag)


def health_check() -> dict:
    """Synchronous GHL connectivity probe. Returns a structured result so admins
    can see the actual reason a write would fail (env unset, 401, 422, network).

    Read-only: hits `GET /contacts/?locationId=...&limit=1`. No contacts are
    created or modified.
    """
    api_key = os.environ.get("GHL_API_KEY", "")
    location_id = os.environ.get("GHL_LOCATION_ID", "")
    result = {
        "api_key_set": bool(api_key),
        "location_id_set": bool(location_id),
        "enabled": _enabled(),
        "status_code": None,
        "latency_ms": None,
        "ok": False,
        "error": None,
        "response_excerpt": None,
    }
    if not result["enabled"]:
        result["error"] = "GHL_API_KEY and/or GHL_LOCATION_ID is unset on this environment."
        return result

    started = time.monotonic()
    try:
        r = requests.get(
            f"{GHL_BASE}/contacts/",
            headers=_headers(),
            params={"locationId": location_id, "limit": 1},
            timeout=10,
        )
        result["latency_ms"] = int((time.monotonic() - started) * 1000)
        result["status_code"] = r.status_code
        result["response_excerpt"] = r.text[:300]
        result["ok"] = r.status_code < 400
        if not result["ok"]:
            if r.status_code == 401:
                result["error"] = "401 Unauthorized — GHL_API_KEY is invalid, expired, or not scoped to this location."
            elif r.status_code == 403:
                result["error"] = "403 Forbidden — token lacks contacts.readonly scope for this location."
            elif r.status_code == 422:
                result["error"] = "422 Unprocessable — GHL_LOCATION_ID likely doesn't match the token's location."
            else:
                result["error"] = f"GHL returned HTTP {r.status_code}."
    except requests.exceptions.Timeout:
        result["latency_ms"] = int((time.monotonic() - started) * 1000)
        result["error"] = "Network timeout after 10s — GHL unreachable from this host."
    except Exception as e:
        result["latency_ms"] = int((time.monotonic() - started) * 1000)
        result["error"] = f"{type(e).__name__}: {e}"
    return result


def _upsert_contact_sync(
    *,
    email: str,
    name: str,
    phone: Optional[str] = None,
    stage_tag: Optional[str] = None,
    custom_fields: Optional[dict] = None,
    extra_tags: Optional[Iterable[str]] = None,
) -> Optional[str]:
    """Synchronous variant of upsert_contact that returns the GHL contact id.

    Used by flows that need to chain follow-up calls (e.g. send a Conversations
    message to the just-upserted contact). Same validation rules as
    upsert_contact. Returns None on any failure or when GHL is unconfigured.
    """
    if stage_tag and stage_tag not in STAGE_TAGS:
        raise ValueError(f"stage_tag must be one of {STAGE_TAGS}, got {stage_tag!r}")

    tags = []
    if stage_tag:
        tags.append(stage_tag)
    if extra_tags:
        for t in extra_tags:
            if t in STAGE_TAGS:
                raise ValueError(f"{t!r} is a stage tag — pass via stage_tag=")
            tags.append(t)

    if not _enabled():
        return None

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
        payload["customFields"] = [
            {"key": k, "value": "" if v is None else str(v)}
            for k, v in custom_fields.items()
        ]

    try:
        r = requests.post(
            f"{GHL_BASE}/contacts/upsert",
            headers=_headers(),
            json=payload,
            timeout=10,
        )
        if r.status_code >= 400:
            log.warning("ghl._upsert_contact_sync %s: %s", r.status_code, r.text[:200])
            return None
        return (r.json().get("contact") or {}).get("id")
    except Exception as e:
        log.warning("ghl._upsert_contact_sync failed: %s", e)
        return None


def send_email_to_contact(*, contact_id: str, subject: str, html: str) -> bool:
    """Send a one-off email to a GHL contact via Conversations API. Synchronous.

    Returns True on 2xx, False otherwise. Caller is expected to be running
    inside a daemon thread if it wants fail-silent semantics.
    """
    if not (_enabled() and contact_id):
        return False
    payload = {
        "type": "Email",
        "contactId": contact_id,
        "subject": subject,
        "html": html,
    }
    try:
        r = requests.post(
            f"{GHL_BASE}/conversations/messages",
            headers=_headers(),
            json=payload,
            timeout=10,
        )
        if r.status_code >= 400:
            log.warning("ghl.send_email_to_contact %s: %s", r.status_code, r.text[:200])
            return False
        return True
    except Exception as e:
        log.warning("ghl.send_email_to_contact failed: %s", e)
        return False


def send_sms_to_contact(*, contact_id: str, message: str) -> bool:
    """Send a one-off SMS to a GHL contact via Conversations API. Synchronous."""
    if not (_enabled() and contact_id):
        return False
    payload = {
        "type": "SMS",
        "contactId": contact_id,
        "message": message,
    }
    try:
        r = requests.post(
            f"{GHL_BASE}/conversations/messages",
            headers=_headers(),
            json=payload,
            timeout=10,
        )
        if r.status_code >= 400:
            log.warning("ghl.send_sms_to_contact %s: %s", r.status_code, r.text[:200])
            return False
        return True
    except Exception as e:
        log.warning("ghl.send_sms_to_contact failed: %s", e)
        return False


def find_contact_id_by_email(email: str) -> Optional[str]:
    """Look up a GHL contact id by exact email. Returns None if not found."""
    if not _enabled():
        return None
    try:
        r = requests.get(
            f"{GHL_BASE}/contacts/",
            headers=_headers(),
            params={
                "locationId": os.environ["GHL_LOCATION_ID"],
                "query": email,
                "limit": 25,
            },
            timeout=10,
        )
        if r.status_code >= 400:
            log.warning("ghl.find_contact_id_by_email %s: %s", r.status_code, r.text[:200])
            return None
        target = email.lower().strip()
        for c in (r.json().get("contacts") or []):
            if (c.get("email") or "").lower().strip() == target:
                return c.get("id")
        return None
    except Exception as e:
        log.warning("ghl.find_contact_id_by_email failed: %s", e)
        return None


def register_meeting_rsvp(
    *,
    email: str,
    name: str,
    phone: Optional[str] = None,
    sms_opt_in: bool = False,
    invited_by: Optional[str] = None,
    invited_by_referral_code: Optional[str] = None,
    rsvp_source: str = "invite-link",
    meeting_date: str = "",
    meeting_time: str = "",
    meeting_location: str = "",
    founder_email: Optional[str] = None,
) -> None:
    """Push a meeting-RSVP to GHL and fire the confirmation email/SMS plus
    founder notification — all in a single fire-and-forget daemon thread.

    Guests aren't members yet — no User row is created. They enter GHL as a
    `prospect` with `meeting-rsvp` + `invite-page` (+ `sms-opted-in` when
    opted in). The actual sends are routed through GHL's Conversations API
    (LC Email + LC Phone) so we don't need a separate SMTP / Twilio account.

    `invited_by` is the inviter's first name (human-readable, not unique).
    `invited_by_referral_code` is the inviter's machine-friendly id used for
    reverse-lookup on conversion — when a guest later signs up, the GHL
    contact still carries this code so we can resolve them back to the right
    User row even if the session cookie has expired.

    Fail-silent: any individual step that errors gets logged but does not
    affect the user-facing route or block subsequent steps.
    """
    extra_tags = ["meeting-rsvp", "invite-page"]
    if sms_opt_in:
        extra_tags.append("sms-opted-in")

    custom_fields = {
        "sms_opt_in": "true" if sms_opt_in else "false",
        "rsvp_source": rsvp_source,
        "invited_by": invited_by or "",
        "invited_by_referral_code": invited_by_referral_code or "",
    }

    def _run():
        contact_id = _upsert_contact_sync(
            email=email,
            name=name,
            phone=phone,
            stage_tag="prospect",
            extra_tags=extra_tags,
            custom_fields=custom_fields,
        )
        if not contact_id:
            log.warning("register_meeting_rsvp: upsert returned no contact_id; skipping sends")
            return

        first_name = (name.split() or [name])[0]
        host = invited_by or "A member"

        confirm_subject = f"You're in. The next gathering — {meeting_date}." if meeting_date else "You're in. The next gathering."
        confirm_html = _render_confirmation_html(
            first_name=first_name,
            host=host,
            meeting_date=meeting_date,
            meeting_time=meeting_time,
            meeting_location=meeting_location,
        )
        send_email_to_contact(contact_id=contact_id, subject=confirm_subject, html=confirm_html)

        if sms_opt_in and phone:
            sms_body = _render_confirmation_sms(
                first_name=first_name,
                meeting_date=meeting_date,
                meeting_time=meeting_time,
                meeting_location=meeting_location,
            )
            send_sms_to_contact(contact_id=contact_id, message=sms_body)

        # Founder notification (email-only).
        if founder_email:
            founder_id = find_contact_id_by_email(founder_email)
            if founder_id:
                send_email_to_contact(
                    contact_id=founder_id,
                    subject=f"New RSVP: {name} (invited by {host})",
                    html=_render_founder_html(
                        name=name, email=email, phone=phone or "(not provided)",
                        sms_opt_in=sms_opt_in, host=host,
                        meeting_date=meeting_date, meeting_time=meeting_time,
                        meeting_location=meeting_location,
                    ),
                )
            else:
                log.warning("register_meeting_rsvp: founder contact %s not found in GHL", founder_email)

    threading.Thread(target=_run, daemon=True).start()


def _render_confirmation_html(*, first_name, host, meeting_date, meeting_time, meeting_location):
    where = meeting_location or "(location TBD — we'll send details soon)"
    when = " · ".join(x for x in (meeting_date, meeting_time) if x) or "(time TBD — we'll send details soon)"
    return f"""\
<!DOCTYPE html>
<html><body style="margin:0;background:#0A0A0A;color:#E8E8E8;font-family:Georgia,'Times New Roman',serif;padding:32px 24px;">
<div style="max-width:560px;margin:0 auto;">
  <p style="font-size:11px;letter-spacing:4px;text-transform:uppercase;color:#D4AF37;margin:0 0 24px;">Sovereign Society</p>
  <p style="font-size:18px;line-height:1.55;color:#E8E8E8;margin:0 0 18px;">{first_name},</p>
  <p style="font-size:16px;line-height:1.7;color:#bdbdbd;margin:0 0 18px;">{host} brought you to the table.</p>
  <p style="font-size:16px;line-height:1.7;color:#bdbdbd;margin:0 0 28px;">Here's what you need to know:</p>
  <p style="font-size:15px;line-height:1.7;color:#E8E8E8;margin:0 0 12px;"><strong style="color:#D4AF37;">When:</strong> {when}</p>
  <p style="font-size:15px;line-height:1.7;color:#E8E8E8;margin:0 0 28px;"><strong style="color:#D4AF37;">Where:</strong> {where}</p>
  <p style="font-size:15px;line-height:1.7;color:#bdbdbd;margin:0 0 16px;">A small, private gathering of sovereign men. Capital, discipline, brotherhood. Come prepared to listen, contribute, and meet men who play the long game.</p>
  <p style="font-size:15px;line-height:1.7;color:#bdbdbd;margin:0 0 16px;">Show up sharp. Show up early. Bring nothing but your presence.</p>
  <p style="font-size:15px;line-height:1.7;color:#E8E8E8;margin:32px 0 4px;">See you at the table.</p>
  <p style="font-size:13px;line-height:1.7;color:#888;margin:0;">— Sovereign Society</p>
</div>
</body></html>
"""


def _render_confirmation_sms(*, first_name, meeting_date, meeting_time, meeting_location):
    when = " · ".join(x for x in (meeting_date, meeting_time) if x) or "details to follow"
    where = meeting_location or "details to follow"
    return f"{first_name}, you're confirmed for Sovereign Society — {when}. {where}. See you there."


def _render_founder_html(*, name, email, phone, sms_opt_in, host, meeting_date, meeting_time, meeting_location):
    when = " · ".join(x for x in (meeting_date, meeting_time) if x) or "(none set)"
    return f"""\
<!DOCTYPE html>
<html><body style="font-family:-apple-system,sans-serif;color:#222;padding:24px;">
<h2 style="margin:0 0 16px;">New RSVP — Sovereign Society</h2>
<table style="border-collapse:collapse;font-size:14px;">
  <tr><td style="padding:4px 14px 4px 0;color:#666;">Name</td><td>{name}</td></tr>
  <tr><td style="padding:4px 14px 4px 0;color:#666;">Email</td><td>{email}</td></tr>
  <tr><td style="padding:4px 14px 4px 0;color:#666;">Phone</td><td>{phone}</td></tr>
  <tr><td style="padding:4px 14px 4px 0;color:#666;">SMS opt-in</td><td>{'yes' if sms_opt_in else 'no'}</td></tr>
  <tr><td style="padding:4px 14px 4px 0;color:#666;">Invited by</td><td>{host}</td></tr>
  <tr><td style="padding:4px 14px 4px 0;color:#666;">Meeting</td><td>{when}</td></tr>
  <tr><td style="padding:4px 14px 4px 0;color:#666;">Location</td><td>{meeting_location or '(none set)'}</td></tr>
</table>
</body></html>
"""


def list_contacts(max_pages: int = 25) -> list:
    """Page through all contacts in the location via GHL's cursor pagination
    (startAfter/startAfterId — the v2 API rejects `offset`). Returns a list of
    contact dicts (id, tags, phone, email, ...). Empty on failure."""
    if not _enabled():
        return []
    out: list = []
    params = {"locationId": os.environ["GHL_LOCATION_ID"], "limit": 100}
    for _ in range(max_pages):
        try:
            r = requests.get(f"{GHL_BASE}/contacts/", headers=_headers(), params=params, timeout=15)
            if r.status_code >= 400:
                log.warning("ghl.list_contacts %s: %s", r.status_code, r.text[:150])
                break
            data = r.json()
            batch = data.get("contacts") if isinstance(data, dict) else data
            if not batch:
                break
            out.extend(batch)
            meta = (data.get("meta") if isinstance(data, dict) else {}) or {}
            saf, safid = meta.get("startAfter"), meta.get("startAfterId")
            if len(batch) < 100 or not safid:
                break
            params["startAfter"], params["startAfterId"] = saf, safid
        except Exception as e:
            log.warning("ghl.list_contacts failed: %s", e)
            break
    return out


# ===== Door / kiosk walk-in check-in =====
# The iPad at the door runs /kiosk -> QR -> /checkin. Each scan captures the
# guest into GHL, tags attendance, increments the `meetings_attended` custom
# field, and (for a NON-member's 2nd+ visit) applies `used-2-meetings` which
# fires the post-meeting hard-close workflow. Tags are ADDED, never replaced,
# so checking in an existing member never wipes their stage tag.

_MEETINGS_ATTENDED_KEY = "contact.meetings_attended"
_field_id_cache: dict = {}


def _custom_field_id(field_key: str) -> Optional[str]:
    """Resolve a custom field's id by its fieldKey (cached)."""
    if field_key in _field_id_cache:
        return _field_id_cache[field_key]
    if not _enabled():
        return None
    try:
        r = requests.get(
            f"{GHL_BASE}/locations/{os.environ['GHL_LOCATION_ID']}/customFields",
            headers=_headers(), timeout=10,
        )
        for f in (r.json().get("customFields") or []):
            if f.get("fieldKey") == field_key:
                _field_id_cache[field_key] = f.get("id")
                return f.get("id")
    except Exception as e:
        log.warning("ghl._custom_field_id failed: %s", e)
    return None


def _get_contact(contact_id: str) -> Optional[dict]:
    if not (_enabled() and contact_id):
        return None
    try:
        r = requests.get(f"{GHL_BASE}/contacts/{contact_id}", headers=_headers(), timeout=10)
        if r.status_code >= 400:
            return None
        return r.json().get("contact") or {}
    except Exception as e:
        log.warning("ghl._get_contact failed: %s", e)
        return None


def _find_contact_id_by_phone(phone: str) -> Optional[str]:
    """Match a contact by the last 10 digits of the phone."""
    if not (_enabled() and phone):
        return None
    target = "".join(ch for ch in phone if ch.isdigit())[-10:]
    if not target:
        return None
    try:
        r = requests.get(
            f"{GHL_BASE}/contacts/", headers=_headers(),
            params={"locationId": os.environ["GHL_LOCATION_ID"], "query": phone, "limit": 20},
            timeout=10,
        )
        for c in (r.json().get("contacts") or []):
            cp = "".join(ch for ch in (c.get("phone") or "") if ch.isdigit())[-10:]
            if cp and cp == target:
                return c.get("id")
    except Exception as e:
        log.warning("ghl._find_contact_id_by_phone failed: %s", e)
    return None


def _add_tags(contact_id: str, tags: Iterable[str]) -> None:
    """Append tags to a contact WITHOUT replacing existing ones."""
    tags = [t for t in tags if t]
    if not (_enabled() and contact_id and tags):
        return
    try:
        requests.post(
            f"{GHL_BASE}/contacts/{contact_id}/tags", headers=_headers(),
            json={"tags": list(tags)}, timeout=10,
        )
    except Exception as e:
        log.warning("ghl._add_tags failed: %s", e)


def register_door_checkin(*, name: str, phone: str, email: Optional[str] = None) -> None:
    """Capture a walk-in from the door kiosk. Fire-and-forget daemon thread.

    - Resolves (or creates) the GHL contact by email/phone WITHOUT passing tags,
      so an existing member's stage tag is never clobbered.
    - Increments the `meetings_attended` numeric custom field.
    - Adds `meeting-checkin` + `sms-opted-in` (+ `prospect` only for non-members).
    - On a non-member's 2nd+ visit, adds `used-2-meetings` to fire the hard-close.
    Fail-silent: any step that errors is logged but never blocks the door route.
    """
    def _run():
        if not _enabled():
            log.debug("register_door_checkin skipped: GHL env unset")
            return
        loc = os.environ["GHL_LOCATION_ID"]

        # 1. Resolve or create the contact (no tags passed -> never clobbers).
        contact_id = None
        if email:
            contact_id = find_contact_id_by_email(email)
        if not contact_id:
            contact_id = _find_contact_id_by_phone(phone)
        if not contact_id:
            payload = {"locationId": loc, "name": name, "phone": phone}
            if email:
                payload["email"] = email.lower().strip()
            try:
                r = requests.post(f"{GHL_BASE}/contacts/upsert", headers=_headers(), json=payload, timeout=10)
                if r.status_code < 400:
                    contact_id = (r.json().get("contact") or {}).get("id")
            except Exception as e:
                log.warning("register_door_checkin create failed: %s", e)
        if not contact_id:
            log.warning("register_door_checkin: could not resolve contact for %r", name)
            return

        contact = _get_contact(contact_id) or {}
        existing_tags = {(t or "").lower() for t in (contact.get("tags") or [])}
        is_member = bool(existing_tags & {"active-member", "lifetime-qualified"})

        # 2. Read + increment meetings_attended.
        fid = _custom_field_id(_MEETINGS_ATTENDED_KEY)
        current = 0
        for cf in (contact.get("customFields") or []):
            if cf.get("id") == fid:
                try:
                    current = int(float(cf.get("value") or 0))
                except (TypeError, ValueError):
                    current = 0
        new_count = current + 1
        if fid:
            try:
                requests.put(
                    f"{GHL_BASE}/contacts/{contact_id}", headers=_headers(),
                    json={"customFields": [{"id": fid, "value": str(new_count)}]}, timeout=10,
                )
            except Exception as e:
                log.warning("register_door_checkin field update failed: %s", e)

        # 3. Tags (append-only). Prospect stage only for non-members.
        add = ["meeting-checkin", "sms-opted-in"]
        if not is_member:
            add.append("prospect")
        if not is_member and new_count >= 2:
            add.append("used-2-meetings")  # fires the hard-close workflow
        _add_tags(contact_id, add)
        log.info("door check-in: %r visit #%d member=%s tags+=%s", name, new_count, is_member, add)

    threading.Thread(target=_run, daemon=True).start()


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


def sync_referrer_to_ghl(referrer) -> None:
    """Push the latest referral counters to a referrer's GHL contact card.

    Called from the Stripe payment webhook whenever a referrer's
    qualified_referrals_count changes (or when they hit lifetime).
    Lets Kashi see live referral counts in GHL without leaving the CRM.

    Fail-silent (daemon thread inside upsert_contact). If the referrer
    has no email or GHL is disabled, no-ops cleanly.
    """
    if not referrer or not referrer.email:
        return
    stage = "lifetime-qualified" if referrer.lifetime_access else "active-member"
    upsert_contact(
        email=referrer.email,
        name=referrer.name or "",
        stage_tag=stage,
        custom_fields=custom_fields_from_user(referrer),
    )
