"""sync_ticket_source のテスト。

get_adapter をモックし、Ticketのupsert(新規作成・更新)と SyncRun の
ステータス遷移(成功・失敗)をDBを使って検証する。
"""
from __future__ import annotations

from datetime import datetime, timezone as dt_timezone
from unittest.mock import patch

import pytest

from tickets.adapters.base import NormalizedTicket, TicketSourceConnectionError
from tickets.models import SyncRun, Ticket, TicketSource, TicketStatusTransition
from tickets.services import sync_ticket_source


class _StaticAdapter:
    """常に固定のNormalizedTicket一覧を返すダミーアダプタ。"""

    def __init__(
        self, tickets: list[NormalizedTicket], history: dict[str, list[dict]] | None = None
    ) -> None:
        self._tickets = tickets
        self._history = history or {}

    def fetch_tickets(self, source: TicketSource) -> list[NormalizedTicket]:
        return self._tickets

    def fetch_status_history(self, source: TicketSource, ticket) -> list[dict]:
        return self._history.get(ticket.external_id, [])


class _FailingAdapter:
    """常に接続エラーを送出するダミーアダプタ。"""

    def __init__(self, message: str) -> None:
        self._message = message

    def fetch_tickets(self, source: TicketSource) -> list[NormalizedTicket]:
        raise TicketSourceConnectionError(self._message)

    def fetch_status_history(self, source: TicketSource, ticket) -> list[dict]:
        return []


class _UnexpectedFailingAdapter:
    def fetch_tickets(self, source: TicketSource) -> list[NormalizedTicket]:
        raise RuntimeError("予期しない同期エラー")


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
def test_sync_ticket_source_marks_failed_and_reraises_unexpected_error(
    ticket_source: TicketSource,
) -> None:
    with patch(
        "tickets.services.get_adapter",
        return_value=_UnexpectedFailingAdapter(),
    ):
        with pytest.raises(RuntimeError, match="予期しない同期エラー"):
            sync_ticket_source(ticket_source)

    run = SyncRun.objects.get(source=ticket_source)
    assert run.status == SyncRun.Status.FAILED
    assert run.error_message == "予期しない同期エラー"
    assert run.finished_at is not None


@pytest.mark.django_db
def test_sync_run_cannot_transition_after_terminal_state(ticket_source: TicketSource) -> None:
    run = SyncRun.objects.create(source=ticket_source)
    run.succeed(1)

    with pytest.raises(ValueError, match="既に終了"):
        run.fail("late failure")

    run.refresh_from_db()
    assert run.status == SyncRun.Status.SUCCESS
    assert run.tickets_synced == 1


@pytest.mark.django_db
def test_sync_ticket_source_creates_sync_run_record(
    ticket_source: TicketSource,
) -> None:
    with patch("tickets.services.get_adapter", return_value=_StaticAdapter([])):
        run = sync_ticket_source(ticket_source)

    assert SyncRun.objects.filter(source=ticket_source).count() == 1
    assert SyncRun.objects.get(pk=run.pk).status == SyncRun.Status.SUCCESS


@pytest.mark.django_db
def test_sync_ticket_source_imports_status_history_for_new_tickets(
    ticket_source: TicketSource,
) -> None:
    normalized = [
        NormalizedTicket(external_id="PROJ-1", summary="新規チケット", status="進行中")
    ]
    history = {
        "PROJ-1": [
            {
                "from_status": "未着手",
                "to_status": "進行中",
                "occurred_at": datetime(2026, 6, 10, tzinfo=dt_timezone.utc),
            }
        ]
    }

    with patch(
        "tickets.services.get_adapter",
        return_value=_StaticAdapter(normalized, history=history),
    ):
        sync_ticket_source(ticket_source)

    ticket = Ticket.objects.get(source=ticket_source, external_id="PROJ-1")
    transitions = TicketStatusTransition.objects.filter(ticket=ticket)
    assert transitions.count() == 1
    assert transitions.first().to_status == "進行中"


@pytest.mark.django_db
def test_sync_ticket_source_skips_history_for_tickets_not_updated_since_last_sync(
    ticket_source: TicketSource,
) -> None:
    old_time = datetime(2026, 1, 1, tzinfo=dt_timezone.utc)
    ticket_source.last_synced_at = datetime(2026, 6, 1, tzinfo=dt_timezone.utc)
    ticket_source.save(update_fields=["last_synced_at"])

    normalized = [
        NormalizedTicket(
            external_id="PROJ-1",
            summary="更新なしチケット",
            status="進行中",
            source_updated_at=old_time,
        )
    ]
    history = {
        "PROJ-1": [
            {"from_status": "未着手", "to_status": "進行中", "occurred_at": old_time}
        ]
    }

    adapter = _StaticAdapter(normalized, history=history)
    with patch("tickets.services.get_adapter", return_value=adapter):
        with patch.object(
            adapter, "fetch_status_history", wraps=adapter.fetch_status_history
        ) as spy:
            sync_ticket_source(ticket_source)

    spy.assert_not_called()
    assert TicketStatusTransition.objects.count() == 0


@pytest.mark.django_db
def test_sync_ticket_source_fetch_history_false_skips_history_entirely(
    ticket_source: TicketSource,
) -> None:
    normalized = [
        NormalizedTicket(external_id="PROJ-1", summary="新規チケット", status="進行中")
    ]
    history = {
        "PROJ-1": [
            {
                "from_status": "未着手",
                "to_status": "進行中",
                "occurred_at": datetime(2026, 6, 10, tzinfo=dt_timezone.utc),
            }
        ]
    }

    with patch(
        "tickets.services.get_adapter",
        return_value=_StaticAdapter(normalized, history=history),
    ):
        sync_ticket_source(ticket_source, fetch_history=False)

    assert TicketStatusTransition.objects.count() == 0
