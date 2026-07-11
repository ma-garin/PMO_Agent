# Phase 3 実装仕様: LLM抽象化層・ODC推定・Copilotチャット・レポート生成

前提: [../HANDBOOK.md](../HANDBOOK.md) を読了していること。ステップ順に実装し、各ステップ完了ごとにテスト→コミットする。

## 全体像と非スコープ

- 作るもの: ①`llm`アプリ（3プロバイダ抽象化＋監査ログ） ②ODC分類のLLM推定候補 ③`copilot`アプリ（案件文脈チャット） ④`reports`アプリ（品質報告書ドラフト生成）
- 作らないもの: ストリーミング表示（同期リクエストでよい）、RAG連携（Phase 4）、Officeファイル出力（画面表示＋ブラウザ印刷CSSでPDF化とする）

---

## Step 1: llmアプリ（抽象化層＋監査ログ）

### 1-1. アプリ作成と登録

```bash
python manage.py startapp llm
```
`config/settings.py` の INSTALLED_APPS に `"llm"` を追加。

### 1-2. 環境変数（.env.exampleにも追記）

```
ANTHROPIC_API_KEY=          # Claude API用
OPENAI_API_KEY=             # OpenAI API用
LLM_CLAUDE_MODEL=claude-haiku-4-5-20251001
LLM_OPENAI_MODEL=gpt-4o-mini
OLLAMA_BASE_URL=http://localhost:11434
LLM_OLLAMA_MODEL=qwen2.5:7b
```

### 1-3. モデル（llm/models.py）

```python
class LlmCallLog(models.Model):
    """全LLM呼び出しの監査ログ(ADR-0002: 監査要件)。プロンプト原文は保存しない(機密)。"""
    class Status(models.TextChoices):
        SUCCESS = "success", "成功"
        FAILED = "failed", "失敗"

    engagement = models.ForeignKey("engagements.Engagement", on_delete=models.CASCADE, related_name="llm_call_logs")
    provider = models.CharField("プロバイダ", max_length=20)          # openai/claude/ollama
    purpose = models.CharField("用途", max_length=50)                 # odc_suggest/copilot_chat/report_draft
    prompt_chars = models.PositiveIntegerField("プロンプト文字数", default=0)
    response_chars = models.PositiveIntegerField("応答文字数", default=0)
    status = models.CharField(max_length=20, choices=Status.choices)
    error_message = models.TextField(blank=True)
    duration_ms = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
```
adminにも登録（list_display: engagement, provider, purpose, status, duration_ms, created_at）。

### 1-4. プロバイダ抽象化（llm/providers/ パッケージ）

`llm/providers/base.py`:
```python
from abc import ABC, abstractmethod

class LlmError(Exception):
    pass

class LlmProvider(ABC):
    name: str = ""

    @abstractmethod
    def complete(self, prompt: str, *, system: str = "", max_tokens: int = 1024) -> str:
        """単発のテキスト補完。失敗時はLlmErrorをraise。"""
```

`llm/providers/claude.py`（**requestsのみ使用。SDK追加禁止**）:
- POST `https://api.anthropic.com/v1/messages`
- headers: `x-api-key: {ANTHROPIC_API_KEY}`, `anthropic-version: 2023-06-01`, `content-type: application/json`
- body: `{"model": LLM_CLAUDE_MODEL, "max_tokens": max_tokens, "system": system, "messages": [{"role": "user", "content": prompt}]}`
- 応答: `resp.json()["content"][0]["text"]`
- timeout=60秒。`requests.RequestException` と非200は `LlmError(str(exc))` に変換

`llm/providers/openai.py`:
- POST `https://api.openai.com/v1/chat/completions`
- headers: `Authorization: Bearer {OPENAI_API_KEY}`
- body: `{"model": LLM_OPENAI_MODEL, "max_tokens": max_tokens, "messages": [{"role":"system","content":system},{"role":"user","content":prompt}]}`（systemが空なら省略）
- 応答: `resp.json()["choices"][0]["message"]["content"]`

`llm/providers/ollama.py`:
- POST `{OLLAMA_BASE_URL}/api/chat`
- body: `{"model": LLM_OLLAMA_MODEL, "stream": false, "messages": [...openaiと同形...]}`
- 応答: `resp.json()["message"]["content"]`
- APIキー不要。接続不可(ConnectionError)は `LlmError("Ollamaに接続できません。ollama serveが起動しているか確認してください")`

`llm/providers/__init__.py`:
```python
def get_provider(provider_name: str) -> LlmProvider   # 不明名はValueError
```

### 1-5. サービス（llm/services.py）— 呼び出し窓口はこの1関数のみ

