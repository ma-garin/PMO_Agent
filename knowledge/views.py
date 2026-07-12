from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from engagements.models import Engagement

from .models import Document
from .tasks import process_document

MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def _current_engagement(request):
    engagement_id = request.session.get("current_engagement_id")
    if not engagement_id:
        return None
    return get_object_or_404(Engagement, pk=engagement_id)


@login_required
def document_list(request):
    engagement = _current_engagement(request)
    if engagement is None:
        return redirect("engagements:select")

    documents = Document.objects.filter(
        Q(engagement__isnull=True) | Q(engagement=engagement)
    ).select_related("engagement")

    context = {
        "engagement": engagement,
        "nav_active": "knowledge",
        "documents": documents,
    }
    return render(request, "knowledge/list.html", context)


@login_required
def upload(request):
    engagement = _current_engagement(request)
    if engagement is None:
        return redirect("engagements:select")

    if request.method != "POST":
        return redirect("knowledge:list")

    uploaded_file = request.FILES.get("file")
    if uploaded_file is None:
        messages.error(request, "ファイルを選択してください。")
        return redirect("knowledge:list")

    if uploaded_file.size > MAX_UPLOAD_BYTES:
        messages.error(request, "ファイルサイズは10MBまでです。")
        return redirect("knowledge:list")

    scope = request.POST.get("scope", "engagement")
    title = request.POST.get("title", "").strip() or uploaded_file.name

    document = Document.objects.create(
        engagement=None if scope == "common" else engagement,
        title=title,
        file=uploaded_file,
        uploaded_by=request.user,
    )
    process_document.defer(document_id=document.pk)
    messages.success(request, f"{title} を取込キューに追加しました。")
    return redirect("knowledge:list")


def _visible_documents(engagement):
    """一覧表示と同じ可視スコープ(共通資料＋現在案件の資料)。IDOR防止に使う。"""
    return Document.objects.filter(
        Q(engagement__isnull=True) | Q(engagement=engagement)
    )


@login_required
def delete(request, pk):
    engagement = _current_engagement(request)
    if engagement is None:
        return redirect("engagements:select")

    document = get_object_or_404(_visible_documents(engagement), pk=pk)
    if request.method == "POST":
        # 共通資料(全案件共有)は影響が広いため管理者のみ削除可
        if document.engagement_id is None and not request.user.is_staff:
            messages.error(request, "共通資料の削除には管理者権限が必要です。")
            return redirect("knowledge:list")
        document.file.delete(save=False)
        document.delete()
        messages.success(request, "文書を削除しました。")
    return redirect("knowledge:list")


@login_required
def reindex(request, pk):
    engagement = _current_engagement(request)
    if engagement is None:
        return redirect("engagements:select")

    document = get_object_or_404(_visible_documents(engagement), pk=pk)
    if request.method == "POST":
        process_document.defer(document_id=document.pk)
        messages.success(request, f"{document.title} を再取込キューに追加しました。")
    return redirect("knowledge:list")
