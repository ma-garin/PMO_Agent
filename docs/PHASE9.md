# Phase 9 実装仕様: 自律エージェント運転（オートパイロット）

前提: [HANDBOOK.md](HANDBOOK.md) 読了。**Phase 3（LLM）とPhase 7（リスク台帳・改善アクション・GeneralNotification）完了が必須**。Phase 8 D-3（監査ログ）は任意（あれば連携する）。

## グリルで確定した要件（2026-07-12）

| 論点 | 決定 |
|---|---|
| 自律の範囲 | **分析と提案まで**。エージェントは異常検知→原因分析→提案ドラフト作成を自律実行し、承認待ちキューに積む。承認された提案は**システム内の登録**（リスク追加・改善アクション作成・報告書ドラフト等）に反映。外部送信は従来原則のまま（定型文のみ、AI文面の自動送信はしない） |
| トリガー | **定期（日次巡回）＋チケット同期後のイベント検知**。検知はルールベースで確定的に、解釈・提案文はLLMで |
| 承認権限 | **案件メンバー全員**が承認/却下できる。誰がいつ判断したかを全件記録（監査ログ連携） |

## 用語（CONTEXT.md にも登録済み）

- **巡回**: エージェントが案件データを点検し異常を検知する実行単位（定期/イベント/手動）
- **提案**: エージェントが作成する承認待ちの行動案。承認でシステム内登録に反映、却下も記録される
- **承認キュー**: 未判断の提案の一覧。案件メンバー全員が判断できる

---

## Step 1: autopilotアプリ — モデル

```bash
python manage.py startapp autopilot
```

```python
# autopilot/models.py
class AgentSettings(models.Model):
    """案件ごとの自律運転設定。レコードが無い案件は運転OFF扱い。"""
    engagement = models.OneToOneField("engagements.Engagement", on_delete=models.CASCADE, related_name="agent_settings")
    enabled = models.BooleanField("自律運転を有効にする", default=False)
    stagnant_spike_threshold = models.PositiveSmallIntegerField("停滞急増の閾値(24h件数)", default=5)
    defect_spike_threshold = models.PositiveSmallIntegerField("欠陥急増の閾値(24h件数)", default=5)
    overdue_threshold = models.PositiveSmallIntegerField("期限超過の閾値(累計件数)", default=3)
    max_llm_calls_per_day = models.PositiveSmallIntegerField("LLM呼び出し上限(日)", default=20)
    updated_at = models.DateTimeField(auto_now=True)

class AgentRun(models.Model):
    """巡回の実行記録。"""
    class Trigger(models.TextChoices):
        SCHEDULED = "scheduled", "定期"
        EVENT = "event", "同期後イベント"
        MANUAL = "manual", "手動"
    class Status(models.TextChoices):
        RUNNING = "running", "実行中"
        SUCCESS = "success", "成功"
        FAILED = "failed", "失敗"
    engagement = models.ForeignKey("engagements.Engagement", on_delete=models.CASCADE, related_name="agent_runs")
    trigger = models.CharField(max_length=20, choices=Trigger.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.RUNNING)
    findings_count = models.PositiveSmallIntegerField("検知数", default=0)
    proposals_count = models.PositiveSmallIntegerField("提案数", default=0)
    error_message = models.TextField(blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    class Meta:
        ordering = ["-started_at"]

class AgentProposal(models.Model):
    """承認待ちキューに積まれる提案。"""
    class Kind(models.TextChoices):
        REGISTER_RISK = "register_risk", "リスク登録"
        CREATE_ACTION = "create_action", "改善アクション作成"
        DRAFT_REPORT = "draft_report", "報告書ドラフト作成"
        SUMMARY_ONLY = "summary_only", "状況共有(登録なし)"
    class Status(models.TextChoices):
        PENDING = "pending", "承認待ち"
        APPROVED = "approved", "承認"
        REJECTED = "rejected", "却下"
    engagement = models.ForeignKey("engagements.Engagement", on_delete=models.CASCADE, related_name="agent_proposals")
    run = models.ForeignKey(AgentRun, on_delete=models.CASCADE, related_name="proposals")
    kind = models.CharField(max_length=30, choices=Kind.choices)
    dedup_key = models.CharField("重複抑止キー", max_length=100)   # 例: "stagnant_spike:2026-07-12"
    title = models.CharField("提案", max_length=200)
    evidence = models.JSONField("検知根拠", default=dict)          # ルール名・実測値・閾値
    body = models.TextField("分析と提案内容")                       # LLM生成(またはルールのみの定型文)
    payload = models.JSONField("承認時の登録データ", default=dict)  # kindごとの構造(下記)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.CharField("判断メモ", max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(
            fields=["engagement", "kind", "dedup_key"],
            condition=models.Q(status="pending"),
            name="unique_pending_proposal")]
```

