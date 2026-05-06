"""Web Push delivery for the Sovereign Society PWA.

Reads VAPID keys from env (see scripts/generate_vapid_keys.py).
Use `send_push_to_user(user_id, title, body, url)` from request handlers —
it dispatches the actual HTTP send on a daemon thread so the request returns
immediately.
"""
import json
import logging
import os
import threading

from flask import current_app

try:
    from pywebpush import webpush, WebPushException
    _PYWEBPUSH_AVAILABLE = True
except ImportError:  # dependency not installed yet (e.g. pre-deploy)
    _PYWEBPUSH_AVAILABLE = False
    webpush = None
    WebPushException = Exception  # type: ignore

log = logging.getLogger(__name__)


def vapid_public_key() -> str:
    """Public VAPID key, base64url-encoded. Returned to the browser so it can
    register a push subscription bound to our server. Empty string disables
    push entirely on the frontend."""
    return os.environ.get("VAPID_PUBLIC_KEY", "").strip()


def _vapid_private_key() -> str:
    return os.environ.get("VAPID_PRIVATE_KEY", "").strip()


def _vapid_claims() -> dict:
    email = os.environ.get("VAPID_CLAIM_EMAIL", "").strip()
    if not email:
        return {}
    return {"sub": email}


def push_configured() -> bool:
    return bool(_PYWEBPUSH_AVAILABLE and vapid_public_key() and _vapid_private_key())


def send_push_to_user(user_id: int, title: str, body: str, url: str = "/feed") -> None:
    """Fire-and-forget. Dispatches a Web Push to every active subscription
    belonging to the user. Safe to call inside a request handler — the network
    work happens on a daemon thread."""
    if not push_configured():
        return

    try:
        app = current_app._get_current_object()  # capture before leaving request ctx
    except RuntimeError:
        log.warning("send_push_to_user called outside app context; skipping")
        return

    payload = json.dumps({
        "title": title,
        "body": body,
        "url": url,
        "icon": "/static/img/icons/icon-192.png",
        "badge": "/static/img/icons/icon-192.png",
    })

    threading.Thread(
        target=_deliver,
        args=(app, user_id, payload),
        daemon=True,
    ).start()


def _deliver(app, user_id: int, payload: str) -> None:
    """Runs on the daemon thread. Opens its own app context + DB session."""
    from models import db, PushSubscription  # local import to avoid circulars

    with app.app_context():
        try:
            subs = PushSubscription.query.filter_by(user_id=user_id).all()
        except Exception as e:
            log.warning("push: failed to load subscriptions for user %s: %s", user_id, e)
            return

        if not subs:
            return

        stale_ids: list[int] = []
        for sub in subs:
            try:
                webpush(
                    subscription_info={
                        "endpoint": sub.endpoint,
                        "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                    },
                    data=payload,
                    vapid_private_key=_vapid_private_key(),
                    vapid_claims=dict(_vapid_claims()),  # webpush mutates the dict
                    ttl=60 * 60 * 24,  # 1 day
                )
            except WebPushException as e:
                status = getattr(e.response, "status_code", None) if e.response is not None else None
                # 404/410 = subscription is gone (user uninstalled, browser purged it)
                if status in (404, 410):
                    stale_ids.append(sub.id)
                else:
                    log.warning("push send failed (status=%s) for sub %s: %s", status, sub.id, e)
            except Exception as e:
                log.warning("push send unexpected error for sub %s: %s", sub.id, e)

        if stale_ids:
            try:
                PushSubscription.query.filter(PushSubscription.id.in_(stale_ids)).delete(
                    synchronize_session=False
                )
                db.session.commit()
            except Exception as e:
                log.warning("push: failed to clean stale subs %s: %s", stale_ids, e)
                db.session.rollback()
