from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.db.models import Count, Max, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, ListView

from audit.services import record

from .forms import EngagementForm, EngagementLlmSettingsForm
from .models import Engagement


def portfolio_stats(engagement_ids: list[int]) -> dict:
    """案件横断のポートフォリオ統計。N+1を避けるため集計クエリ3本のみ実行する。"""
    from tickets.models import Notification, Ticket

    today = timezone.localdate()
    open_counts = dict(
        Ticket.objects.filter(source__engagement_id__in=engagement_ids)
        .exclude(is_done=True)
        .values_list("source__engagement_id")
        .annotate(count=Count("id"))
    )
    overdue_counts = dict(
        Ticket.objects.filter(source__engagement_id__in=engagement_ids, due_date__lt=today)
        .exclude(is_done=True)
        .values_list("source__engagement_id")
        .annotate(count=Count("id"))
    )
    unread_counts = dict(
        Notification.objects.filter(engagement_id__in=engagement_ids, is_read=False)
        .values_list("engagement_id")
        .annotate(count=Count("id"))
    )
    sync_dates = dict(
        Engagement.objects.filter(pk__in=engagement_ids)
        .values_list("pk")
        .annotate(last_sync=Max("ticket_sources__last_synced_at"))
    )

    return {
        eid: {
            "open": open_counts.get(eid, 0),
            "overdue": overdue_counts.get(eid, 0),
            "unread": unread_counts.get(eid, 0),
            "last_sync": sync_dates.get(eid),
        }
        for eid in engagement_ids
    }


class EngagementSelectView(LoginRequiredMixin, ListView):
    model = Engagement
    template_name = "engagements/select.html"
    context_object_name = "engagements"

    def get_queryset(self):
        user = self.request.user
        member_qs = (
            Engagement.objects.filter(Q(owner=user) | Q(members=user))
            .distinct()
            .prefetch_related("members")
        )
        if not user.is_staff:
            return member_qs

        member_list = list(member_qs)
        member_ids = [e.pk for e in member_list]
        others = list(
            Engagement.objects.exclude(pk__in=member_ids).prefetch_related("members")
        )
        for e in others:
            e.is_non_member = True
        return member_list + others

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        engagements = context[self.context_object_name]
        ids = [e.pk for e in engagements]
        stats = portfolio_stats(ids)
        for e in engagements:
            e.stats = stats.get(e.pk, {"open": 0, "overdue": 0, "unread": 0, "last_sync": None})
        return context


class EngagementCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Engagement
    form_class = EngagementForm
    template_name = "engagements/engagement_form.html"
    success_url = reverse_lazy("engagements:select")

    def test_func(self) -> bool:
        return self.request.user.is_staff

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()
        messages.error(self.request, "この操作には管理者権限が必要です。")
        return redirect("dashboard:home")

    def form_valid(self, form):
        form.instance.owner = self.request.user
        response = super().form_valid(form)
        self.object.members.add(self.request.user)
        record(self.request.user, "engagement_create", self.object, detail=self.object.name)
        return response


@login_required
def enter_engagement(request, pk):
    engagement = get_object_or_404(
        Engagement.objects.filter(
            Q(owner=request.user) | Q(members=request.user)
        ).distinct(),
        pk=pk,
    )
    request.session["current_engagement_id"] = engagement.pk
    request.session["current_engagement_name"] = engagement.name
    return redirect("dashboard:home")


def _get_current_engagement(request):
    engagement_id = request.session.get("current_engagement_id")
    if not engagement_id:
        return None
    return get_object_or_404(
        Engagement.objects.filter(
            Q(owner=request.user) | Q(members=request.user)
        ).distinct(),
        pk=engagement_id,
    )


@login_required
def llm_settings(request):
    engagement = _get_current_engagement(request)
    if engagement is None:
        return redirect("engagements:select")

    # F-12(CWE-200): LLMプロバイダの変更は機密データのクラウド送信可否を左右するため、
    # 変更操作は管理者に限定する。閲覧は案件メンバーに許可する(表示のみ)。
    can_edit = request.user.is_staff

    if request.method == "POST":
        if not can_edit:
            messages.error(request, "LLMプロバイダの変更には管理者権限が必要です。")
            return redirect("engagements:llm_settings")
        form = EngagementLlmSettingsForm(request.POST, instance=engagement)
        if form.is_valid():
            form.save()
            messages.success(request, "LLM設定を更新しました。")
            return redirect("engagements:llm_settings")
    else:
        form = EngagementLlmSettingsForm(instance=engagement)

    return render(
        request,
        "engagements/llm_settings.html",
        {
            "form": form,
            "engagement": engagement,
            "nav_active": "settings",
            "can_edit": can_edit,
        },
    )
