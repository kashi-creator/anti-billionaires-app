def test_app_imports(app):
    assert app is not None
    assert len(list(app.url_map.iter_rules())) > 50


def test_login_page_renders(client):
    res = client.get("/login")
    assert res.status_code == 200
    assert b"login" in res.data.lower() or b"sign in" in res.data.lower()


def test_pricing_page_renders(client):
    res = client.get("/pricing")
    assert res.status_code == 200


def test_signup_page_renders(client):
    res = client.get("/signup")
    assert res.status_code == 200


def test_root_serves_landing_unauthenticated(client):
    res = client.get("/")
    assert res.status_code == 200
    assert b"1%" in res.data or b"Men" in res.data or b"Apply" in res.data


def test_protected_route_redirects(client):
    res = client.get("/feed", follow_redirects=False)
    assert res.status_code in (301, 302)


def test_old_reset_pwd_route_is_removed(client):
    res = client.get("/reset-pwd/abmc2026reset")
    assert res.status_code == 404


def test_signup_no_longer_grants_admin(client, app):
    from models import db, User
    res = client.post("/signup", data={
        "name": "Test User",
        "email": "smoke@example.com",
        "password": "validpassword123",
        "confirm_password": "validpassword123",
    }, follow_redirects=False)
    assert res.status_code in (301, 302)
    with app.app_context():
        u = User.query.filter_by(email="smoke@example.com").first()
        assert u is not None
        assert u.is_admin is False
        assert u.subscription_status == "inactive"
        assert u.email_verified is False
        assert u.lifetime_access is False
        assert u.payments_made_count == 0


def test_forgot_password_page_renders(client):
    res = client.get("/forgot-password")
    assert res.status_code == 200


def test_forgot_password_does_not_leak_existence(client, app):
    res = client.post("/forgot-password", data={"email": "nobody@example.com"}, follow_redirects=False)
    assert res.status_code in (301, 302)


def test_reset_password_invalid_token_redirects(client):
    res = client.get("/reset-password/invalidtoken123", follow_redirects=False)
    assert res.status_code in (301, 302)


def test_verify_email_invalid_token_redirects(client):
    res = client.get("/verify-email/invalidtoken123", follow_redirects=False)
    assert res.status_code in (301, 302)


def test_lifetime_access_grants_active_subscription(app):
    from models import db, User
    with app.app_context():
        u = User(name="Lifer", email="lifer@example.com", password_hash="x",
                 lifetime_access=True, subscription_status="canceled")
        db.session.add(u)
        db.session.commit()
        assert u.has_active_subscription is True
