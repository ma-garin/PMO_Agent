"""停滞検知後の能動要約(未読通知が閾値を超えた案件へのCopilot自動投稿)。"""

from __future__ import annotations

from datetime import date

from django.utils import timezone

from llm.providers.base import LlmError
from llm.services import run_completion
from tickets.models import Notification

from .models import ChatMessage, ChatThread

UNREAD_THRESHOLD = 10
AUTO_SUMMARY_SYSTEM = (
    "あなたはPMOアシスタントです。未読通知一覧から状況サマリーと推奨アクションを"
    "日本語の箇条書き中心で簡潔に作成してください。"
)


def _auto_summary_title(today: date) -> str:
    return f"(自動) 状況サマリー {today.isoformat()}"


def create_auto_summary(engagement, today: date | None = None) -> ChatThread | None:
    """未読通知がUNREAD_THRESHOLD件以上の案件に、1日1回まで自動サマリースレッドを作成する。"""
    today = today or timezone.localdate()

    unread = Notification.objects.filter(engagement=engagement, is_read=False).order_by(
        "-created_at"
    )
    unread_count = unread.count()
    if unread_count < UNREAD_THRESHOLD:
        return None

    title = _auto_summary_title(today)
    if ChatThread.objects.filter(engagement=engagement, title=title).exists():
        return None

    # スレッド作成者はシステム操作のため案件オーナーに帰属させる(created_byは必須項目)
    thread = ChatThread.objects.create(
        engagement=engagement, created_by=engagement.owner, title=title
    )

    notification_lines = "\n".join(f"- {n.message}" for n in unread[:20])
    prompt = (
        f"以下は案件「{engagement.name}」の未読通知一覧({unread_count}件)です。\n\n"
        f"{notification_lines}\n\n"
        "状況サマリーと推奨アクションを箇条書きで作成してください。"
    )
    try:
        body = run_completion(
            engagement, "copilot_auto_summary", prompt, system=AUTO_SUMMARY_SYSTEM
        )
    except LlmError:
        body = (
            f"未読通知が{unread_count}件あります。優先度の高いものから確認してください。\n\n"
            f"{notification_lines}"
        )

    ChatMessage.objects.create(thread=thread, role=ChatMessage.Role.ASSISTANT, content=body)
    return thread
