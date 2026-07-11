from __future__ import annotations

from .models import AuditLog


def record(actor, action: str, target=None, detail: str = "") -> AuditLog:
    """操作を明示的に記録する。呼び出し側(各記録ポイント)から都度呼ぶこと。"""
    target_type = target.__class__.__name__ if target is not None else ""
    target_id = getattr(target, "pk", None)
    return AuditLog.objects.create(
        actor=actor,
        action=action,
        target_type=target_type,
        target_id=target_id,
        detail=detail,
    )
