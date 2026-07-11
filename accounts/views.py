from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import ProfileForm


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
