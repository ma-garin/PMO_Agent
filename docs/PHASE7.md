# Phase 7 実装仕様: 検証PMO支援モジュール（テストマネジメント＋品質改善伴走）

前提: [HANDBOOK.md](HANDBOOK.md) 読了。Phase 3（LLM）完了が必須、Phase 4（RAG）完了が望ましい（未完了ならRAG注入部分をスキップ可能な設計にしてある）。

## 背景と狙い

検証会社が提供する「検証PMO（テストマネジメント支援）」と「品質コンサルティング」に相当する業務を、本システム上で遂行・記録できるようにする。市販サービスの構成要素を参考に、業務領域を次の4つに分解して実装する（文言・成果物はすべて本システム独自のもの）:

| 領域 | 業務 | 本フェーズの機能 |
|---|---|---|
| 戦略・計画 | テスト戦略/マスターテスト計画/レベルテスト計画の策定 | テスト計画書の構造化管理＋LLMドラフト |
| 推進 | 進捗集計・課題管理・リスク監視 | 品質リスク台帳＋テスト進捗トラッキング |
| 評価 | 報告用情報の整理・振り返り | 品質ゲート判定＋既存レポートへの統合 |
| 改善伴走 | 欠陥分析からのプロセス改善 | 改善アクション管理（ODC/TPI/リスクと連携） |

## 事前決定事項（このまま実装する）

| 論点 | 決定 |
|---|---|
| テスト計画の粒度 | 案件ごとに複数のテスト計画書。`kind`でマスター/レベル別を区別（ISTQB用語準拠） |
| 計画書の形式 | 固定セクション構成のMarkdown（自由書式にしない。LLMドラフトと差分レビューを可能にするため） |
| リスク評価 | 発生確率×影響度の5×5マトリクス（スコア=確率×影響度、1〜25）。閾値: 15以上=高、8以上=中、それ未満=低 |
| テスト進捗の入力 | 手動の日次実績入力＋CSV一括取込の2経路（テスト管理ツール連携はスコープ外・将来課題） |
| 品質ゲート | 案件ごとの判定条件セット（テスト消化率・欠陥収束・高リスク残数など）。自動判定＋人の承認 |
| 新規アプリ | `testmgmt`（テスト計画・進捗・ゲート）と `risks`（リスク・改善アクション）の2アプリに分ける |

---

## Step 1: risksアプリ — 品質リスク台帳

### モデル（risks/models.py）

```python
class RiskItem(models.Model):
    class Status(models.TextChoices):
        IDENTIFIED = "identified", "識別"
        MONITORING = "monitoring", "監視中"
        MATERIALIZED = "materialized", "顕在化"
        CLOSED = "closed", "クローズ"
    engagement = models.ForeignKey("engagements.Engagement", on_delete=models.CASCADE, related_name="risks")
    title = models.CharField("リスク", max_length=200)
    description = models.TextField("内容", blank=True)
    probability = models.PositiveSmallIntegerField("発生確率(1-5)", default=3)
    impact = models.PositiveSmallIntegerField("影響度(1-5)", default=3)
    measurement = models.CharField("測定方法", max_length=300, blank=True)   # 例: 週次の欠陥収束率で監視
    countermeasure = models.TextField("顕在化時の対策", blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.IDENTIFIED)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    due_date = models.DateField("対応期限", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["status", "-updated_at"]

    @property
    def score(self) -> int:
        return self.probability * self.impact

    @property
    def severity(self) -> str:   # high/medium/low (閾値: 15/8)
        ...

class ImprovementAction(models.Model):
    """改善アクション。欠陥分析(ODC)・TPIアセスメント・リスクのどれかを起点に登録できる。"""
    class Status(models.TextChoices):
        PLANNED = "planned", "計画"
        IN_PROGRESS = "in_progress", "実行中"
        DONE = "done", "完了"
        CANCELLED = "cancelled", "中止"
    engagement = models.ForeignKey("engagements.Engagement", on_delete=models.CASCADE, related_name="improvement_actions")
    title = models.CharField("アクション", max_length=200)
    background = models.TextField("背景・根拠", blank=True)   # 例: ODC分析で結合テスト起因が突出
    origin_risk = models.ForeignKey(RiskItem, null=True, blank=True, on_delete=models.SET_NULL, related_name="actions")
    origin_note = models.CharField("起点(自由記述)", max_length=200, blank=True)  # 例: "TPI 2026-07回 テスト戦略が未達"
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    due_date = models.DateField("期限", null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PLANNED)
    effect_note = models.TextField("効果確認メモ", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["status", "due_date"]
```

### 画面（URL prefix `/risks/`、nav_active: `risks`、サイドバー表記「リスク・改善」&#9888;）

