"""Transactional + engagement emails.

Falls back to console output when RESEND_API_KEY is not set, so dev/CI
work without external services.
"""
import os
import threading
from flask import render_template, current_app


def _render_pair(template_base, **context):
    """Render an email's HTML + text bodies from templates/emails/<base>.html|.txt."""
    html = render_template(f"emails/{template_base}.html", **context)
    text = render_template(f"emails/{template_base}.txt", **context)
    return html, text


def _send_via_resend(to, subject, text, html):
    import resend
    resend.api_key = os.environ["RESEND_API_KEY"]
    from_addr = os.environ.get("EMAIL_FROM", "onboarding@resend.dev")
    from_name = os.environ.get("EMAIL_FROM_NAME", "Sovereign Society")
    payload = {
        "from": f"{from_name} <{from_addr}>",
        "to": [to],
        "subject": subject,
        "text": text,
        "html": html,
    }
    reply_to = os.environ.get("EMAIL_REPLY_TO")
    if reply_to:
        payload["reply_to"] = reply_to
    resend.Emails.send(payload)


def _send_now(to, subject, text, html):
    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        print(f"\n[EMAIL STUB] To: {to}\n[EMAIL STUB] Subject: {subject}\n[EMAIL STUB] Body:\n{text}\n")
        return True
    try:
        _send_via_resend(to, subject, text, html)
        return True
    except Exception as e:
        print(f"[EMAIL ERROR] {e}")
        return False


def send_email(to, subject, body_text=None, body_html=None, template=None, context=None, async_=True):
    """Send an email. Either provide body_text/body_html OR a template + context.

    async_=True dispatches in a daemon thread so request handlers return fast.
    """
    if template:
        ctx = dict(context or {})
        ctx.setdefault("subject", subject)
        body_html, body_text = _render_pair(template, **ctx)
    if not body_text:
        body_text = ""
    if not body_html:
        body_html = body_text

    if async_:
        app = current_app._get_current_object() if current_app else None

        def _go():
            if app:
                with app.app_context():
                    _send_now(to, subject, body_text, body_html)
            else:
                _send_now(to, subject, body_text, body_html)

        threading.Thread(target=_go, daemon=True).start()
        return True
    return _send_now(to, subject, body_text, body_html)


# --- Typed helpers ---

def send_welcome_verify(user, verify_url):
    return send_email(
        to=user.email,
        subject="Welcome to Sovereign Society. Confirm your email",
        template="welcome_verify",
        context={"user": user, "verify_url": verify_url},
    )


def send_password_reset(user, reset_url, async_=True):
    return send_email(
        to=user.email,
        subject="Reset your password",
        template="password_reset",
        context={"user": user, "reset_url": reset_url},
        async_=async_,
    )


def send_payment_succeeded(user, amount_cents, payments_made, lifetime_unlocked=False):
    """Receipt to the paying user. payments_made is THIS user's count
    (toward their referrer's qualification at 6)."""
    return send_email(
        to=user.email,
        subject="Payment received. Sovereign Society",
        template="payment_succeeded",
        context={
            "user": user,
            "amount": f"${amount_cents/100:.2f}",
            "payments_made": payments_made,
            "payments_to_qualify": 6,
            "lifetime_unlocked": lifetime_unlocked,
        },
    )


def send_referral_progress(referrer, referee, qualified_count, threshold):
    """Sent to the referrer when one of their referees just hit 6 payments
    (i.e. they just locked in another qualified referral)."""
    return send_email(
        to=referrer.email,
        subject=f"{referee.name} just qualified. {qualified_count} of {threshold}",
        template="referral_qualified",
        context={
            "referrer": referrer,
            "referee": referee,
            "qualified_count": qualified_count,
            "threshold": threshold,
            "remaining": max(0, threshold - qualified_count),
        },
    )


def send_payment_failed(user, update_url):
    return send_email(
        to=user.email,
        subject="Action needed: payment failed",
        template="payment_failed",
        context={"user": user, "update_url": update_url},
    )


def send_lifetime_unlocked(user):
    return send_email(
        to=user.email,
        subject="You're in for life",
        template="lifetime_unlocked",
        context={"user": user},
    )


def send_complete_signup_reminder(email, name, complete_url, async_=True):
    """Remind someone who paid through Stripe Checkout but never finished
    creating their app account (no User row / password yet). Takes a raw
    email + name rather than a user object, because by definition no User
    exists for them yet."""
    return send_email(
        to=email,
        subject="Finish setting up your Sovereign Society account",
        template="complete_signup",
        context={"name": name or "there", "complete_url": complete_url},
        async_=async_,
    )


def send_weekly_digest(user, digest_data):
    return send_email(
        to=user.email,
        subject="This week at Sovereign Society",
        template="weekly_digest",
        context={"user": user, **digest_data},
    )


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
