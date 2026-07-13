"""PMO Agent APIの簡易レート制限。

django-axesは認証専用のため、保存系・LLM実行APIはユーザー×スコープ単位で
固定ウィンドウのスロットルを掛ける(LLMコスト保護・多重送信抑止)。
既定キャッシュ(LocMemCache)で動作する。
"""

import functools

from django.core.cache import cache
from django.http import JsonResponse


def throttle(scope: str, limit: int, window: int = 60):
    """POSTのみ、ユーザー×スコープで window 秒あたり limit 回に制限する。"""

    def decorator(view):
        @functools.wraps(view)
        def wrapped(request, *args, **kwargs):
            if request.method == "POST" and getattr(request.user, "pk", None):
                key = f"pmo_throttle:{scope}:{request.user.pk}"
                if cache.add(key, 1, window):
                    count = 1
                else:
                    try:
                        count = cache.incr(key)
                    except ValueError:
                        cache.set(key, 1, window)
                        count = 1
                if count > limit:
                    return JsonResponse(
                        {"error": "rate_limited", "detail": "短時間の操作が多すぎます。少し待って再実行してください。"},
                        status=429,
                    )
            return view(request, *args, **kwargs)

        return wrapped

    return decorator
