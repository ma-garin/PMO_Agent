import json

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.middleware.csrf import get_token
from django.shortcuts import redirect
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.html import escape
from django.views.decorators.http import require_http_methods

from audit.services import record
from engagements.models import Engagement
from llm.prompt_utils import EXTERNAL_DATA_GUARD, wrap_external
from llm.services import LlmError, run_completion

from .models import PmoJsonStore, PmoTaskStore

# クライアントは全量保存のため、異常な巨大リクエストだけを弾く上限
MAX_TASKS = 500
# 汎用JSONストアの1件あたりの最大バイト数(報告本文など。過大POSTを弾く)
MAX_STORE_BYTES = 512 * 1024


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


def _json_for_script(value) -> str:
    """<script>内へ安全に埋め込むJSON文字列(タグ閉じ・行区切り文字を無害化)。"""
    return (
        json.dumps(value, ensure_ascii=False)
        .replace("<", "\\u003c")
        .replace(" ", "\\u2028")
        .replace(" ", "\\u2029")
    )


def _project_tokens(engagement: Engagement) -> dict[str, str]:
    """MVPテンプレートの __PROJECT_*__ トークンへ注入する実データ。

    Engagementに存在する値のみ実値を入れ、未連携ドメイン(文書/RAG/リスク/AI提案)は
    偽の数値を見せず「未連携」「0」を明示する。
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


def _json_stores(engagement: Engagement) -> dict[str, PmoJsonStore]:
    """案件の報告/KPI/AI提案ストアを種別キーで取得する。"""
    rows = PmoJsonStore.objects.filter(engagement=engagement)
    return {row.kind: row for row in rows}


def _server_tokens(request: HttpRequest, engagement: Engagement) -> dict[str, str]:
    """サーバー保存データとAPI設定をMVPテンプレートへ注入するトークン。"""
    store = PmoTaskStore.objects.filter(engagement=engagement).first()
    json_stores = _json_stores(engagement)
    report = json_stores.get(PmoJsonStore.Kind.REPORT)
    kpi = json_stores.get(PmoJsonStore.Kind.KPI)
    proposal = json_stores.get(PmoJsonStore.Kind.PROPOSAL)
    return {
        "__PMO_TASKS_JSON__": _json_for_script(store.tasks if store else []),
        "__PMO_USE_DEMO__": "false",
        "__PMO_TASKS_SAVED_AT__": escape(store.saved_at if store else ""),
        "__PMO_TASKS_STORE_HASH__": escape(store.store_hash if store else ""),
        "__PMO_TASKS_API_URL__": reverse("pmo_agent:tasks_api"),
        "__PMO_REPORT_JSON__": _json_for_script(report.payload if report else {}),
        "__PMO_REPORT_SAVED_AT__": escape(report.saved_at if report else ""),
        "__PMO_KPI_JSON__": _json_for_script(kpi.payload if kpi else {}),
        "__PMO_KPI_SAVED_AT__": escape(kpi.saved_at if kpi else ""),
        "__PMO_PROPOSAL_JSON__": _json_for_script(proposal.payload if proposal else {}),
        "__PMO_PROPOSAL_SAVED_AT__": escape(proposal.saved_at if proposal else ""),
        "__PMO_STORES_API_BASE__": reverse("pmo_agent:stores_api", args=["_kind_"]).replace(
            "_kind_/", ""
        ),
        "__PMO_AI_RUN_URL__": reverse("pmo_agent:ai_run"),
        "__PMO_CSRF_TOKEN__": get_token(request),
        # ヘッダー右端(ユーザーメニュー/案件切替/ログアウト)用
        "__PMO_USER_NAME__": escape(request.user.get_full_name() or request.user.username),
        "__PMO_USER_EMAIL__": escape(request.user.email or ""),
        "__PMO_USER_INITIALS__": escape((request.user.username[:2] or "PM").upper()),
        "__PMO_PROFILE_URL__": reverse("accounts:profile"),
        "__PMO_SELECT_URL__": reverse("engagements:select"),
        "__PMO_LOGOUT_URL__": reverse("accounts:logout"),
        "__PMO_LLM_SETTINGS_URL__": reverse("engagements:llm_settings"),
    }


@login_required
def home(request: HttpRequest) -> HttpResponse:
    """PMO Agent MVPシェルを、選択中Engagementの実データを注入して配信する。

    MVPは ``__PROJECT_*__`` トークンをサーバー側で置換する前提で設計されており、
    ここでは選択案件の実値とサーバー保存済みタスクを注入する。
    案件未選択(または権限なし)の場合は案件選択画面へ戻す。
    """
    engagement = _current_engagement(request)
    if engagement is None:
        return redirect("engagements:select")

    html = render_to_string("pmo_agent/mvp.html")
    tokens = {**_project_tokens(engagement), **_server_tokens(request, engagement)}
    for token, value in tokens.items():
        html = html.replace(token, value)
    return HttpResponse(html)


@login_required
@require_http_methods(["GET", "POST"])
def tasks_api(request: HttpRequest) -> JsonResponse:
    """案件単位のタスクストアAPI。GET=取得 / POST=全量保存(楽観ロック付き)。"""
    engagement = _current_engagement(request)
    if engagement is None:
        return JsonResponse({"error": "engagement_not_selected"}, status=403)

    if request.method == "GET":
        store = PmoTaskStore.objects.filter(engagement=engagement).first()
        return JsonResponse(
            {
                "tasks": store.tasks if store else [],
                "savedAt": store.saved_at if store else "",
                "storeHash": store.store_hash if store else "",
                "sourceVersion": f"dj-{engagement.pk}-v1",
            }
        )

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "invalid_json"}, status=400)

    tasks = payload.get("tasks")
    if (
        not isinstance(tasks, list)
        or len(tasks) > MAX_TASKS
        or not all(isinstance(t, dict) for t in tasks)
    ):
        return JsonResponse({"error": "invalid_tasks"}, status=400)

    store, _created = PmoTaskStore.objects.get_or_create(engagement=engagement)
    base_hash = str(payload.get("baseStoreHash") or "")
    if store.store_hash and base_hash and base_hash != store.store_hash:
        # 別端末が先に保存済み。クライアントは「更新」で再取得する。
        return JsonResponse(
            {"error": "conflict", "savedAt": store.saved_at, "storeHash": store.store_hash},
            status=409,
        )

    store.tasks = tasks
    store.store_hash = str(payload.get("storeHash") or "")[:64]
    store.saved_at = timezone.now().isoformat()
    store.updated_by = request.user
    store.save()
    record(
        request.user,
        "pmo_task_store_save",
        engagement,
        detail=f"{payload.get('action', 'save')} / {len(tasks)}件",
    )
    return JsonResponse({"ok": True, "savedAt": store.saved_at, "storeHash": store.store_hash})


@login_required
@require_http_methods(["GET", "POST"])
def stores_api(request: HttpRequest, kind: str) -> JsonResponse:
    """報告/KPI/AI提案の汎用JSONストアAPI。GET=取得 / POST=全量保存。

    保存はlast-write-winsだが、保存のたびにAuditLogへ記録するため
    「誰がいつ保存したか」の監査証跡はDBに残る。
    """
    if kind not in PmoJsonStore.Kind.values:
        return JsonResponse({"error": "invalid_kind"}, status=404)
    engagement = _current_engagement(request)
    if engagement is None:
        return JsonResponse({"error": "engagement_not_selected"}, status=403)

    if request.method == "GET":
        store = PmoJsonStore.objects.filter(engagement=engagement, kind=kind).first()
        return JsonResponse(
            {"payload": store.payload if store else {}, "savedAt": store.saved_at if store else ""}
        )

    if len(request.body) > MAX_STORE_BYTES:
        return JsonResponse({"error": "payload_too_large"}, status=413)
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "invalid_json"}, status=400)
    if not isinstance(payload, dict):
        return JsonResponse({"error": "invalid_payload"}, status=400)

    store, _created = PmoJsonStore.objects.get_or_create(engagement=engagement, kind=kind)
    store.payload = payload
    store.saved_at = timezone.now().isoformat()
    store.updated_by = request.user
    store.save()
    record(
        request.user,
        f"pmo_{kind}_store_save",
        engagement,
        detail=str(payload.get("action", "save")),
    )
    return JsonResponse({"ok": True, "savedAt": store.saved_at})


AI_SYSTEM = (
    "あなたはPMO(プロジェクトマネジメントオフィス)支援AIです。"
    "第三者検証会社のPMO実務向けに、日本語で簡潔に、確認・判断に使える形へ整理してください。"
    "見出しと箇条書きを使い、根拠が無い主張は『要確認』と明記し、最終判断・採用・承認は人が行う前提で書いてください。\n"
    + EXTERNAL_DATA_GUARD
)
AI_FALLBACK = (
    "## 生成AIは現在利用できません\n\n"
    "- LLMプロバイダへの接続に失敗しました(モデル未取得・APIキー未設定・接続不可などの可能性)。\n"
    "- 案件の「LLM設定」でプロバイダ/モデル/APIキーを確認し、再実行してください。\n"
    "- それまでは画面上のデータ(WBS・KPI・提案・根拠)を人が直接確認してください。"
)


@login_required
@require_http_methods(["POST"])
def ai_run(request: HttpRequest) -> JsonResponse:
    """全画面の「生成AIで〜」を案件のLLM設定で実行する。

    失敗時(LLM不通など)はフォールバック文言を返し、画面が壊れないようにする。
    呼び出しはllm.services経由でLlmCallLogに記録される。
    """
    engagement = _current_engagement(request)
    if engagement is None:
        return JsonResponse({"error": "engagement_not_selected"}, status=403)
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "invalid_json"}, status=400)

    screen = str(payload.get("screen", ""))[:40]
    action = str(payload.get("action", ""))[:60]
    request_text = str(payload.get("requestText", "")).strip()[:2000]
    screen_text = str(payload.get("screenText", "")).strip()[:4000]
    if not screen or not action or not request_text:
        return JsonResponse({"error": "missing_fields"}, status=400)

    prompt = f"{request_text}\n\n参考(現在の画面のデータ):\n{wrap_external(screen_text)}"
    created_at = timezone.now().isoformat()
    try:
        answer = run_completion(
            engagement,
            purpose=f"pmo_{action}"[:60],
            prompt=prompt,
            system=AI_SYSTEM,
            max_tokens=1200,
            user=request.user,
        )
        used_fallback = not (answer and answer.strip())
        if used_fallback:
            answer = AI_FALLBACK
        record(request.user, "pmo_ai_run", engagement, detail=f"{screen}/{action}")
        return JsonResponse(
            {
                "answer": answer,
                "provider": engagement.llm_provider,
                "usedFallback": used_fallback,
                "createdAt": created_at,
            }
        )
    except LlmError as exc:
        record(request.user, "pmo_ai_run_failed", engagement, detail=f"{screen}/{action}: {exc}"[:200])
        return JsonResponse(
            {
                "answer": AI_FALLBACK,
                "provider": engagement.llm_provider,
                "usedFallback": True,
                "error": str(exc)[:200],
                "createdAt": created_at,
            }
        )
