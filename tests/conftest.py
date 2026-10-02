import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User


@pytest.fixture(autouse=True)
def fast_test_passwords(settings):
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username="vilma", name="Operadora", password="test-password-123!"
    )


@pytest.fixture
def api(user):
    client = APIClient(enforce_csrf_checks=True)
    client.force_login(user)
    token = client.get("/api/v1/auth/csrf").json()["csrf_token"]
    client.credentials(HTTP_X_CSRFTOKEN=token)
    return client