```python
def run_completion(engagement, purpose: str, prompt: str, *,
                   system: str = "", max_tokens: int = 1024, user=None) -> str:
    """engagement.llm_providerでプロバイダを解決し、実行し、LlmCallLogを必ず記録する。
    成功: 応答文字列を返す / 失敗: LlmCallLog(FAILED)記録後にLlmErrorを再raise"""
```
実装ポイント: `time.monotonic()`で計測、try/except/finallyでログ作成。**他アプリはproviderを直接触らず必ずこの関数を通す**。

### 1-6. テスト（llm/tests/）

- `test_providers.py`: `responses`で各プロバイダのHTTPをモックし、正常応答のパース・非200でLlmError・タイムアウト例外変換を検証（各プロバイダ3ケース）
- `test_services.py`: `unittest.mock.patch("llm.services.get_provider")` でフェイクを注入し、①成功時にLlmCallLog(SUCCESS)が作られる ②LlmError時にFAILEDログ＋例外再送出 ③engagement.llm_providerが渡ること
- コミット例: `feat: LLM抽象化層(3プロバイダ+監査ログ)を追加`

---

## Step 2: ODC分類のLLM推定候補

### 2-1. サービス（analytics/llm_suggest.py 新規）

```python
SUGGEST_SYSTEM = "あなたはソフトウェア品質保証の専門家です。欠陥チケットをODC分類します。必ずJSONのみで回答してください。"

def build_prompt(ticket) -> str: ...
def suggest_classification(ticket, user=None) -> OdcClassification: ...
```
- プロンプトには: チケットのsummary/description/status/priority と、4軸それぞれの選択肢（`OdcClassification.DefectType.choices` 等の value と日本語label の対応表）を列挙し、`{"defect_type": "...", "trigger": "...", "activity": "...", "impact": "..."}` 形式のJSONのみを返すよう指示
- `llm.services.run_completion(engagement, purpose="odc_suggest", ...)` を呼ぶ
- 応答パース: `json.loads`前に、応答から最初の`{`〜最後の`}`を切り出す（LLMが前後に文を付けても耐える）。パース失敗・choices外の値は該当軸を空文字にする
- **status=CONFIRMEDの既存分類は絶対に上書きしない**（その場合は何もせず既存を返す）。それ以外は `update_or_create` で `source=LLM, status=PENDING` として保存

### 2-2. ビューとUI（analytics/views.py・analysis.html）

- `POST /analytics/suggest/` (`analytics:suggest_bulk`): 現在案件の欠陥のうち「確定済み分類が無い」ものを古い順に最大10件、`suggest_classification`を実行。件数と失敗件数をmessagesで表示（LlmErrorはcatchしてエラーメッセージ表示、500にしない）
- analysis.htmlのODC分類テーブル上部に `AI推定を実行（未分類から最大10件）` ボタン（form POST）を追加
- 推定済み（PENDING）の行は既存の「レビュー待ち」バッジ表示とselectのプリセットで自然に反映される（既存実装のまま動く）

### 2-3. テスト（analytics/tests/test_llm_suggest.py）

- run_completionをpatchして: ①正常JSON→PENDING分類が保存される ②確定済みは上書きされない ③壊れたJSON→全軸空のPENDING ④choices外の値→該当軸のみ空
- コミット例: `feat: ODC分類のLLM推定候補を追加`

---

## Step 3: copilotアプリ（PMO相談チャット）

### 3-1. モデル（copilot/models.py）

```python
class ChatThread(models.Model):
    engagement = models.ForeignKey("engagements.Engagement", on_delete=models.CASCADE, related_name="chat_threads")
    title = models.CharField("タイトル", max_length=200, default="新しい相談")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        ordering = ["-updated_at"]

class ChatMessage(models.Model):
    class Role(models.TextChoices):
        USER = "user", "ユーザー"
        ASSISTANT = "assistant", "アシスタント"
    thread = models.ForeignKey(ChatThread, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=10, choices=Role.choices)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ["created_at"]
```

### 3-2. 文脈構築（copilot/context_builder.py）

```python
def build_system_prompt(engagement) -> str:
```
以下を含む日本語のsystemプロンプトを組み立てる:
1. 役割宣言（「あなたは第三者検証会社のPMOを支援するアシスタント」）
2. 案件名・ステータス・進捗
3. `analytics.services.summarize_defects()` の結果（欠陥総数/未クローズ/期限超過/平均滞留/欠陥密度）
4. `analytics.services.odc_distribution()` の確定済み分布（軸ごと上位3件）
5. 未読通知（`Notification.objects.filter(engagement=..., is_read=False)[:5]` のmessage）
6. 「データに基づいて簡潔に回答し、わからないことは推測せずその旨を言う」という指示

### 3-3. ビュー/URL（copilot/views.py, urls.py, config/urls.py に `path("copilot/", ...)`）

