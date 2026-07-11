from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView

from .forms import EngagementForm, EngagementLlmSettingsForm
from .models import Engagement


class EngagementSelectView(LoginRequiredMixin, ListView):
    model = Engagement
    template_name = "engagements/select.html"
    context_object_name = "engagements"

    def get_queryset(self):
        user = self.request.user
        return (
            Engagement.objects.filter(Q(owner=user) | Q(members=user))
            .distinct()
            .prefetch_related("members")
        )


class EngagementCreateView(LoginRequiredMixin, CreateView):
    model = Engagement
    form_class = EngagementForm
    template_name = "engagements/engagement_form.html"
    success_url = reverse_lazy("engagements:select")

    def form_valid(self, form):
        form.instance.owner = self.request.user
        response = super().form_valid(form)
        self.object.members.add(self.request.user)
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

    if request.method == "POST":
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
        {"form": form, "engagement": engagement, "nav_active": "settings"},
    )
