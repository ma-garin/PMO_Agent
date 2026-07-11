from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .forms import ProfileForm
from .models import UserPreference


@login_required
def profile(request):
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "プロフィールを更新しました。")
            return redirect("accounts:profile")
    else:
        form = ProfileForm(instance=request.user)

    return render(
        request,
        "accounts/profile.html",
        {"form": form, "nav_active": "settings", "settings_tab": "profile"},
    )


@require_POST
@login_required
def set_theme(request):
    theme = request.POST.get("theme", "")
    if theme not in UserPreference.Theme.values:
        return JsonResponse({"ok": False}, status=400)
    UserPreference.objects.update_or_create(user=request.user, defaults={"theme": theme})
    return JsonResponse({"ok": True})