| URL | name | 動作 |
|---|---|---|
| GET `/copilot/` | `copilot:home` | スレッド一覧＋最新スレッドへリダイレクト（なければ空状態表示） |
| POST `/copilot/threads/new/` | `copilot:new_thread` | スレッド作成→そのスレッドへ |
| GET `/copilot/threads/<pk>/` | `copilot:thread` | メッセージ一覧＋入力フォーム |
| POST `/copilot/threads/<pk>/send/` | `copilot:send` | 下記フロー |

sendのフロー: ①ユーザーメッセージ保存 ②会話履歴（直近10件を `[USER] ...\n[ASSISTANT] ...` 形式で連結）＋今回の質問をpromptに、`run_completion(engagement, purpose="copilot_chat", system=build_system_prompt(...), max_tokens=2000)` ③応答をASSISTANTとして保存 ④スレッドtitleが初期値なら質問の先頭30文字に更新 ⑤thread画面へredirect。LlmErrorはmessages.errorで表示しユーザーメッセージは残す。

### 3-4. テンプレート（templates/copilot/thread.html）

- 2カラング: 左にスレッド一覧（案件のもの）、右にメッセージ吹き出し＋送信フォーム
- 吹き出しCSSは新規 `static/css/copilot.css`（userは右寄せ`--primary-soft`背景、assistantは左寄せ`--surface`）
- sidebar.htmlに `&#129302; Copilot` を追加（nav_active: `copilot`）

### 3-5. テスト（copilot/tests/）

- run_completionをpatchして: send POSTでUSER/ASSISTANT両メッセージが保存される、タイトル自動命名、LlmError時にASSISTANTが保存されずエラーメッセージ、他案件のスレッドが見えない（404）
- コミット例: `feat: PMO Copilotチャットを追加`

---

## Step 4: reportsアプリ（品質報告書）

### 4-1. モデル（reports/models.py）

```python
class Report(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "ドラフト"
        APPROVED = "approved", "承認済み"
    engagement = models.ForeignKey("engagements.Engagement", on_delete=models.CASCADE, related_name="reports")
    title = models.CharField("タイトル", max_length=200)
    period_start = models.DateField("対象期間(自)")
    period_end = models.DateField("対象期間(至)")
    body = models.TextField("本文", blank=True)          # Markdown
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        ordering = ["-created_at"]
```

### 4-2. ドラフト生成（reports/services.py）

```python
def generate_draft(engagement, period_start, period_end, user=None) -> str:
```
- promptに含める: 案件情報／`summarize_defects()`／`convergence_series()`の直近8点／`odc_distribution()`／期間
- systemで章立てを固定: 「# 品質状況報告書」「## サマリー」「## 定量分析」「## ODC分析所見」「## リスクと提言」のMarkdownで出力せよ、数値は与えたデータのみ使用し捏造禁止、と指示
- `run_completion(purpose="report_draft", max_tokens=3000)`

### 4-3. ビュー/URL（`path("reports/", ...)`）

| URL | name | 動作 |
|---|---|---|
| GET `/reports/` | `reports:list` | 案件の報告書一覧＋新規作成フォーム(タイトル・期間) |
| POST `/reports/create/` | `reports:create` | Report作成→generate_draftでbody生成→編集画面へ（LlmError時はbody空で作成しエラー表示） |
| GET/POST `/reports/<pk>/` | `reports:edit` | textareaでbody編集・保存。「承認」ボタンでstatus=APPROVED |
| GET `/reports/<pk>/print/` | `reports:print` | 印刷用ページ |

- Markdown表示: 新規依存 `markdown`（`pip install markdown`、requirements.txtへ）。テンプレートフィルタを自作せずビューで `markdown.markdown(report.body, extensions=["tables"])` してcontextへ
- 印刷ページ: sidebar/headerを含まない単独レイアウト＋`@media print`でボタン非表示。「PDFとして保存」はブラウザの印刷機能を案内する文言を画面に表示（追加依存なしでPDF要件を満たす）
- sidebar.htmlに `&#128196; レポート`（nav_active: `reports`）

### 4-4. テスト

- generate_draftのprompt組み立て（メトリクス数値が含まれる）、create→edit→approveフロー、他案件の報告書は404
- コミット例: `feat: 品質報告書のドラフト生成と承認フローを追加`

---

## 最終確認（Phase 3全体のDone）

1. 案件のLLMプロバイダをOllamaにし、`ollama serve`＋`ollama pull qwen2.5:7b` 環境で: AI推定→チャット→報告書生成が通ること（Ollama未導入環境ではエラーメッセージが画面に出て500にならないこと）
2. `pytest` 全パス／`manage.py check` クリーン
3. docs/DESIGN.md のロードマップPhase 3を「実装済み」に更新
4. コミット＆push
