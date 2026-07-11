"""ProfileForm のバリデーションテスト。"""
from __future__ import annotations

import pytest

from accounts.forms import ProfileForm


@pytest.mark.unit
def test_profile_form_valid_with_all_fields() -> None:
    form = ProfileForm(
        data={
            "first_name": "太郎",
            "last_name": "山田",
            "email": "taro.yamada@example.com",
        }
    )
    assert form.is_valid(), form.errors


@pytest.mark.unit
def test_profile_form_valid_when_all_fields_blank() -> None:
    # Djangoの標準Userモデルはfirst_name/last_name/emailがblank=Trueのため
    # 未入力でも有効になる
    form = ProfileForm(data={"first_name": "", "last_name": "", "email": ""})
    assert form.is_valid(), form.errors


@pytest.mark.unit
def test_profile_form_invalid_with_malformed_email() -> None:
    form = ProfileForm(
        data={"first_name": "太郎", "last_name": "山田", "email": "not-an-email"}
    )
    assert not form.is_valid()
    assert "email" in form.errors


@pytest.mark.unit
def test_profile_form_invalid_with_name_exceeding_max_length() -> None:
    form = ProfileForm(
        data={
            "first_name": "た" * 151,  # User.first_name max_length=150
            "last_name": "山田",
            "email": "taro.yamada@example.com",
        }
    )
    assert not form.is_valid()
    assert "first_name" in form.errors
