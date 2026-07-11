"""JiraAdapter/RedmineAdapter の日時パースヘルパーと、アダプタレジストリのテスト。"""
from __future__ import annotations

from datetime import date, datetime

import pytest

from tickets.adapters import get_adapter
from tickets.adapters.jira import JiraAdapter, _parse_date as jira_parse_date
from tickets.adapters.jira import _parse_datetime as jira_parse_datetime
from tickets.adapters.redmine import RedmineAdapter
from tickets.adapters.redmine import _parse_date as redmine_parse_date
from tickets.adapters.redmine import _parse_datetime as redmine_parse_datetime
from tickets.models import TicketSource


@pytest.mark.unit
@pytest.mark.parametrize("value", [None, ""])
def test_jira_parse_datetime_returns_none_for_empty_value(value: str | None) -> None:
    assert jira_parse_datetime(value) is None


@pytest.mark.unit
@pytest.mark.parametrize("value", [None, ""])
def test_jira_parse_date_returns_none_for_empty_value(value: str | None) -> None:
    assert jira_parse_date(value) is None


@pytest.mark.unit
def test_jira_parse_datetime_parses_iso8601_with_offset() -> None:
    assert jira_parse_datetime("2026-07-10T15:30:00.000+0900") == datetime.fromisoformat(
        "2026-07-10T15:30:00.000+0900"
    )


@pytest.mark.unit
def test_jira_parse_date_parses_iso8601_date() -> None:
    assert jira_parse_date("2026-08-01") == date(2026, 8, 1)


@pytest.mark.unit
@pytest.mark.parametrize("value", [None, ""])
def test_redmine_parse_datetime_returns_none_for_empty_value(value: str | None) -> None:
    assert redmine_parse_datetime(value) is None


@pytest.mark.unit
@pytest.mark.parametrize("value", [None, ""])
def test_redmine_parse_date_returns_none_for_empty_value(value: str | None) -> None:
    assert redmine_parse_date(value) is None


@pytest.mark.unit
def test_redmine_parse_datetime_parses_iso8601_utc() -> None:
    assert redmine_parse_datetime("2026-07-09T03:15:00Z") == datetime.fromisoformat(
        "2026-07-09T03:15:00Z"
    )


@pytest.mark.unit
def test_get_adapter_returns_jira_adapter_instance() -> None:
    adapter = get_adapter(TicketSource.Kind.JIRA)
    assert isinstance(adapter, JiraAdapter)


@pytest.mark.unit
def test_get_adapter_returns_redmine_adapter_instance() -> None:
    adapter = get_adapter(TicketSource.Kind.REDMINE)
    assert isinstance(adapter, RedmineAdapter)


@pytest.mark.unit
def test_get_adapter_raises_value_error_for_unknown_kind() -> None:
    with pytest.raises(ValueError, match="未対応のチケットソース種別です"):
        get_adapter("unknown-kind")
