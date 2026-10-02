from datetime import timedelta

import pytest
from django.contrib.sessions.models import Session
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import LoginBucket, User

pytestmark = pytest.mark.django_db


def csrf(client):
    return client.get("/api/v1/auth/csrf").json()["csrf_token"]


def signin(client, username="vilma", password="test-password-123!"):
    return client.post(
        "/api/v1/auth/login",
        {"username": username, "password": password},
        format="json",
        HTTP_X_CSRFTOKEN=csrf(client),
    )


def test_login_requires_csrf_and_hides_password(user):
    client = APIClient(enforce_csrf_checks=True)
    bad = client.post(
        "/api/v1/auth/login", {"username": user.username, "password": "test-password-123!"}
    )
    assert bad.status_code == 403 and bad.json()["code"] == "CSRF_FAILED"
    response = signin(client)
    assert response.status_code == 200
    assert "password" not in response.json()
    assert client.cookies["sessionid"]["httponly"]
    assert client.cookies["sessionid"]["samesite"] == "Lax"
    assert 43190 <= client.cookies["sessionid"]["max-age"] <= 43200
    assert client.get("/api/v1/auth/me").json()["id"] == str(user.id)


def test_expired_session_and_logout(user):
    client = APIClient(enforce_csrf_checks=True)
    assert client.get("/api/v1/auth/me").status_code == 401
    assert signin(client).status_code == 200
    Session.objects.update(expire_date=timezone.now() - timedelta(seconds=1))
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401 and response.json()["code"] == "SESSION_EXPIRED"
    signin(client)
    response = client.post("/api/v1/auth/logout", HTTP_X_CSRFTOKEN=csrf(client))
    assert response.status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401


def test_password_change_rotates_session_and_revokes_other_sessions(user):
    user.password_change_required = True
    user.save()
    first, second = APIClient(enforce_csrf_checks=True), APIClient(enforce_csrf_checks=True)
    signin(first)
    signin(second)
    old_key = first.cookies["sessionid"].value
    response = first.post(
        "/api/v1/auth/change-password",
        {
            "old_password": "test-password-123!",
            "new_password": "Changed-sitrap-secure-123!",
        },
        format="json",
        HTTP_X_CSRFTOKEN=csrf(first),
    )
    assert response.status_code == 200 and not response.json()["password_change_required"]
    assert first.cookies["sessionid"].value != old_key
    assert first.get("/api/v1/auth/me").status_code == 200
    assert second.get("/api/v1/auth/me").status_code == 401
    assert User.objects.get(pk=user.pk).check_password("Changed-sitrap-secure-123!")


def test_invalid_password_and_unknown_fields(api):
    response = api.post(
        "/api/v1/auth/change-password",
        {
            "old_password": "test-password-123!",
            "new_password": "123",
        },
        format="json",
    )
    assert response.status_code == 422 and response.json()["code"] == "VALIDATION_ERROR"
    assert (
        api.post("/api/v1/auth/change-password", {"actor": "someone"}, format="json").status_code
        == 422
    )


def test_inactive_account_and_login_throttle(user, settings):
    settings.LOGIN_USER_LIMIT = 2
    client = APIClient(enforce_csrf_checks=True)
    assert signin(client, password="wrong").status_code == 401
    assert signin(client, password="wrong").status_code == 401
    assert signin(client).status_code == 429
    assert all("vilma" not in key for key in LoginBucket.objects.values_list("key", flat=True))
    LoginBucket.objects.all().delete()
    user.is_active = False
    user.save()
    assert signin(client).status_code == 401


def test_authenticated_csrf_is_normalized(api):
    api.credentials()
    response = api.post("/api/v1/auth/logout")
    assert response.status_code == 403 and response.json()["code"] == "CSRF_FAILED"
