from itertools import chain

from .models import Notification


def notifications(request):
    engagement_id = getattr(request, "session", {}).get("current_engagement_id")
    if not engagement_id or not request.user.is_authenticated:
        return {"header_notifications": [], "header_unread_count": 0}

    ticket_notifications = list(
        Notification.objects.filter(engagement_id=engagement_id).select_related("ticket")[:8]
    )
    unread_count = Notification.objects.filter(
        engagement_id=engagement_id, is_read=False
    ).count()

    try:
        from risks.models import GeneralNotification
    except ImportError:
        general_notifications: list = []
    else:
        general_notifications = list(
            GeneralNotification.objects.filter(engagement_id=engagement_id)[:8]
        )
        unread_count += GeneralNotification.objects.filter(
            engagement_id=engagement_id, is_read=False
        ).count()

    combined = sorted(
        chain(ticket_notifications, general_notifications),
        key=lambda n: n.created_at,
        reverse=True,
    )[:8]

    return {"header_notifications": combined, "header_unread_count": unread_count}
