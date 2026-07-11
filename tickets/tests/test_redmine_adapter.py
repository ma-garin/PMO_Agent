"""RedmineAdapter.fetch_tickets の単体テスト。

Redmine REST API /issues.json の実レスポンス形状に近いfixtureを responses で
モックし、done_ratio==100 とクローズ状態名の両方の完了判定ヒューリスティックを検証する。
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone as dt_timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
import requests
import responses

from tickets.adapters.base import TicketSourceConnectionError
from tickets.adapters.redmine import RedmineAdapter, _is_done

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


def _make_source(**overrides) -> SimpleNamespace:
    defaults = dict(
        base_url="https://redmine.example.com",
        project_key="proj",
        username="",
        api_token="dummy-api-key",
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


@pytest.mark.unit
@responses.activate
def test_fetch_tickets_maps_fields_correctly() -> None:
    payload = _load_fixture("redmine_issues_response.json")
    responses.add(
        responses.GET,
        "https://redmine.example.com/issues.json",
        json=payload,
        status=200,
    )

    tickets = RedmineAdapter().fetch_tickets(_make_source())

    assert len(tickets) == 3
    first = tickets[0]
    assert first.external_id == "101"
    assert first.external_url == "https://redmine.example.com/issues/101"
    assert first.summary == "検索機能が動作しない"
    assert first.description == "検索ボタン押下時に500エラーが発生する。"
    assert first.status == "進行中"
    assert first.priority == "通常"
    assert first.ticket_type == "バグ"
    assert first.assignee_name == "山田太郎"
    assert first.reporter_name == "鈴木花子"
    assert first.due_date == date(2026, 7, 20)
    assert first.source_created_at == datetime(2026, 6, 1, 0, 0, 0, tzinfo=dt_timezone.utc)
    assert first.source_updated_at == datetime(2026, 7, 9, 3, 15, 0, tzinfo=dt_timezone.utc)
    assert first.raw_payload == payload["issues"][0]


@pytest.mark.unit
@responses.activate
def test_fetch_tickets_done_ratio_below_100_and_open_status_is_not_done() -> None:
    payload = _load_fixture("redmine_issues_response.json")
    responses.add(
        responses.GET,
        "https://redmine.example.com/issues.json",
        json=payload,
        status=200,
    )

    tickets = RedmineAdapter().fetch_tickets(_make_source())

    ticket = tickets[0]  # done_ratio=40, status="進行中"
    assert ticket.is_done is False


@pytest.mark.unit
@responses.activate
def test_fetch_tickets_closed_status_name_marks_done_even_with_zero_ratio() -> None:
    payload = _load_fixture("redmine_issues_response.json")
    responses.add(
        responses.GET,
        "https://redmine.example.com/issues.json",
        json=payload,
        status=200,
    )

    tickets = RedmineAdapter().fetch_tickets(_make_source())

    ticket = tickets[1]  # done_ratio=0, status="終了"(クローズ状態名)
    assert ticket.external_id == "102"
    assert ticket.is_done is True
    assert ticket.assignee_name == ""
    assert ticket.description == ""
    assert ticket.due_date is None


@pytest.mark.unit
@responses.activate
def test_fetch_tickets_done_ratio_100_marks_done_regardless_of_status_name() -> None:
    payload = _load_fixture("redmine_issues_response.json")
    responses.add(
        responses.GET,
        "https://redmine.example.com/issues.json",
        json=payload,
        status=200,
    )

    tickets = RedmineAdapter().fetch_tickets(_make_source())

    ticket = tickets[2]  # done_ratio=100, status="レビュー中"(非クローズ名)
    assert ticket.external_id == "103"
    assert ticket.is_done is True


@pytest.mark.unit
@responses.activate
def test_fetch_tickets_sends_api_key_header() -> None:
    payload = _load_fixture("redmine_issues_response.json")
    responses.add(
        responses.GET,
        "https://redmine.example.com/issues.json",
        json=payload,
        status=200,
    )

    RedmineAdapter().fetch_tickets(_make_source(api_token="secret-key"))

    assert len(responses.calls) == 1
    sent_request = responses.calls[0].request
    assert sent_request.headers["X-Redmine-API-Key"] == "secret-key"


@pytest.mark.unit
@responses.activate
def test_fetch_tickets_raises_connection_error_on_request_failure() -> None:
    responses.add(
        responses.GET,
        "https://redmine.example.com/issues.json",
        body=requests.exceptions.ConnectionError("network down"),
    )

    with pytest.raises(TicketSourceConnectionError):
        RedmineAdapter().fetch_tickets(_make_source())


@pytest.mark.unit
@responses.activate
def test_fetch_tickets_raises_connection_error_on_http_error_status() -> None:
    responses.add(
        responses.GET,
        "https://redmine.example.com/issues.json",
        json={"errors": ["invalid api key"]},
        status=403,
    )

    with pytest.raises(TicketSourceConnectionError):
        RedmineAdapter().fetch_tickets(_make_source())


@pytest.mark.unit
@pytest.mark.parametrize(
    ("status_name", "done_ratio", "expected"),
    [
        ("進行中", 40, False),
        ("進行中", 100, True),
        ("終了", 0, True),
        ("Closed", 10, True),
        ("closed", 10, True),  # 大文字小文字を区別しない
        ("却下", 0, True),
        ("レビュー中", 99, False),
    ],
)
def test_is_done_heuristic(status_name: str, done_ratio: int, expected: bool) -> None:
    assert _is_done(status_name, done_ratio) is expected


@pytest.mark.unit
@responses.activate
def test_fetch_status_history_resolves_status_ids_to_names_and_filters_status_id_only() -> None:
    issue_payload = _load_fixture("redmine_issue_with_journals_response.json")
    statuses_payload = _load_fixture("redmine_statuses_response.json")
    responses.add(
        responses.GET,
        "https://redmine.example.com/statuses.json",
        json=statuses_payload,
        status=200,
    )
    responses.add(
        responses.GET,
        "https://redmine.example.com/issues/101.json",
        json=issue_payload,
        status=200,
    )

    ticket = SimpleNamespace(external_id="101")
    history = RedmineAdapter().fetch_status_history(_make_source(), ticket)

    assert len(history) == 2  # priority_id側のjournalは除外される
    assert history[0]["from_status"] == "新規"
    assert history[0]["to_status"] == "進行中"
    assert history[1]["from_status"] == "進行中"
    assert history[1]["to_status"] == "終了"


@pytest.mark.unit
@responses.activate
def test_fetch_status_history_caches_status_map_across_calls() -> None:
    issue_payload = _load_fixture("redmine_issue_with_journals_response.json")
    statuses_payload = _load_fixture("redmine_statuses_response.json")
    responses.add(
        responses.GET,
        "https://redmine.example.com/statuses.json",
        json=statuses_payload,
        status=200,
    )
    responses.add(
        responses.GET,
        "https://redmine.example.com/issues/101.json",
        json=issue_payload,
        status=200,
    )
    responses.add(
        responses.GET,
        "https://redmine.example.com/issues/101.json",
        json=issue_payload,
        status=200,
    )

    adapter = RedmineAdapter()
    ticket = SimpleNamespace(external_id="101")
    adapter.fetch_status_history(_make_source(), ticket)
    adapter.fetch_status_history(_make_source(), ticket)

    status_calls = [c for c in responses.calls if c.request.url.endswith("/statuses.json")]
    assert len(status_calls) == 1


@pytest.mark.unit
@responses.activate
def test_fetch_status_history_raises_connection_error_when_statuses_fail() -> None:
    responses.add(
        responses.GET,
        "https://redmine.example.com/statuses.json",
        body=requests.exceptions.ConnectionError("network down"),
    )

    ticket = SimpleNamespace(external_id="101")
    with pytest.raises(TicketSourceConnectionError):
        RedmineAdapter().fetch_status_history(_make_source(), ticket)
