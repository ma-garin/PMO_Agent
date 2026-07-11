"""sync_ticket_source のテスト。

get_adapter をモックし、Ticketのupsert(新規作成・更新)と SyncRun の
ステータス遷移(成功・失敗)をDBを使って検証する。
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from tickets.adapters.base import NormalizedTicket, TicketSourceConnectionError
from tickets.models import SyncRun, Ticket, TicketSource
from tickets.services import sync_ticket_source


class _StaticAdapter:
    """常に固定のNormalizedTicket一覧を返すダミーアダプタ。"""

    def __init__(self, tickets: list[NormalizedTicket]) -> None:
        self._tickets = tickets

    def fetch_tickets(self, source: TicketSource) -> list[NormalizedTicket]:
        return self._tickets


class _FailingAdapter:
    """常に接続エラーを送出するダミーアダプタ。"""

    def __init__(self, message: str) -> None:
        self._message = message

    def fetch_tickets(self, source: TicketSource) -> list[NormalizedTicket]:
        raise TicketSourceConnectionError(self._message)


@pytest.mark.django_db
def test_sync_ticket_source_creates_new_tickets(ticket_source: TicketSource) -> None:
    normalized = [
        NormalizedTicket(
            external_id="PROJ-1",
            summary="新規チケット1",
            status="進行中",
            is_done=False,
        ),
        NormalizedTicket(
            external_id="PROJ-2",
            summary="新規チケット2",
            status="完了",
            is_done=True,
        ),
    ]

    with patch(
        "tickets.services.get_adapter", return_value=_StaticAdapter(normalized)
    ):
        run = sync_ticket_source(ticket_source)

    assert run.status == SyncRun.Status.SUCCESS
    assert run.tickets_synced == 2
    assert run.finished_at is not None
    assert run.error_message == ""

    assert Ticket.objects.filter(source=ticket_source).count() == 2
    ticket1 = Ticket.objects.get(source=ticket_source, external_id="PROJ-1")
    assert ticket1.summary == "新規チケット1"
    assert ticket1.is_done is False
    ticket2 = Ticket.objects.get(source=ticket_source, external_id="PROJ-2")
    assert ticket2.is_done is True

    ticket_source.refresh_from_db()
    assert ticket_source.last_synced_at == run.finished_at


@pytest.mark.django_db
def test_sync_ticket_source_updates_existing_ticket_without_duplicating(
    ticket_source: TicketSource,
) -> None:
    existing = Ticket.objects.create(
        source=ticket_source,
        external_id="PROJ-1",
        summary="旧タイトル",
        status="未着手",
        is_done=False,
    )
    normalized = [
        NormalizedTicket(
            external_id="PROJ-1",
            summary="更新後タイトル",
            status="完了",
            is_done=True,
        )
    ]

    with patch(
        "tickets.services.get_adapter", return_value=_StaticAdapter(normalized)
    ):
        run = sync_ticket_source(ticket_source)

    assert run.status == SyncRun.Status.SUCCESS
    assert Ticket.objects.filter(source=ticket_source).count() == 1

    existing.refresh_from_db()
    assert existing.pk is not None
    assert existing.summary == "更新後タイトル"
    assert existing.status == "完了"
    assert existing.is_done is True


@pytest.mark.django_db
def test_sync_ticket_source_marks_failed_on_connection_error(
    ticket_source: TicketSource,
) -> None:
    with patch(
        "tickets.services.get_adapter",
        return_value=_FailingAdapter("接続に失敗しました"),
    ):
        run = sync_ticket_source(ticket_source)

    assert run.status == SyncRun.Status.FAILED
    assert run.error_message == "接続に失敗しました"
    assert run.finished_at is not None
    assert run.tickets_synced == 0

    assert Ticket.objects.filter(source=ticket_source).count() == 0

    ticket_source.refresh_from_db()
    assert ticket_source.last_synced_at is None


@pytest.mark.django_db
def test_sync_ticket_source_creates_sync_run_record(
    ticket_source: TicketSource,
) -> None:
    with patch("tickets.services.get_adapter", return_value=_StaticAdapter([])):
        run = sync_ticket_source(ticket_source)

    assert SyncRun.objects.filter(source=ticket_source).count() == 1
    assert SyncRun.objects.get(pk=run.pk).status == SyncRun.Status.SUCCESS
