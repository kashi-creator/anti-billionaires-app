"""Tests for GHL upsert retry behaviour (lib/ghl.py).

Reproduces the silent-drop bug: a single transient GHL failure (timeout / 5xx)
permanently loses the contact, because upsert_contact POSTs once with no retry
inside a fire-and-forget daemon thread. After the fix, a transient failure is
retried and the contact lands — while permanent client errors (4xx) are not
retried.
"""
import requests
from unittest.mock import MagicMock


def _enable_ghl(monkeypatch):
    monkeypatch.setenv("GHL_API_KEY", "test-token")
    monkeypatch.setenv("GHL_LOCATION_ID", "test-loc")


def _run_synchronously(monkeypatch, ghl):
    """Run the fire-and-forget daemon thread inline and skip real backoff sleeps,
    so the test is deterministic."""
    class _SyncThread:
        def __init__(self, target=None, daemon=None, **kw):
            self._target = target

        def start(self):
            if self._target:
                self._target()

    monkeypatch.setattr(ghl.threading, "Thread", _SyncThread)
    monkeypatch.setattr(ghl.time, "sleep", lambda *a, **k: None)


def _resp(status):
    m = MagicMock()
    m.status_code = status
    m.text = f"status {status}"
    return m


def test_transient_failure_is_retried_until_success(app, monkeypatch):
    from lib import ghl
    _enable_ghl(monkeypatch)
    _run_synchronously(monkeypatch, ghl)

    calls = {"n": 0}

    def fake_post(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            raise requests.exceptions.Timeout("simulated GHL slowness")
        return _resp(200)

    monkeypatch.setattr(ghl.requests, "post", fake_post)

    with app.app_context():
        ghl.upsert_contact(email="t@example.com", name="T", stage_tag="active-member")

    # BUG: current code calls post exactly once and drops the contact on the
    # timeout. FIX: the 2nd attempt succeeds, so the contact lands.
    assert calls["n"] >= 2


def test_gives_up_after_bounded_attempts(app, monkeypatch):
    from lib import ghl
    _enable_ghl(monkeypatch)
    _run_synchronously(monkeypatch, ghl)

    calls = {"n": 0}

    def always_timeout(*a, **k):
        calls["n"] += 1
        raise requests.exceptions.Timeout("GHL down")

    monkeypatch.setattr(ghl.requests, "post", always_timeout)

    with app.app_context():
        ghl.upsert_contact(email="t@example.com", name="T", stage_tag="active-member")

    # Retries, but a bounded number of times — never loops forever.
    assert 2 <= calls["n"] <= 8


def test_no_retry_on_client_error(app, monkeypatch):
    from lib import ghl
    _enable_ghl(monkeypatch)
    _run_synchronously(monkeypatch, ghl)

    calls = {"n": 0}

    def bad_request(*a, **k):
        calls["n"] += 1
        return _resp(400)

    monkeypatch.setattr(ghl.requests, "post", bad_request)

    with app.app_context():
        ghl.upsert_contact(email="t@example.com", name="T", stage_tag="active-member")

    # A 400 is a permanent payload error — retrying won't help, so don't.
    assert calls["n"] == 1
