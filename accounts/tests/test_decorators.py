"""admin_required デコレータの権限チェックテスト。"""
from __future__ import annotations

import pytest
from django.contrib.auth.models import AnonymousUser, User
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.http import HttpResponse
from django.urls import reverse

from accounts.decorators import admin_required


@admin_required
def _dummy_view(request):
    return HttpResponse("ok")


def _prepare_request(request):
    SessionMiddleware(lambda r: HttpResponse()).process_request(request)
    request.session.save()
    setattr(request, "_messages", FallbackStorage(request))
    return request


@pytest.mark.unit
def test_admin_required_redirects_anonymous_to_login(rf) -> None:
    request = rf.get("/manage/")
    request.user = AnonymousUser()
    _prepare_request(request)

    response = _dummy_view(request)

    assert response.status_code == 302
    assert response.url == reverse("accounts:login")


@pytest.mark.django_db
def test_admin_required_redirects_non_staff_with_error_message(rf) -> None:
    user = User.objects.create_user(
        username="general", password="pass12345", is_staff=False  # noqa: S106
    )
    request = rf.get("/manage/")
    request.user = user
    _prepare_request(request)

    response = _dummy_view(request)

    assert response.status_code == 302
    assert response.url == reverse("dashboard:home")
    stored_messages = list(request._messages)
    assert any("管理者権限" in str(message) for message in stored_messages)


@pytest.mark.django_db
def test_admin_required_allows_staff_user(rf) -> None:
    user = User.objects.create_user(
        username="staff", password="pass12345", is_staff=True  # noqa: S106
    )
    request = rf.get("/manage/")
    request.user = user
    _prepare_request(request)

    response = _dummy_view(request)

    assert response.status_code == 200
    assert response.content == b"ok"
