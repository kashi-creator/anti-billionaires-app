"""Tests for the nightly reconciliation cron — `flask cron reconcile`.

The cron does three independent things:
  1. Patches User.referred_by from GHL contact's invited_by_referral_code
     for members where attribution was lost between RSVP and signup.
  2. Pulls live Stripe subscription status and reconciles
     User.subscription_status if it has drifted (catches missed webhooks).
  3. Re-pushes custom fields to GHL for every active member.

We test 1 and 2 directly; 3 just calls upsert_contact in a daemon thread
(already covered indirectly by the referral_qualification suite).
"""
from unittest.mock import patch, MagicMock


def _make_user(app, email, **kwargs):
    from models import db, User
    with app.app_context():
        u = User(
            email=email,
            password_hash="x",
            name=kwargs.pop("name", email.split("@")[0]),
            subscription_status=kwargs.pop("subscription_status", "active"),
            **kwargs,
        )
        db.session.add(u)
        db.session.commit()
        return u.id


def _get(app, user_id):
    from models import User
    with app.app_context():
        return User.query.get(user_id)


# --- Referrer reconciliation ---


def test_reconcile_referrers_patches_unattributed_member(app):
    """A member with referred_by=None gets fixed when GHL knows their inviter."""
    referrer_id = _make_user(app, "rec_ref@example.com", referral_code="RECREF1")
    orphan_id = _make_user(app, "rec_orphan@example.com",
                            stripe_customer_id="cus_REC_O")  # no referred_by

    with app.app_context(), \
         patch("app._resolve_referrer_from_ghl", return_value=referrer_id):
        from cron import _reconcile_referrers
        stats = _reconcile_referrers(dry_run=False)

    assert stats["patched"] == 1
    assert _get(app, orphan_id).referred_by == referrer_id


def test_reconcile_referrers_skips_users_already_attributed(app):
    """Members who already have referred_by are not retouched."""
    referrer_id = _make_user(app, "rec_skip@example.com", referral_code="RECSKIP")
    other_id = _make_user(app, "rec_other@example.com", referral_code="RECOTHER")
    attributed_id = _make_user(
        app, "rec_attr@example.com",
        stripe_customer_id="cus_REC_A",
        referred_by=referrer_id,
    )

    # GHL would say it's `other_id`, but we already have `referrer_id`.
    # The reconciler should not re-look-up since the field is already set.
    with app.app_context(), \
         patch("app._resolve_referrer_from_ghl", return_value=other_id):
        from cron import _reconcile_referrers
        stats = _reconcile_referrers(dry_run=False)

    assert stats["candidates"] == 0  # filter excluded the attributed user
    assert _get(app, attributed_id).referred_by == referrer_id


def test_reconcile_referrers_skips_pure_prospects(app):
    """Users without a stripe_customer_id are pure prospects (free signup,
    never paid). Don't reconcile them — they may not even exist long term."""
    referrer_id = _make_user(app, "pp_ref@example.com", referral_code="PPREF1")
    prospect_id = _make_user(app, "pp_prospect@example.com")  # no stripe_customer_id

    with app.app_context(), \
         patch("app._resolve_referrer_from_ghl", return_value=referrer_id):
        from cron import _reconcile_referrers
        stats = _reconcile_referrers(dry_run=False)

    assert stats["candidates"] == 0
    assert _get(app, prospect_id).referred_by is None


def test_reconcile_referrers_dry_run_does_not_write(app):
    referrer_id = _make_user(app, "dry_ref@example.com", referral_code="DRYREF1")
    orphan_id = _make_user(app, "dry_orphan@example.com",
                            stripe_customer_id="cus_DRY_O")

    with app.app_context(), \
         patch("app._resolve_referrer_from_ghl", return_value=referrer_id):
        from cron import _reconcile_referrers
        stats = _reconcile_referrers(dry_run=True)

    assert stats["patched"] == 1
    # But nothing actually written
    assert _get(app, orphan_id).referred_by is None


# --- Subscription reconciliation ---