| URL | name | 内容 |
|---|---|---|
| GET `/risks/` | `risks:list` | 上段: 5×5リスクマトリクス（行=影響度5→1、列=確率1→5。セルに該当リスク数、高=danger-soft/中=#FFF3E0/低=ground背景。セルクリックで下の一覧を絞り込み `?p=&i=`） 下段: リスク一覧テーブル（重要度バッジ・状態・期限・担当） |
| GET/POST `/risks/new/` `/risks/<pk>/edit/` | `risks:create` `risks:edit` | リスクの登録・編集フォーム（ModelForm） |
| POST `/risks/<pk>/status/` | `risks:change_status` | 状態遷移（select＋ボタン） |
| GET `/risks/actions/` | `risks:actions` | 改善アクション一覧（かんばん風に計画/実行中/完了の3カラム表示。CSSはflexで簡易に） |
| GET/POST `/risks/actions/new/` `/risks/actions/<pk>/edit/` | | 登録・編集 |

### LLM連携（risks/services.py、Phase 3の`run_completion`を使用）

```python
def suggest_risks(engagement, user=None) -> list[dict]:
    """メトリクス(summarize_defects/odc_distribution)と未読通知を入力に、
    品質リスク候補を最大5件 {"title","description","probability","impact","measurement"} のJSON配列で提案。
    保存はせず候補を返し、画面で「採用」ボタンを押したものだけRiskItemに登録する(人の承認必須)。"""
```
- `/risks/suggest/` POST → 候補をセッションに保持して一覧上部に候補カードを表示 → 各候補の「採用」POSTで登録
- LlmError時はメッセージ表示（500にしない）

### テスト

- score/severityの境界値（15=高、8=中、7=低）
- マトリクス集計（セルごとの件数）とクエリ絞り込み
- suggest_risksのJSONパース（壊れたJSONで空リスト）・採用フローで保存されること
- 他案件のリスクが見えない/編集できない

---

## Step 2: testmgmtアプリ — テスト計画書

### モデル（testmgmt/models.py）

```python
class TestPlan(models.Model):
    class Kind(models.TextChoices):
        MASTER = "master", "マスターテスト計画"
        LEVEL = "level", "レベルテスト計画"
    class Status(models.TextChoices):
        DRAFT = "draft", "ドラフト"
        APPROVED = "approved", "承認済み"
    engagement = models.ForeignKey("engagements.Engagement", on_delete=models.CASCADE, related_name="test_plans")
    kind = models.CharField(max_length=10, choices=Kind.choices)
    title = models.CharField("タイトル", max_length=200)          # 例: "システムテスト計画 v1"
    test_level = models.CharField("対象テストレベル", max_length=50, blank=True)  # kind=levelのとき: 単体/結合/システム/受入
    body = models.TextField("本文", blank=True)                    # 固定セクションのMarkdown
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    approved_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

### 固定セクション（LLMドラフトも編集画面もこの構成を強制）

```
## 1. 目的とスコープ
## 2. テストレベルとテストタイプ
## 3. 開始基準・終了基準
## 4. スケジュールと体制
## 5. 品質リスクと対策方針
## 6. 成果物と報告
```

### LLMドラフト（testmgmt/services.py）

```python
def generate_plan_draft(engagement, kind: str, test_level: str = "", user=None) -> str:
    """promptに含める: 案件概要 / summarize_defects() / リスク台帳の高・中リスク(最大10件) /
    (Phase 4済なら) search_knowledge(engagement, "テスト計画 標準", top_k=3) の出典付き抜粋。
    systemで上記固定セクションのMarkdown出力・数値の捏造禁止・[出典n]明記を指示。
    run_completion(purpose="test_plan_draft", max_tokens=3000)"""
```

### 画面（URL prefix `/testmgmt/plans/`、nav_active: `testmgmt`、サイドバー「テスト計画」&#128203;は既存チケットと被るため&#128221;を使用）

- 一覧（kind別バッジ・状態・承認者）／新規作成（kind・タイトル・テストレベル選択→「AIドラフト生成」or「空で作成」）／編集（textarea＋Markdownプレビュー、reportsの実装を踏襲）／承認POST（approved_by/approved_atを記録、以後読み取り専用）

### テスト

- ドラフト生成promptに固定セクション指示とメトリクス数値が含まれる（run_completionをpatch）
- 承認後は編集POSTが拒否される／承認者・日時が記録される

---

## Step 3: testmgmtアプリ — テスト進捗と品質ゲート

### モデル（追加）

```python
class TestProgressEntry(models.Model):
    """日次のテスト実行実績。テストレベル単位で記録する。"""
    engagement = models.ForeignKey("engagements.Engagement", on_delete=models.CASCADE, related_name="test_progress")
    test_level = models.CharField("テストレベル", max_length=50)     # 単体/結合/システム/受入(自由文字列)
    date = models.DateField("日付")
    planned_cases = models.PositiveIntegerField("計画累計", default=0)   # その日時点の累計計画消化数
    executed_cases = models.PositiveIntegerField("実行累計", default=0)
    passed_cases = models.PositiveIntegerField("合格累計", default=0)
    note = models.CharField("メモ", max_length=200, blank=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["engagement", "test_level", "date"], name="unique_progress_per_day")]
        ordering = ["test_level", "date"]

