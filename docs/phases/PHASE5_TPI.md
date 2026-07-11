# Phase 5 実装仕様: TPIアセスメント（テストプロセス成熟度評価）

前提: [../HANDBOOK.md](../HANDBOOK.md) と Phase 3（LLM）・Phase 4（RAG）完了。

## 全体像と重要な制約

- 作るもの: `tpi`アプリ。TPI NEXTモデルの**フレームワーク構造**（キーエリア×成熟度レベル×チェックポイント）を管理する器、案件ごとのアセスメント記入UI、成熟度マトリクス可視化、LLM＋RAGによる改善提言
- **著作権上の制約（必読）**: TPI NEXTのキーエリア定義やチェックポイントの文言は書籍の著作物である。**書籍のチェックポイント本文をコード・fixture・マイグレーションに同梱してはならない**。システムはあくまで「空の器＋自社入力」で出荷する。キーエリアやチェックポイントの内容は、利用企業が自社で保有・ライセンスされた資料からCSVインポートまたは画面入力する

## 事前決定事項（このまま実装する）

| 論点 | 決定 |
|---|---|
| 成熟度レベル | 固定3段階: `controlled`(コントロールド) / `efficient`(エフィシェント) / `optimizing`(オプティマイジング)。未達は「イニシャル」（レベル未達状態を指すだけでDB値は持たない） |
| レベル判定 | あるレベルに到達＝そのレベル**以下すべて**のチェックポイントが充足（例: efficient到達にはcontrolledも全充足） |
| キーエリア | マスターデータとしてユーザーが管理（件数の決め打ちをしない）。表示順は`order`フィールド |
| アセスメントの単位 | 案件 × 実施回。同一案件で繰り返し実施し、時系列比較できる |
| 判定の入力 | チェックポイントごとに 充足/未充足/対象外 の3値＋任意メモ |

## Step 1: モデル（tpi/models.py）

```python
class TpiKeyArea(models.Model):
    """キーエリアのマスター。内容はユーザーが投入する(同梱しない)。"""
    name = models.CharField("キーエリア名", max_length=100, unique=True)
    description = models.CharField("説明", max_length=300, blank=True)
    order = models.PositiveSmallIntegerField("表示順", default=0)
    is_active = models.BooleanField("有効", default=True)
    class Meta:
        ordering = ["order", "id"]

class MaturityLevel(models.TextChoices):
    CONTROLLED = "controlled", "コントロールド"
    EFFICIENT = "efficient", "エフィシェント"
    OPTIMIZING = "optimizing", "オプティマイジング"

LEVEL_ORDER = ["controlled", "efficient", "optimizing"]  # 判定に使う昇順

class TpiCheckpoint(models.Model):
    key_area = models.ForeignKey(TpiKeyArea, on_delete=models.CASCADE, related_name="checkpoints")
    level = models.CharField("成熟度レベル", max_length=20, choices=MaturityLevel.choices)
    text = models.CharField("チェックポイント", max_length=500)
    order = models.PositiveSmallIntegerField("表示順", default=0)
    class Meta:
        ordering = ["key_area", "level", "order", "id"]

class TpiAssessment(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "実施中"
        FINAL = "final", "確定"
    engagement = models.ForeignKey("engagements.Engagement", on_delete=models.CASCADE, related_name="tpi_assessments")
    title = models.CharField("タイトル", max_length=200)   # 例: "2026年7月 定期アセスメント"
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    assessed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        ordering = ["-created_at"]

class TpiAnswer(models.Model):
    class Result(models.TextChoices):
        MET = "met", "充足"
        NOT_MET = "not_met", "未充足"
        NA = "na", "対象外"
    assessment = models.ForeignKey(TpiAssessment, on_delete=models.CASCADE, related_name="answers")
    checkpoint = models.ForeignKey(TpiCheckpoint, on_delete=models.CASCADE, related_name="+")
    result = models.CharField(max_length=10, choices=Result.choices, default=Result.NOT_MET)
    note = models.CharField("メモ", max_length=300, blank=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["assessment", "checkpoint"], name="unique_answer_per_checkpoint")]
```
adminに4モデルとも登録（TpiCheckpointはkey_area/levelでlist_filter）。

## Step 2: マスター投入経路（2つ用意する）

### 2-1. CSVインポート管理コマンド（tpi/management/commands/import_tpi_checkpoints.py）

```bash
python manage.py import_tpi_checkpoints path/to/checkpoints.csv
```
CSV仕様（1行目ヘッダ必須、UTF-8）:
```
key_area,level,text,order
テスト戦略,controlled,（自社基準の文言）,1
```
- key_areaは名前でget_or_create（orderは出現順で自動採番）
- levelはcontrolled/efficient/optimizingのみ許可、他はエラー行として行番号を表示して当該行スキップ
- 同一(key_area, level, text)は重複作成しない
- 完了時に「キーエリアN件・チェックポイントM件を取込」と出力

