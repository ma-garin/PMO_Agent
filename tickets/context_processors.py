from .models import Notification


def notifications(request):
    engagement_id = getattr(request, "session", {}).get("current_engagement_id")
    if not engagement_id or not request.user.is_authenticated:
        return {"header_notifications": [], "header_unread_count": 0}

    qs = Notification.objects.filter(engagement_id=engagement_id).select_related(
        "ticket"
    )[:8]
    unread_count = Notification.objects.filter(
        engagement_id=engagement_id, is_read=False
    ).count()
    return {"header_notifications": qs, "header_unread_count": unread_count}
