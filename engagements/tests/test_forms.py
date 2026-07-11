"""EngagementForm のバリデーションテスト。"""
from __future__ import annotations

import pytest

from engagements.forms import EngagementForm
from engagements.models import Engagement


@pytest.mark.unit
def test_engagement_form_valid_with_all_fields() -> None:
    form = EngagementForm(
        data={
            "name": "基幹システム刷新",
            "description": "業務システムの刷新プロジェクト",
            "status": Engagement.Status.ACTIVE,
        }
    )
    assert form.is_valid(), form.errors


@pytest.mark.unit
def test_engagement_form_valid_without_optional_description() -> None:
    # descriptionはblank=Trueのため省略可能
    form = EngagementForm(
        data={"name": "基幹システム刷新", "description": "", "status": Engagement.Status.ACTIVE}
    )
    assert form.is_valid(), form.errors


@pytest.mark.unit
def test_engagement_form_invalid_without_name() -> None:
    form = EngagementForm(
        data={"name": "", "description": "概要", "status": Engagement.Status.ACTIVE}
    )
    assert not form.is_valid()
    assert "name" in form.errors


@pytest.mark.unit
def test_engagement_form_invalid_without_status() -> None:
    form = EngagementForm(data={"name": "基幹システム刷新", "description": ""})
    assert not form.is_valid()
    assert "status" in form.errors


@pytest.mark.unit
def test_engagement_form_invalid_with_unknown_status_choice() -> None:
    form = EngagementForm(
        data={"name": "基幹システム刷新", "description": "", "status": "unknown_status"}
    )
    assert not form.is_valid()
    assert "status" in form.errors


@pytest.mark.unit
def test_engagement_form_invalid_with_name_exceeding_max_length() -> None:
    form = EngagementForm(
        data={
            "name": "あ" * 201,  # max_length=200
            "description": "",
            "status": Engagement.Status.ACTIVE,
        }
    )
    assert not form.is_valid()
    assert "name" in form.errors