### 2-2. 画面での追加・編集

設定タブに「TPIマスター」を追加（`settings_tab: "tpi"`、partials/settings_tabs.htmlに追記）。キーエリアの追加/名称変更/並び順、チェックポイントの追加/編集/削除ができる素朴なフォーム画面。

## Step 3: 成熟度判定ロジック（tpi/services.py）

```python
def level_status(assessment, key_area) -> dict:
    """キーエリア1件の判定。
    返り値: {"achieved_level": "controlled"|"efficient"|"optimizing"|None,
             "levels": {level: {"total": int, "met": int, "na": int, "complete": bool}}}
    - completeの定義: そのレベルの全チェックポイントが 充足 または 対象外（未回答は未充足扱い）
    - チェックポイントが1件もないレベルは complete=True とみなす(空レベルで詰まらない)
    - ただし全レベルが空のキーエリアは achieved_level=None
    - achieved_level: LEVEL_ORDER順に、下位からすべてcompleteな最上位レベル"""

def assessment_matrix(assessment) -> list[dict]:
    """全有効キーエリア分のlevel_statusを返す(マトリクス描画用)。
    [{"key_area": TpiKeyArea, "achieved_level": ..., "levels": {...}}, ...]"""

def unmet_checkpoints(assessment) -> list[TpiAnswer]:
    """未充足(NOT_MET)の回答一覧(改善提言のLLM入力に使う)。"""
```

## Step 4: 画面

| URL | name | 動作 |
|---|---|---|
| GET `/tpi/` | `tpi:list` | 案件のアセスメント一覧＋新規作成（タイトル入力） |
| GET `/tpi/<pk>/` | `tpi:detail` | 成熟度マトリクス＋キーエリア別サマリー＋改善提言表示 |
| GET/POST `/tpi/<pk>/answer/<key_area_pk>/` | `tpi:answer` | キーエリア1件分の回答フォーム（チェックポイントを表で列挙、3値ラジオ＋メモ、保存） |
| POST `/tpi/<pk>/finalize/` | `tpi:finalize` | status=FINAL（以後answerは読み取り専用表示） |
| POST `/tpi/<pk>/suggest/` | `tpi:suggest` | LLM改善提言の生成（下記） |

マトリクス表示（templates/tpi/detail.html＋static/css/tpi.css）:
- 行=キーエリア、列=3レベル。到達済みセルは `--success-soft`、部分達成（met>0だが未complete）は `#FFF3E0`、未着手は `--ground`。セル内に `met/total` を表示
- 行末に到達レベルのバッジ（未達なら「イニシャル」灰色バッジ）
- sidebar.htmlに `&#128209; TPI評価`（nav_active: `tpi`）

## Step 5: LLM改善提言（tpi/services.py に追加）

```python
def generate_suggestion(assessment, user=None) -> str:
```
- prompt: マトリクスのサマリー（キーエリアごとの到達レベル）＋未充足チェックポイント（キーエリア名・レベル・文言、最大30件）＋Phase 4の `search_knowledge(engagement, "テストプロセス 改善", top_k=3)` の出典付き抜粋
- system: 「テストプロセス改善のコンサルタントとして、優先度順に改善アクションを3〜5件、根拠と共にMarkdownで提案。参考資料を使った場合は[出典n]を明記」
- `run_completion(purpose="tpi_suggest", max_tokens=2000)`
- 結果は `TpiAssessment` に `suggestion = models.TextField(blank=True)` を追加して保存（このフィールドもStep 1のモデルに含めてよい）

## Step 6: テスト（tpi/tests/）

- `test_services.py`（最重要）:
  - controlled全充足のみ → achieved_level == "controlled"
  - controlled全充足＋efficient一部 → "controlled" のまま
  - 全レベル充足 → "optimizing"
  - controlledに未充足1件＋efficient全充足 → **None**（下位が欠けたら上位は無効）
  - NA扱い: NAのみのレベルはcomplete
  - チェックポイント0件のレベルを飛ばして判定できる
  - 全レベル空のキーエリア → None
- `test_import.py`: 正常CSV取込、levelエラー行スキップ、重複行の非重複
- `test_views.py`: 回答保存（unique制約でupdateになる）、finalize後は編集不可、他案件のアセスメント404
- コミット例: `feat: TPIアセスメント(成熟度マトリクス+改善提言)を追加`

## Done

1. マスターを画面かCSVで数件投入→アセスメント作成→回答→マトリクスの色と到達レベルが仕様通り→確定→（LLM環境ありなら）改善提言が生成される
2. `pytest` 全パス／DESIGN.mdのPhase 5を実装済みに更新／コミット＆push