def test_reconcile_subscriptions_flips_drifted_status(app):
    """User in DB shows 'active' but Stripe says 'canceled' → DB gets fixed."""
    import os
    os.environ["STRIPE_SECRET_KEY"] = "sk_test_real"  # not 'placeholder'

    user_id = _make_user(
        app, "sub_drift@example.com",
        stripe_customer_id="cus_SD",
        stripe_subscription_id="sub_SD",
        subscription_status="active",
    )

    fake_sub = {"status": "canceled"}

    with app.app_context(), \
         patch("stripe.Subscription.retrieve", return_value=fake_sub):
        from cron import _reconcile_subscriptions
        stats = _reconcile_subscriptions(dry_run=False)

    assert stats["drifted"] == 1
    assert _get(app, user_id).subscription_status == "canceled"


def test_reconcile_subscriptions_protects_lifetime_members(app):
    """Lifetime members had their sub canceled at qualification — that's
    expected. Don't downgrade them just because Stripe says canceled."""
    import os
    os.environ["STRIPE_SECRET_KEY"] = "sk_test_real"

    user_id = _make_user(
        app, "sub_lifer@example.com",
        stripe_customer_id="cus_SL",
        stripe_subscription_id="sub_SL",
        subscription_status="active",
        lifetime_access=True,
    )

    fake_sub = {"status": "canceled"}

    with app.app_context(), \
         patch("stripe.Subscription.retrieve", return_value=fake_sub):
        from cron import _reconcile_subscriptions
        stats = _reconcile_subscriptions(dry_run=False)

    assert stats["skipped_lifetime"] == 1
    # Status untouched
    assert _get(app, user_id).subscription_status == "active"


def test_reconcile_subscriptions_no_op_when_status_matches(app):
    """If DB and Stripe agree, nothing is written and drift count is 0."""
    import os
    os.environ["STRIPE_SECRET_KEY"] = "sk_test_real"

    _make_user(
        app, "sub_match@example.com",
        stripe_customer_id="cus_SM",
        stripe_subscription_id="sub_SM",
        subscription_status="active",
    )

    fake_sub = {"status": "active"}

    with app.app_context(), \
         patch("stripe.Subscription.retrieve", return_value=fake_sub):
        from cron import _reconcile_subscriptions
        stats = _reconcile_subscriptions(dry_run=False)

    assert stats["checked"] == 1
    assert stats["drifted"] == 0


def test_reconcile_subscriptions_skipped_when_stripe_unconfigured(app):
    """Placeholder Stripe key → no Stripe calls, function returns cleanly."""
    import os
    os.environ["STRIPE_SECRET_KEY"] = "sk_test_placeholder"

    _make_user(app, "sub_skip@example.com",
               stripe_customer_id="cus_SS", stripe_subscription_id="sub_SS")

    with app.app_context():
        from cron import _reconcile_subscriptions
        stats = _reconcile_subscriptions(dry_run=False)

    assert stats == {"checked": 0, "drifted": 0, "errors": 0, "skipped_lifetime": 0}


# --- Orchestrator ---


def test_run_nightly_reconcile_calls_all_three(app):
    """The orchestrator runs all three jobs even when one finds nothing."""
    import os
    os.environ["STRIPE_SECRET_KEY"] = "sk_test_placeholder"  # short-circuits sub job

    with app.app_context(), \
         patch("cron._reconcile_referrers", return_value={"candidates": 0, "patched": 0, "skipped": 0}) as m_ref, \
         patch("cron._reconcile_subscriptions", return_value={"checked": 0, "drifted": 0, "errors": 0, "skipped_lifetime": 0}) as m_sub, \
         patch("cron._resync_ghl_active_members", return_value={"actives": 0, "pushed": 0}) as m_ghl:
        from cron import run_nightly_reconcile
        run_nightly_reconcile(dry_run=True)

    m_ref.assert_called_once_with(dry_run=True)
    m_sub.assert_called_once_with(dry_run=True)
    m_ghl.assert_called_once_with(dry_run=True)
