"""JiraAdapter.fetch_tickets の単体テスト。

JIRA Cloud REST API v3 /rest/api/3/search の実レスポンス形状に近いfixtureを
responses でモックし、NormalizedTicket への変換ロジックを検証する。
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone as dt_timezone
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest
import requests
import responses

from tickets.adapters.base import TicketSourceConnectionError
from tickets.adapters.jira import JiraAdapter

FIXTURES_DIR = Path(__file__).parent / "fixtures"
JST = dt_timezone(timedelta(hours=9))


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


def _make_source(**overrides) -> SimpleNamespace:
    defaults = dict(
        base_url="https://example.atlassian.net",
        project_key="PROJ",
        username="user@example.com",
        api_token="dummy-token",
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


@pytest.mark.unit
@responses.activate
def test_fetch_tickets_maps_plain_text_description_and_in_progress_status() -> None:
    payload = _load_fixture("jira_search_response.json")
    responses.add(
        responses.GET,
        "https://example.atlassian.net/rest/api/3/search",
        json=payload,
        status=200,
    )

    tickets = JiraAdapter().fetch_tickets(_make_source())

    assert len(tickets) == 3
    first = tickets[0]
    assert first.external_id == "PROJ-1"
    assert first.external_url == "https://example.atlassian.net/browse/PROJ-1"
    assert first.summary == "ログイン画面の不具合修正"
    assert first.description == "ログイン時にエラーが発生する。再現手順は以下の通り。"
    assert first.status == "進行中"
    assert first.is_done is False
    assert first.priority == "High"
    assert first.ticket_type == "バグ"
    assert first.assignee_name == "山田太郎"
    assert first.reporter_name == "鈴木花子"
    assert first.due_date == date(2026, 8, 1)
    assert first.source_created_at == datetime(2026, 6, 1, 9, 0, 0, tzinfo=JST)
    assert first.source_updated_at == datetime(2026, 7, 10, 15, 30, 0, tzinfo=JST)
    assert first.raw_payload == payload["issues"][0]


@pytest.mark.unit
@responses.activate
def test_fetch_tickets_treats_adf_description_as_empty_string() -> None:
    payload = _load_fixture("jira_search_response.json")
    responses.add(
        responses.GET,
        "https://example.atlassian.net/rest/api/3/search",
        json=payload,
        status=200,
    )

    tickets = JiraAdapter().fetch_tickets(_make_source())

    done_ticket = tickets[1]
    assert done_ticket.external_id == "PROJ-2"
    # ADF(構造化JSON)は文字列でないため空文字になる
    assert done_ticket.description == ""
    assert done_ticket.assignee_name == ""
    assert done_ticket.due_date is None


@pytest.mark.unit
@responses.activate
def test_fetch_tickets_done_detection_uses_status_category_key() -> None:
    payload = _load_fixture("jira_search_response.json")
    responses.add(
        responses.GET,
        "https://example.atlassian.net/rest/api/3/search",
        json=payload,
        status=200,
    )

    tickets = JiraAdapter().fetch_tickets(_make_source())

    is_done_by_id = {t.external_id: t.is_done for t in tickets}
    assert is_done_by_id == {
        "PROJ-1": False,  # statusCategory.key == "indeterminate"
        "PROJ-2": True,  # statusCategory.key == "done"
        "PROJ-3": False,  # statusCategory.key == "new"
    }


@pytest.mark.unit
@responses.activate
def test_fetch_tickets_null_description_becomes_empty_string() -> None:
    payload = _load_fixture("jira_search_response.json")
    responses.add(
        responses.GET,
        "https://example.atlassian.net/rest/api/3/search",
        json=payload,
        status=200,
    )

    tickets = JiraAdapter().fetch_tickets(_make_source())

    todo_ticket = tickets[2]
    assert todo_ticket.external_id == "PROJ-3"
    assert todo_ticket.description == ""


@pytest.mark.unit
@responses.activate
def test_fetch_tickets_sends_basic_auth_and_project_jql() -> None:
    payload = _load_fixture("jira_search_response.json")
    responses.add(
        responses.GET,
        "https://example.atlassian.net/rest/api/3/search",
        json=payload,
        status=200,
    )

    JiraAdapter().fetch_tickets(
        _make_source(username="me@example.com", api_token="secret-token")
    )

    assert len(responses.calls) == 1
    sent_request = responses.calls[0].request
    query = parse_qs(urlparse(sent_request.url).query)
    assert query["jql"][0] == "project = PROJ ORDER BY updated DESC"
    assert sent_request.headers["Authorization"].startswith("Basic ")


@pytest.mark.unit
@responses.activate
def test_fetch_tickets_raises_connection_error_on_request_failure() -> None:
    responses.add(
        responses.GET,
        "https://example.atlassian.net/rest/api/3/search",
        body=requests.exceptions.ConnectionError("network down"),
    )

    with pytest.raises(TicketSourceConnectionError):
        JiraAdapter().fetch_tickets(_make_source())


@pytest.mark.unit
@responses.activate
def test_fetch_tickets_raises_connection_error_on_http_error_status() -> None:
    responses.add(
        responses.GET,
        "https://example.atlassian.net/rest/api/3/search",
        json={"errorMessages": ["Unauthorized"]},
        status=401,
    )

    with pytest.raises(TicketSourceConnectionError):
        JiraAdapter().fetch_tickets(_make_source())


@pytest.mark.unit
@responses.activate
def test_fetch_tickets_returns_empty_list_when_no_issues() -> None:
    responses.add(
        responses.GET,
        "https://example.atlassian.net/rest/api/3/search",
        json={"issues": []},
        status=200,
    )

    tickets = JiraAdapter().fetch_tickets(_make_source())

    assert tickets == []