payloadのkind別スキーマ（apply時にバリデーション。欠けたキーは既定値）:
- `register_risk`: `{"title", "description", "probability", "impact", "measurement", "countermeasure"}` → RiskItem作成
- `create_action`: `{"title", "background", "due_days"}` → ImprovementAction作成（期限=今日+due_days）
- `draft_report`: `{"title", "period_days"}` → reports.services.generate_draftを呼びReport(draft)作成
- `summary_only`: `{}` → 登録なし（承認=既読扱い）

## Step 2: 検知ルール（autopilot/rules.py）— ルールベースで確定的に

```python
@dataclass(frozen=True)
class Finding:
    rule: str            # "stagnant_spike" 等
    title: str           # 人間可読の見出し
    evidence: dict       # {"observed": 7, "threshold": 5, "window": "24h"} 等
    suggested_kind: str  # AgentProposal.Kindの値

def evaluate_rules(engagement, settings: AgentSettings) -> list[Finding]:
```
組み込みルール4本（すべて既存データのみで判定・LLM不使用）:
1. `stagnant_spike`: 直近24hに作成された停滞通知(Notification kind=stagnant)件数 >= 閾値 → CREATE_ACTION
2. `defect_spike`: 直近24hに取り込まれた新規欠陥(analytics.get_defectsでsource_created_at基準) >= 閾値 → REGISTER_RISK
3. `overdue_accumulation`: 未クローズ×期限超過の欠陥 >= 閾値 → CREATE_ACTION
4. `convergence_stall`: 収束曲線で直近2週の累積クローズ増分が0かつ未クローズ>0 → DRAFT_REPORT（状況報告を提案）

dedup_keyは `f"{rule}:{今日のISO日付}"`（同日同ルールの重複提案を防ぐ。pending中はunique制約でも防がれる）。

## Step 3: 巡回サービスとタスク（autopilot/services.py, tasks.py）

```python
# services.py
def run_patrol(engagement, trigger: str) -> AgentRun:
    """AgentRun作成→evaluate_rules→Findingごとに提案を作成→Run完了。
    - LLM呼び出し前に当日のLlmCallLog(purpose="autopilot")件数を数え、
      max_llm_calls_per_dayを超えていたらLLMを使わずルール定型文でbodyを作る
    - LLM使用時: promptに Finding.evidence + summarize_defects + odc_distribution +
      高リスク一覧を渡し、body(分析2〜3段落) と payload(kind別JSON) を生成させる
      (JSONパースはanalytics/llm_suggest.pyと同じ「最初の{〜最後の}」方式)
    - LlmErrorは定型文フォールバック(巡回自体は止めない)
    - 提案作成時にGeneralNotification「エージェントから提案: {title}」を作成(Phase 7 Step 4)
    - 例外時: run.status=FAILED, error_message記録。raiseしない"""

def apply_proposal(proposal, user) -> None:
    """承認処理。kind別にpayloadを検証してシステム内登録を実行し、
    status/decided_by/decided_atを更新。監査ログapp(audit)がinstalledなら record()。
    却下(reject_proposal)は登録なしで記録のみ。"""

# tasks.py (Procrastinate)
@app.periodic(cron="30 8 * * *")
@app.task(name="autopilot.daily_patrol")
def daily_patrol(timestamp: int) -> None:
    # enabled=Trueの全案件に run_patrol(trigger="scheduled")

@app.task(name="autopilot.event_patrol")
def event_patrol(engagement_id: int) -> None:
    # tickets/tasks.py の sync_and_detect_engagement 末尾から、
    # AgentSettings.enabledの案件のみ defer される(trigger="event")
```

