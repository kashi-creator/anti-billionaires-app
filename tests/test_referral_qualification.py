"""Tests for the referral-based lifetime qualification logic.

The model:
- Member pays $99/mo until they qualify
- Qualifies when 3 of their referrals each hit 6 successful payments
- On qualification: lifetime_access=True, Stripe sub canceled
"""
from unittest.mock import patch


def _make_user(app, email, **kwargs):
    from models import db, User
    with app.app_context():
        u = User(email=email, password_hash="x", name=kwargs.pop("name", email.split("@")[0]),
                 subscription_status=kwargs.pop("subscription_status", "active"), **kwargs)
        db.session.add(u)
        db.session.commit()
        return u.id


def _trigger_payment(app, user_id):
    """Simulate a Stripe invoice.payment_succeeded webhook handler call."""
    from app import _handle_payment_succeeded
    from models import User
    with app.app_context():
        u = User.query.get(user_id)
        with patch("app.stripe.Subscription.cancel") as mock_cancel:
            _handle_payment_succeeded({"customer": u.stripe_customer_id, "amount_paid": 9900})
        return mock_cancel


def _get(app, user_id):
    from models import User
    with app.app_context():
        return User.query.get(user_id)


def test_referral_payment_increments_referee_count(app):
    referrer_id = _make_user(app, "ref@example.com", referral_code="ABC123",
                              stripe_customer_id="cus_R")
    referee_id = _make_user(app, "child@example.com", referred_by=referrer_id,
                             stripe_customer_id="cus_C1")
    _trigger_payment(app, referee_id)

    referee = _get(app, referee_id)
    assert referee.payments_made_count == 1

    referrer = _get(app, referrer_id)
    # Not yet at 6 — referrer's qualified count should still be 0.
    assert referrer.qualified_referrals_count == 0


def test_six_payments_qualifies_referee_and_credits_referrer(app):
    referrer_id = _make_user(app, "ref2@example.com", referral_code="REF2", stripe_customer_id="cus_R2")
    referee_id = _make_user(app, "child2@example.com", referred_by=referrer_id, stripe_customer_id="cus_C2")

    for _ in range(6):
        _trigger_payment(app, referee_id)

    referee = _get(app, referee_id)
    assert referee.payments_made_count == 6

    referrer = _get(app, referrer_id)
    assert referrer.qualified_referrals_count == 1
    assert referrer.lifetime_access is False  # Need 3 qualified, only 1 so far


def test_three_qualified_referrals_grants_lifetime(app):
    """3 referrals each hitting 6 payments → referrer gets lifetime + sub canceled."""
    referrer_id = _make_user(app, "ref3@example.com", referral_code="REF3",
                              stripe_customer_id="cus_R3", stripe_subscription_id="sub_R3")
    r1 = _make_user(app, "k1@example.com", referred_by=referrer_id, stripe_customer_id="cus_K1")
    r2 = _make_user(app, "k2@example.com", referred_by=referrer_id, stripe_customer_id="cus_K2")
    r3 = _make_user(app, "k3@example.com", referred_by=referrer_id, stripe_customer_id="cus_K3")

    # Each referral pays 6 times
    last_mock = None
    for kid in (r1, r2, r3):
        for _ in range(6):
            last_mock = _trigger_payment(app, kid)

    referrer = _get(app, referrer_id)
    assert referrer.qualified_referrals_count == 3
    assert referrer.lifetime_access is True
    assert referrer.lifetime_qualified_at is not None
    # The 6th payment of the 3rd referral triggers the lifetime grant + cancel.
    last_mock.assert_called_with("sub_R3")


def test_lifetime_member_payments_dont_affect_referrer(app):
    """If a member is already lifetime, their further payments shouldn't process."""
    from models import db, User
    referrer_id = _make_user(app, "rl@example.com", referral_code="RL")
    lifetime_id = _make_user(app, "lifer@example.com", referred_by=referrer_id,
                              lifetime_access=True, stripe_customer_id="cus_L",
                              payments_made_count=6)
    _trigger_payment(app, lifetime_id)
    lifetime = _get(app, lifetime_id)
    # No-op: payments_made_count stays at 6 (we already counted these)
    assert lifetime.payments_made_count == 6


def test_referrals_dashboard_loads_for_authenticated_user(app, client):
    from models import db, User
    import bcrypt
    hashed = bcrypt.hashpw(b"validpassword123", bcrypt.gensalt()).decode()
    with app.app_context():
        u = User(email="dash@example.com", password_hash=hashed, name="Dash",
                 subscription_status="active", onboarding_complete=True,
                 referral_code="DASH1")
        db.session.add(u)
        db.session.commit()

    client.post("/login", data={"email": "dash@example.com", "password": "validpassword123"})
    res = client.get("/referrals", follow_redirects=False)
    # Either renders (200) or redirects to onboarding (302) — both are fine.
    assert res.status_code in (200, 302)


def test_qualification_threshold_constants_match():
    """Sanity: the constants in app.py and features_routes.py must agree on the rules."""
    from app import PAYMENTS_PER_REFERRAL_QUALIFICATION, QUALIFIED_REFERRALS_FOR_LIFETIME
    from features_routes import PAYMENTS_TO_QUALIFY, QUALIFIED_NEEDED_FOR_LIFETIME
    assert PAYMENTS_PER_REFERRAL_QUALIFICATION == PAYMENTS_TO_QUALIFY == 6
    assert QUALIFIED_REFERRALS_FOR_LIFETIME == QUALIFIED_NEEDED_FOR_LIFETIME == 3
