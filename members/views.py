from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from engagements.models import Engagement
from tickets.models import Ticket

from .models import MemberAlias


def _current_engagement(request):
    engagement_id = request.session.get("current_engagement_id")
    if not engagement_id:
        return None
    return get_object_or_404(Engagement, pk=engagement_id)


@login_required
def member_list(request):
    engagement = _current_engagement(request)
    if engagement is None:
        return redirect("engagements:select")

    tickets = Ticket.objects.filter(source__engagement=engagement)
    aliases = MemberAlias.objects.filter(engagement=engagement).select_related("user")

    member_rows = []
    mapped_names = set()
    for member in engagement.members.all():
        external_names = [a.external_name for a in aliases if a.user_id == member.pk]
        mapped_names.update(external_names)
        member_tickets = tickets.filter(assignee_name__in=external_names) if external_names else tickets.none()
        member_rows.append(
            {
                "user": member,
                "external_names": external_names,
                "total": member_tickets.count(),
                "open": member_tickets.exclude(is_done=True).count(),
                "stagnant": member_tickets.filter(notifications__kind="stagnant").distinct().count(),
            }
        )

    all_assignee_names = set(
        tickets.exclude(assignee_name="").values_list("assignee_name", flat=True).distinct()
    )
    unmapped_names = sorted(all_assignee_names - mapped_names)

    context = {
        "engagement": engagement,
        "nav_active": "members",
        "member_rows": member_rows,
        "unmapped_names": unmapped_names,
        "all_users": engagement.members.all(),
    }
    return render(request, "members/list.html", context)


@login_required
def alias_create(request):
    engagement = _current_engagement(request)
    if engagement is None:
        return redirect("engagements:select")

    if not request.user.is_staff:
        messages.error(request, "この操作には管理者権限が必要です。")
        return redirect("members:list")

    if request.method == "POST":
        user_id = request.POST.get("user_id")
        external_name = request.POST.get("external_name", "").strip()
        if user_id and external_name:
            MemberAlias.objects.get_or_create(
                engagement=engagement, external_name=external_name, defaults={"user_id": user_id}
            )
            messages.success(request, "対応付けを追加しました。")
    return redirect("members:list")


@login_required
def alias_delete(request, pk):
    engagement = _current_engagement(request)
    if engagement is None:
        return redirect("engagements:select")

    if not request.user.is_staff:
        messages.error(request, "この操作には管理者権限が必要です。")
        return redirect("members:list")

    alias = get_object_or_404(MemberAlias, pk=pk, engagement=engagement)
    if request.method == "POST":
        alias.delete()
        messages.success(request, "対応付けを削除しました。")
    return redirect("members:list")