`tickets/tasks.py` への変更は末尾3行のみ（AgentSettings存在＋enabled確認→event_patrol.defer）。

## Step 4: 画面（URL prefix `/autopilot/`、nav_active: `autopilot`、サイドバー「&#9992; 自律運転」）

| URL | name | 内容 |
|---|---|---|
| GET `/autopilot/` | `autopilot:queue` | 承認キュー: pending提案のカード一覧（タイトル/種別バッジ/検知根拠テーブル/body/承認・却下ボタン＋判断メモ入力）。上部に直近のAgentRun状況（最終巡回日時・検知数） |
| POST `/autopilot/<pk>/approve/` | `autopilot:approve` | apply_proposal実行→messagesで結果表示 |
| POST `/autopilot/<pk>/reject/` | `autopilot:reject` | 却下記録 |
| GET `/autopilot/history/` | `autopilot:history` | 判断済み提案と巡回履歴（タブ切替、ページネーション20件） |
| GET/POST `/autopilot/settings/` | `autopilot:settings` | AgentSettingsフォーム（有効化・閾値3種・LLM上限）。案件メンバー編集可 |
| POST `/autopilot/run-now/` | `autopilot:run_now` | 手動巡回（run_patrol(trigger="manual")を同期実行、結果をmessages表示） |

承認/却下は**案件メンバーなら誰でも可**（`_current_engagement`で案件スコープ確認のみ。is_staff不要）。ヘッダー通知に提案が載るのはStep 3のGeneralNotification経由。

## Step 5: LLMプロンプト設計（run_patrol内）

- system: 「あなたは検証会社のPMOエージェント。検知された異常について、与えられたデータのみを根拠に①何が起きているか②考えられる原因③推奨アクションを日本語で簡潔に分析し、指定のJSON形式で出力。数値の捏造禁止」
- 出力形式: `{"body": "分析文", "payload": {kind別スキーマ}}`
- purpose="autopilot" でLlmCallLogに記録される（Phase 8 D-1のコストダッシュボードで監視可能）

## Step 6: テスト（autopilot/tests/）

- `test_rules.py`: 4ルールそれぞれの発火境界（閾値ちょうどで発火）・非発火。convergence_stallの「2週increment=0」判定
- `test_services.py`:
  - run_patrol: Finding→Proposal作成、同日重複のdedup（2回目で増えない）、LLM上限超過で定型文フォールバック、LlmErrorでもrun成功
  - apply_proposal: kind別の登録（RiskItem/ImprovementAction/Reportが実際に作られる）、payload欠損時の既定値、summary_onlyは何も作らない、二重承認の拒否（status!=pendingならエラーメッセージ）
- `test_views.py`: メンバーは承認できる／非メンバー404／却下の記録／設定フォーム保存
- `test_tasks.py`: enabled案件のみ巡回対象になる

## Done

1. デモ案件で閾値を下げて手動巡回→提案がキューに載る→承認でリスク/アクションが登録される→履歴と監査ログに残る、が画面で一通り動く
2. 同期タスク経由のイベント巡回が動く（閾値未満では提案が増えない）
3. `pytest`全パス／DESIGN.mdのPhase 9を実装済みに更新／コミット＆push
