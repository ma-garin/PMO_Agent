from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.shortcuts import render

from accounts.decorators import admin_required

from .models import AuditLog

PAGE_SIZE = 50


@admin_required
def audit_log_list(request):
    logs = AuditLog.objects.select_related("actor").all()

    actor_id = request.GET.get("actor", "").strip()
    if actor_id:
        logs = logs.filter(actor_id=actor_id)

    action = request.GET.get("action", "").strip()
    if action:
        logs = logs.filter(action__icontains=action)

    date_from = request.GET.get("date_from", "").strip()
    if date_from:
        logs = logs.filter(created_at__date__gte=date_from)

    date_to = request.GET.get("date_to", "").strip()
    if date_to:
        logs = logs.filter(created_at__date__lte=date_to)

    paginator = Paginator(logs, PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        "nav_active": "manage",
        "page_obj": page_obj,
        "actors": User.objects.order_by("username"),
        "filters": {
            "actor": actor_id,
            "action": action,
            "date_from": date_from,
            "date_to": date_to,
        },
    }
    return render(request, "audit/list.html", context)