class QualityGate(models.Model):
    """終了判定(品質ゲート)。条件はJSONで保持し自動判定+人の承認。"""
    class Verdict(models.TextChoices):
        PENDING = "pending", "判定前"
        PASSED = "passed", "合格"
        FAILED = "failed", "不合格"
    engagement = models.ForeignKey("engagements.Engagement", on_delete=models.CASCADE, related_name="quality_gates")
    name = models.CharField("ゲート名", max_length=100)              # 例: "システムテスト終了判定"
    criteria = models.JSONField("判定条件", default=dict)
    # criteria例: {"min_execution_rate": 95, "min_pass_rate": 90,
    #              "max_open_defects": 0, "max_high_risks": 0}
    verdict = models.CharField(max_length=10, choices=Verdict.choices, default=Verdict.PENDING)
    judged_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    judged_at = models.DateTimeField(null=True, blank=True)
    note = models.TextField("判定コメント", blank=True)
```

### サービス（testmgmt/services.py に追加）

```python
def progress_series(engagement, test_level: str) -> list[dict]
    # 日付順の {date, planned, executed, passed}。バーンアップ描画用

def progress_summary(engagement) -> list[dict]
    # テストレベルごとの最新エントリから {test_level, execution_rate, pass_rate, last_date}
    # execution_rate = executed/planned*100 (planned=0なら0)

def evaluate_gate(gate: QualityGate) -> dict
    # criteriaの各条件を実データと突合し {"results": [{"label","expected","actual","ok"}], "all_ok": bool}
    # 実データ: progress_summary(全レベル合算) / summarize_defects()のopen /
    #          RiskItem(status!=closed, severity=high)の件数
    # 未知のcriteriaキーは無視(前方互換)

def import_progress_csv(engagement, file) -> tuple[int, list[str]]
    # CSV(ヘッダ: test_level,date,planned_cases,executed_cases,passed_cases,note)を取込。
    # update_or_create。エラー行は行番号付きメッセージのリストで返し、正常行は取り込む
```

### 画面（`/testmgmt/progress/`・`/testmgmt/gates/`）

- 進捗: テストレベル別のバーンアップチャート（analyticsの`convergence_svg_points`を汎用化して再利用、planned/executed/passedの3本線）＋日次入力フォーム＋CSVアップロード
- ゲート: 一覧（判定結果バッジ）／作成（名前＋条件4項目の数値入力→criteria JSONに詰める）／詳細（evaluate_gateの結果表: 条件・期待値・実績・○×。全○でも**人が「合格にする」ボタンを押して確定**。判定者・日時・コメント記録）
- ダッシュボード連携: `dashboard/views.py`に進捗サマリー（最新の消化率）とオープン高リスク数のstatカードを追加（既存カードのレイアウトを崩さない範囲で）

### テスト

- evaluate_gateの各条件（境界値: 消化率ちょうど95%は合格側）／未知キー無視
- CSV取込: 正常・重複日付上書き・不正日付行スキップとエラーメッセージ
- progress_summaryのゼロ除算（planned=0）

---

## Step 4: 統合（レポート・Copilot・通知）

1. `reports.services.generate_draft` のpromptに以下を追加: リスク台帳サマリー（高/中/低件数と高リスクのタイトル）、テスト進捗サマリー、直近の品質ゲート判定結果。systemの章立てに「## テスト進捗」「## リスク状況」を追加
2. `copilot.context_builder.build_system_prompt` に高リスク（最大5件）と進捗サマリーを追加
3. 期限超過の改善アクション・リスクを既存Notificationに載せる: `tickets/tasks.py`の`sync_and_detect_engagement`実行時に、`due_date < today` かつ未完了のRiskItem/ImprovementActionへの通知を作成（Notification.kindに `risk_overdue` を追加するマイグレーション込み。unique制約は既存の(ticket,kind)がticket前提なので、**ticketをnull許容にしてリスク用は(engagement,kind,message)の重複チェックをget_or_createで行う**か、別モデル`GeneralNotification`を新設するか→ **別モデル新設を推奨**（既存の停滞検知を壊さない）。context_processorで両方を結合して表示）

## Done

1. リスク登録→マトリクス表示→AI候補の採用、テスト計画のAIドラフト→承認、進捗CSV取込→バーンアップ表示、ゲート判定→合格確定、が一通り画面で動く
2. レポート生成にリスク・進捗が反映される
3. `pytest`全パス／DESIGN.mdのPhase 7を実装済みに更新／コミット＆push

---

Phase 8以降のスコープは未定。**必ずユーザーと相談して確定すること**（勝手に候補を確定・記載しない）。
