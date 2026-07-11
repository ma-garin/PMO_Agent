from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.models import User
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.decorators import admin_required
from analytics.services import benchmark_rows
from audit.services import record
from engagements.forms import EngagementForm
from engagements.models import Engagement
from llm.services import usage_summary
from tickets.models import NotificationChannel, TicketSource

from .forms import UserCreateForm


@admin_required
def home(request: HttpRequest) -> HttpResponse:
    context = {
        "nav_active": "manage",
        "user_count": User.objects.count(),
        "engagement_count": Engagement.objects.count(),
        "source_count": TicketSource.objects.count(),
        "llm_log_count": 0,
    }
    return render(request, "adminpanel/home.html", context)


@admin_required
def users(request: HttpRequest) -> HttpResponse:
    form = UserCreateForm()

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "create":
            form = UserCreateForm(request.POST)
            if form.is_valid():
                new_user = form.save()
                record(request.user, "user_create", new_user, detail=new_user.username)
                messages.success(request, "ユーザーを作成しました。")
                return redirect("adminpanel:users")
        elif action == "toggle_staff":
            target = get_object_or_404(User, pk=request.POST.get("user_id"))
            if target == request.user:
                messages.error(request, "自分自身の管理者権限は変更できません。")
            else:
                target.is_staff = not target.is_staff
                target.save(update_fields=["is_staff"])
                record(
                    request.user,
                    "user_permission_change",
                    target,
                    detail=f"is_staff={target.is_staff}",
                )
                messages.success(request, "管理者権限を更新しました。")
            return redirect("adminpanel:users")
        elif action == "toggle_active":
            target = get_object_or_404(User, pk=request.POST.get("user_id"))
            target.is_active = not target.is_active
            target.save(update_fields=["is_active"])
            record(
                request.user, "user_active_change", target, detail=f"is_active={target.is_active}"
            )
            messages.success(request, "ユーザーの有効状態を更新しました。")
            return redirect("adminpanel:users")

    context = {
        "nav_active": "manage",
        "users": User.objects.order_by("username"),
        "form": form,
    }
    return render(request, "adminpanel/users.html", context)


@admin_required
def engagements(request: HttpRequest) -> HttpResponse:
    if request.method == "POST" and request.POST.get("action") == "archive":
        engagement = get_object_or_404(Engagement, pk=request.POST.get("engagement_id"))
        engagement.status = Engagement.Status.COMPLETED
        engagement.save(update_fields=["status"])
        messages.success(request, "案件をアーカイブしました。")
        return redirect("adminpanel:engagements")

    context = {
        "nav_active": "manage",
        "engagements": Engagement.objects.select_related("owner").prefetch_related(
            "members"
        ),
    }
    return render(request, "adminpanel/engagements.html", context)


@admin_required
def engagement_edit(request: HttpRequest, pk: int) -> HttpResponse:
    engagement = get_object_or_404(Engagement, pk=pk)

    if request.method == "POST":
        form = EngagementForm(request.POST, instance=engagement)
        if form.is_valid():
            engagement = form.save()
            member_ids = request.POST.getlist("members")
            engagement.members.set(User.objects.filter(pk__in=member_ids))
            record(request.user, "engagement_edit", engagement, detail=engagement.name)
            messages.success(request, "案件を更新しました。")
            return redirect("adminpanel:engagements")
    else:
        form = EngagementForm(instance=engagement)

    context = {
        "nav_active": "manage",
        "engagement": engagement,
        "form": form,
        "users": User.objects.order_by("username"),
        "member_ids": set(engagement.members.values_list("pk", flat=True)),
    }
    return render(request, "adminpanel/engagement_edit.html", context)


@admin_required
def tokens(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        action = request.POST.get("action")
        source = get_object_or_404(TicketSource, pk=request.POST.get("source_id"))
        if action == "update_token":
            api_token = request.POST.get("api_token", "")
            if api_token:
                source.api_token = api_token
                source.save(update_fields=["_api_token_encrypted"])
                record(request.user, "token_update", source, detail=source.name)
                messages.success(request, "トークンを更新しました。")
        elif action == "toggle_active":
            source.is_active = not source.is_active
            source.save(update_fields=["is_active"])
            messages.success(request, "接続の有効状態を更新しました。")
        elif action == "delete":
            record(request.user, "token_delete", source, detail=source.name)
            source.delete()
            messages.success(request, "接続を削除しました。")
        return redirect("adminpanel:tokens")

    context = {
        "nav_active": "manage",
        "sources": TicketSource.objects.select_related("engagement").all(),
    }
    return render(request, "adminpanel/tokens.html", context)


@admin_required
def notification_channels(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "create":
            engagement = get_object_or_404(Engagement, pk=request.POST.get("engagement_id"))
            kind = request.POST.get("kind", "")
            target = request.POST.get("target", "").strip()
            if kind in NotificationChannel.Kind.values and target:
                NotificationChannel.objects.create(
                    engagement=engagement, kind=kind, target=target
                )
                messages.success(request, "通知チャネルを追加しました。")
            else:
                messages.error(request, "種別と宛先を入力してください。")
        else:
            channel = get_object_or_404(
                NotificationChannel, pk=request.POST.get("channel_id")
            )
            if action == "toggle_active":
                channel.is_active = not channel.is_active
                channel.save(update_fields=["is_active"])
                messages.success(request, "通知チャネルの有効状態を更新しました。")
            elif action == "delete":
                channel.delete()
                messages.success(request, "通知チャネルを削除しました。")
        return redirect("adminpanel:notification_channels")

    context = {
        "nav_active": "manage",
        "channels": NotificationChannel.objects.select_related("engagement").all(),
        "engagements": Engagement.objects.order_by("name"),
        "kind_choices": NotificationChannel.Kind.choices,
    }
    return render(request, "adminpanel/notification_channels.html", context)


@admin_required
def llm_logs(request: HttpRequest) -> HttpResponse:
    today = timezone.localdate()
    previous_month_date = today.replace(day=1) - timedelta(days=1)

    context = {
        "nav_active": "manage",
        "sections": [
            (f"{today.year}年{today.month}月", usage_summary(today.year, today.month)),
            (
                f"{previous_month_date.year}年{previous_month_date.month}月",
                usage_summary(previous_month_date.year, previous_month_date.month),
            ),
        ],
    }
    return render(request, "adminpanel/llm_logs.html", context)


@admin_required
def benchmark(request: HttpRequest) -> HttpResponse:
    context = {
        "nav_active": "manage",
        "rows": benchmark_rows(),
    }
    return render(request, "adminpanel/benchmark.html", context)
