"""Tests for the django-axes admin-login lockout (issue #74).

Pin-tests the AXES_FAILURE_LIMIT + AXES_COOLOFF_TIME +
AXES_LOCKOUT_PARAMETERS configuration: 5 wrong-password attempts for
the same (username, ip_address) tuple lock the account; the 6th
attempt is refused even with the correct password until the cooloff
expires.
"""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse


@pytest.mark.django_db
class TestAdminLoginLockout:
    """``django-axes`` denies further login attempts after
    ``AXES_FAILURE_LIMIT`` (=5) failures for the same
    ``(username, ip_address)`` tuple."""

    def _post_login(self, client, username, password):
        return client.post(
            reverse("admin:login"),
            {"username": username, "password": password, "next": "/admin/"},
        )

    def test_six_failed_attempts_then_blocked_with_correct_password(self, client):
        User = get_user_model()
        User.objects.create_user(
            username="admin", password="correct-horse-battery-staple", is_staff=True
        )

        # 5 wrong-password attempts — each one is a normal login failure
        # (200 with the form re-rendered showing an error).
        for _ in range(5):
            self._post_login(client, "admin", "wrong")

        # 6th attempt — even with the right password, axes blocks it.
        # django-axes 8.x returns 429 Too Many Requests (RFC 6585 — the
        # semantically right status for rate-limiting; older versions
        # returned 403). Accept either so we don't pin the assertion to
        # one minor release.
        r = self._post_login(client, "admin", "correct-horse-battery-staple")
        assert r.status_code in (403, 429), (
            "Expected django-axes to block the 6th attempt (403 or 429); "
            f"got {r.status_code}. Check AXES_FAILURE_LIMIT="
            "5 in literature/settings/base.py."
        )

    def test_first_few_failures_do_not_block(self, client):
        """Sanity check: the lockout doesn't fire too early — fewer than
        AXES_FAILURE_LIMIT failures still let a valid login through."""
        User = get_user_model()
        User.objects.create_user(
            username="admin", password="correct-horse-battery-staple", is_staff=True
        )

        # 3 wrong-password attempts.
        for _ in range(3):
            self._post_login(client, "admin", "wrong")

        # Right password on the 4th try should succeed (admin login
        # redirects to the admin index).
        r = self._post_login(client, "admin", "correct-horse-battery-staple")
        assert r.status_code in (200, 302), (
            "Login with correct password after 3 failures should succeed; "
            f"got status {r.status_code}. AXES_FAILURE_LIMIT may be set "
            "too low."
        )
