"""detect_stagnant_tickets のテスト。

実DBに新旧のTicketを作成し、閾値超え・期限超過のみNotificationが作られること、
2回実行しても重複Notificationが作られないこと(unique_together)を検証する。
"""
from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from engagements.models import Engagement
from tickets.models import Notification, StagnationRule, Ticket, TicketSource
from tickets.services import detect_stagnant_tickets


@pytest.mark.django_db
def test_detect_stagnant_tickets_creates_notification_only_for_stale_open_ticket(
    ticket_source: TicketSource, engagement: Engagement
) -> None:
    now = timezone.now()
    stale_ticket = Ticket.objects.create(
        source=ticket_source,
        external_id="PROJ-1",
        summary="放置チケット",
        is_done=False,
        source_updated_at=now - timedelta(days=10),
    )
    Ticket.objects.create(
        source=ticket_source,
        external_id="PROJ-2",
        summary="最近更新されたチケット",
        is_done=False,
        source_updated_at=now - timedelta(days=1),
    )
    Ticket.objects.create(
        source=ticket_source,
        external_id="PROJ-3",
        summary="完了済みだが更新は古いチケット",
        is_done=True,
        source_updated_at=now - timedelta(days=30),
    )

    created = detect_stagnant_tickets(engagement)

    assert len(created) == 1
    assert created[0].ticket_id == stale_ticket.id
    assert created[0].kind == Notification.Kind.STAGNANT
    assert Notification.objects.count() == 1


@pytest.mark.django_db
def test_detect_stagnant_tickets_does_not_duplicate_on_second_run(
    ticket_source: TicketSource, engagement: Engagement
) -> None:
    now = timezone.now()
    Ticket.objects.create(
        source=ticket_source,
        external_id="PROJ-1",
        summary="放置チケット",
        is_done=False,
        source_updated_at=now - timedelta(days=10),
    )

    first_run = detect_stagnant_tickets(engagement)
    second_run = detect_stagnant_tickets(engagement)

    assert len(first_run) == 1
    assert len(second_run) == 0
    assert Notification.objects.count() == 1


@pytest.mark.django_db
def test_detect_stagnant_tickets_creates_overdue_notification(
    ticket_source: TicketSource, engagement: Engagement
) -> None:
    today = timezone.localdate()
    overdue_ticket = Ticket.objects.create(
        source=ticket_source,
        external_id="PROJ-4",
        summary="期限切れチケット",
        is_done=False,
        source_updated_at=timezone.now(),  # 更新自体は最近
        due_date=today - timedelta(days=1),
    )

    created = detect_stagnant_tickets(engagement)

    kinds = {n.kind for n in created}
    assert Notification.Kind.OVERDUE in kinds
    overdue_notification = Notification.objects.get(
        ticket=overdue_ticket, kind=Notification.Kind.OVERDUE
    )
    assert "期限を超過しています" in overdue_notification.message


@pytest.mark.django_db
def test_detect_stagnant_tickets_respects_custom_rule_and_disabled_overdue(
    ticket_source: TicketSource, engagement: Engagement
) -> None:
    StagnationRule.objects.create(
        engagement=engagement, stale_after_days=3, notify_on_overdue=False
    )
    now = timezone.now()
    today = timezone.localdate()
    Ticket.objects.create(
        source=ticket_source,
        external_id="PROJ-5",
        summary="3日以上更新なしかつ期限切れ",
        is_done=False,
        source_updated_at=now - timedelta(days=4),
        due_date=today - timedelta(days=1),
    )

    created = detect_stagnant_tickets(engagement)

    kinds = {n.kind for n in created}
    assert Notification.Kind.STAGNANT in kinds
    assert Notification.Kind.OVERDUE not in kinds  # notify_on_overdue=Falseのため


@pytest.mark.django_db
def test_detect_stagnant_tickets_ignores_ticket_updated_within_threshold(
    ticket_source: TicketSource, engagement: Engagement
) -> None:
    now = timezone.now()
    Ticket.objects.create(
        source=ticket_source,
        external_id="PROJ-6",
        summary="デフォルト閾値内で更新されたチケット",
        is_done=False,
        source_updated_at=now - timedelta(days=4),  # デフォルト閾値5日未満
    )

    created = detect_stagnant_tickets(engagement)

    assert created == []
    assert Notification.objects.count() == 0
