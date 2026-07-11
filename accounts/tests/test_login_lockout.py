import pytest
from django.contrib.auth.models import User
from django.test import Client


@pytest.fixture
def user(db) -> User:
    return User.objects.create_user(username="pmo", password="correct-password-123")


@pytest.mark.django_db
class TestLoginLockout:
    def test_five_failures_lock_account_even_with_correct_password(self, user):
        client = Client()
        for _ in range(5):
            client.post(
                "/accounts/login/", {"username": "pmo", "password": "wrong-password"}
            )
        response = client.post(
            "/accounts/login/", {"username": "pmo", "password": "correct-password-123"}
        )
        assert response.status_code != 302

    def test_login_succeeds_before_lockout_threshold(self, user):
        client = Client()
        for _ in range(3):
            client.post(
                "/accounts/login/", {"username": "pmo", "password": "wrong-password"}
            )
        response = client.post(
            "/accounts/login/", {"username": "pmo", "password": "correct-password-123"}
        )
        assert response.status_code == 302
