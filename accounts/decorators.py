from collections.abc import Callable
from functools import wraps
from typing import Any

from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect


def admin_required(view_func: Callable[..., HttpResponse]) -> Callable[..., HttpResponse]:
    @wraps(view_func)
    def _wrapped(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        if not request.user.is_staff:
            messages.error(request, "この操作には管理者権限が必要です。")
            return redirect("dashboard:home")
        return view_func(request, *args, **kwargs)

    return _wrapped
