from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.template.loader import render_to_string
from django.utils.html import escape

from engagements.models import Engagement


def _current_engagement(request: HttpRequest) -> Engagement | None:
    """セッションの選択案件を、アクセス権(owner/member)込みで解決する。"""
    engagement_id = request.session.get("current_engagement_id")
    if not engagement_id:
        return None
    return (
        Engagement.objects.filter(
            Q(owner=request.user) | Q(members=request.user), pk=engagement_id
        )
        .distinct()
        .first()
    )


def _project_tokens(engagement: Engagement) -> dict[str, str]:
    """MVPテンプレートの __PROJECT_*__ トークンへ注入する実データ。

    Engagementに存在する値のみ実値を入れ、未連携ドメイン(文書/RAG/リスク/AI提案)は
    偽の数値を見せず「未連携」「0」を明示する。全トークンを置換するため、
    テンプレート末尾のデモ補完IIFEは実行されても何も書き換えない。
    """
    progress = str(int(engagement.progress or 0))
    return {
        "__PROJECT_NAME__": escape(engagement.name),
        "__PROJECT_TYPE__": escape(engagement.description or "未設定"),
        "__PROJECT_STATUS_TEXT__": escape(engagement.get_status_display()),
        "__PROJECT_STATUS_CLASS__": escape(engagement.status),
        "__PROJECT_PROGRESS_NUM__": progress,
        "__PROJECT_PROGRESS_DELTA__": escape(
            f"更新 {engagement.updated_at:%Y/%m/%d}" if engagement.updated_at else "登録値"
        ),
        "__PROJECT_DOCUMENT_COUNT__": "0",
        "__PROJECT_DOC_KPI_LABEL__": "登録文書",
        "__PROJECT_DOC_INDEXED__": "0",
        "__PROJECT_DOC_TOTAL__": "0",
        "__PROJECT_DOC_INDEX_SUB__": "文書管理は未連携",
        "__PROJECT_DOC_INDEX_WIDTH__": "0",
        "__PROJECT_RAG_INDEX_STATUS__": "未連携",
        "__PROJECT_RAG_TEXT__": "RAG未連携",
        "__PROJECT_RAG_CLASS__": "n",
        "__PROJECT_SEARCH_SCOPE__": "案件内ドキュメント",
        "__PROJECT_NEXT_ACTION__": "-",
        "__PROJECT_OPEN_RISKS__": "0",
        "__PROJECT_RISK_DELTA__": "リスク台帳は未連携",
        "__PROJECT_RISK_WIDTH__": "0",
        "__PROJECT_AI_ACTIONS__": "0",
        "__PROJECT_AI_ACTION_LABEL__": "確認待ち提案",
        "__PROJECT_WORKSPACE__": escape(
            engagement.owner.get_full_name() or engagement.owner.username
        ),
        # タスクstoreを案件単位に分離する(localStorageキーと保存データの整合判定に使用)
        "__PROJECT_TASK_STORE_KEY__": f"engagement-{engagement.pk}",
        "__PROJECT_TASK_SOURCE_VERSION__": f"dj-{engagement.pk}-v1",
    }


@login_required
def home(request: HttpRequest) -> HttpResponse:
    """PMO Agent MVPシェルを、選択中Engagementの実データを注入して配信する。

    MVPは ``__PROJECT_*__`` トークンをサーバー側で置換する前提で設計されており、
    ここでは選択案件の実値を注入する。案件未選択(または権限なし)の場合は
    案件選択画面へ戻す。
    """
    engagement = _current_engagement(request)
    if engagement is None:
        return redirect("engagements:select")

    html = render_to_string("pmo_agent/mvp.html")
    for token, value in _project_tokens(engagement).items():
        html = html.replace(token, value)
    return HttpResponse(html)
