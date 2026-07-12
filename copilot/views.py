from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from engagements.models import Engagement
from llm.providers.base import LlmError
from llm.services import run_completion

from llm.prompt_utils import wrap_external

from .context_builder import build_rag_context, build_system_prompt
from .models import ChatMessage, ChatThread

HISTORY_LIMIT = 10
MAX_TOKENS = 2000


def _current_engagement(request):
    engagement_id = request.session.get("current_engagement_id")
    if not engagement_id:
        return None
    return get_object_or_404(Engagement, pk=engagement_id)


@login_required
def home(request):
    engagement = _current_engagement(request)
    if engagement is None:
        return redirect("engagements:select")

    latest = engagement.chat_threads.order_by("-updated_at").first()
    if latest is not None:
        return redirect("copilot:thread", pk=latest.pk)

    threads = engagement.chat_threads.none()
    return render(
        request,
        "copilot/thread.html",
        {"engagement": engagement, "nav_active": "copilot", "threads": threads, "thread": None, "chat_messages": []},
    )


@login_required
def new_thread(request):
    engagement = _current_engagement(request)
    if engagement is None:
        return redirect("engagements:select")

    thread = ChatThread.objects.create(engagement=engagement, created_by=request.user)
    return redirect("copilot:thread", pk=thread.pk)


@login_required
def thread(request, pk):
    engagement = _current_engagement(request)
    if engagement is None:
        return redirect("engagements:select")

    current_thread = get_object_or_404(ChatThread, pk=pk, engagement=engagement)
    threads = engagement.chat_threads.all()
    return render(
        request,
        "copilot/thread.html",
        {
            "engagement": engagement,
            "nav_active": "copilot",
            "threads": threads,
            "thread": current_thread,
            "chat_messages": current_thread.messages.all(),
        },
    )


@login_required
def send(request, pk):
    engagement = _current_engagement(request)
    if engagement is None:
        return redirect("engagements:select")

    current_thread = get_object_or_404(ChatThread, pk=pk, engagement=engagement)
    question = request.POST.get("content", "").strip()
    if not question:
        return redirect("copilot:thread", pk=pk)

    ChatMessage.objects.create(thread=current_thread, role=ChatMessage.Role.USER, content=question)

    if current_thread.title == "新しい相談":
        current_thread.title = question[:30]
        current_thread.save(update_fields=["title"])

    history = current_thread.messages.order_by("created_at")[: 2 * HISTORY_LIMIT]
    history_text = "\n".join(
        f"[{m.get_role_display()}] {m.content}" for m in history
    )
    rag_context = build_rag_context(engagement, question)
    if rag_context:
        # 参考資料(取込文書)は外部由来のため区切りで囲む(F-11)
        prompt = (
            f"## 参考資料\n{wrap_external(rag_context)}\n\n## 会話\n{history_text}\n\n"
            "上記の会話を踏まえて、直近の質問に回答してください。"
            "参考資料を使った場合は文末に[出典n]を明記してください。"
        )
    else:
        prompt = f"{history_text}\n\n上記の会話を踏まえて、直近の質問に回答してください。"

    try:
        answer = run_completion(
            engagement,
            "copilot_chat",
            prompt,
            system=build_system_prompt(engagement),
            max_tokens=MAX_TOKENS,
            user=request.user,
        )
        ChatMessage.objects.create(
            thread=current_thread, role=ChatMessage.Role.ASSISTANT, content=answer
        )
    except LlmError as exc:
        messages.error(request, f"応答の生成に失敗しました: {exc}")

    current_thread.save(update_fields=["updated_at"])
    return redirect("copilot:thread", pk=pk)
