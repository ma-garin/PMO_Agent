from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from .adapters import get_adapter
from .adapters.base import TicketSourceConnectionError
from .models import (
    Notification,
    StagnationRule,
    SyncRun,
    Ticket,
    TicketSource,
    TicketStatusTransition,
)


def _import_status_history(adapter, source: TicketSource, ticket: Ticket) -> None:
    try:
        history = adapter.fetch_status_history(source, ticket)
    except TicketSourceConnectionError:
        # 履歴取得の失敗はチケット本体の同期を妨げない(ベストエフォート)
        return

    for entry in history:
        TicketStatusTransition.objects.get_or_create(
            ticket=ticket,
            occurred_at=entry["occurred_at"],
            to_status=entry["to_status"],
            defaults={"from_status": entry["from_status"]},
        )


def sync_ticket_source(source: TicketSource, fetch_history: bool = True) -> SyncRun:
    run = SyncRun.objects.create(source=source)
    adapter = get_adapter(source.kind)
    previous_synced_at = source.last_synced_at

    try:
        normalized_tickets = adapter.fetch_tickets(source)
    except TicketSourceConnectionError as exc:
        run.status = SyncRun.Status.FAILED
        run.error_message = str(exc)
        run.finished_at = timezone.now()
        run.save(update_fields=["status", "error_message", "finished_at"])
        return run

    synced_count = 0
    tickets_needing_history: list[Ticket] = []
    for normalized in normalized_tickets:
        ticket, _created = Ticket.objects.update_or_create(
            source=source,
            external_id=normalized.external_id,
            defaults={
                "external_url": normalized.external_url,
                "summary": normalized.summary,
                "description": normalized.description,
                "status": normalized.status,
                "is_done": normalized.is_done,
                "priority": normalized.priority,
                "ticket_type": normalized.ticket_type,
                "assignee_name": normalized.assignee_name,
                "reporter_name": normalized.reporter_name,
                "due_date": normalized.due_date,
                "source_created_at": normalized.source_created_at,
                "source_updated_at": normalized.source_updated_at,
                "closed_at": normalized.closed_at,
                "raw_payload": normalized.raw_payload,
            },
        )
        synced_count += 1

        # API負荷対策: 履歴取得は前回同期以降に更新されたチケットのみ対象とする
        if fetch_history and (
            previous_synced_at is None
            or normalized.source_updated_at is None
            or normalized.source_updated_at >= previous_synced_at
        ):
            tickets_needing_history.append(ticket)

    for ticket in tickets_needing_history:
        _import_status_history(adapter, source, ticket)

    run.status = SyncRun.Status.SUCCESS
    run.tickets_synced = synced_count
    run.finished_at = timezone.now()
    run.save(update_fields=["status", "tickets_synced", "finished_at"])

    source.last_synced_at = run.finished_at
    source.save(update_fields=["last_synced_at"])
    return run


def sync_engagement(engagement) -> list[SyncRun]:
    return [
        sync_ticket_source(source)
        for source in engagement.ticket_sources.filter(is_active=True)
    ]


def detect_stagnant_tickets(engagement) -> list[Notification]:
    rule = getattr(engagement, "stagnation_rule", None)
    if rule is None:
        rule = StagnationRule(engagement=engagement)

    now = timezone.now()
    stale_before = now - timedelta(days=rule.stale_after_days)
    today = timezone.localdate()

    open_tickets = Ticket.objects.filter(
        source__engagement=engagement, is_done=False
    )
    created: list[Notification] = []

    stagnant_tickets = open_tickets.filter(source_updated_at__lt=stale_before)
    for ticket in stagnant_tickets:
        notification, is_new = Notification.objects.get_or_create(
            ticket=ticket,
            kind=Notification.Kind.STAGNANT,
            defaults={
                "engagement": engagement,
                "message": (
                    f"「{ticket.summary}」が{rule.stale_after_days}日以上更新されていません"
                ),
            },
        )
        if is_new:
            created.append(notification)

    if rule.notify_on_overdue:
        overdue_tickets = open_tickets.filter(due_date__lt=today)
        for ticket in overdue_tickets:
            notification, is_new = Notification.objects.get_or_create(
                ticket=ticket,
                kind=Notification.Kind.OVERDUE,
                defaults={
                    "engagement": engagement,
                    "message": f"「{ticket.summary}」が期限を超過しています",
                },
            )
            if is_new:
                created.append(notification)

    return created
