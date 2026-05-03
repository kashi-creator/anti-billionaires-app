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
    log.info("ghl.upsert_opportunity stub: %s -> %s", contact_email, stage_tag)


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
