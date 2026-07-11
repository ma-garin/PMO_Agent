# 実装ハンドブック（全フェーズ共通）

このリポジトリで実装作業を行うエージェント/開発者向けの前提知識。**フェーズ仕様書（docs/phases/）を実装する前に必ず全部読むこと。**

## 1. プロダクト概要

第三者検証会社向けのPMO支援システム（単一会社の社内ツール、ADR-0001）。JIRA/Redmineからチケットを読み取り専用で同期し、品質分析・診断・報告・相談をAIで支援する。用語は [../CONTEXT.md](../CONTEXT.md) に従うこと（例:「プロジェクト」ではなく「案件」、「バグ」ではなく「欠陥」）。

## 2. 技術スタックと環境

| 項目 | 内容 |
|---|---|
| 言語/FW | Python 3.13 / Django 6.0.7 |
| DB | PostgreSQL 17（Homebrew, `brew services start postgresql@17`）+ pgvector 0.8.5 |
| 非同期ジョブ | Procrastinate 3.9.0（PostgreSQLネイティブ。Redis/Celeryは使わない、ADR-0003） |
| テスト | pytest / pytest-django / pytest-cov / responses |
| venv | リポジトリ直下 `./venv` |
| 環境変数 | `.env`（gitignore対象）。読み込みは `config/settings.py` の `load_dotenv` |

**制約: Dockerおよび商用契約が必要な外部サービスは使用禁止**（ユーザー指示）。新しいpipパッケージはOSS・無償のもののみ。

### コマンド集

```bash
source venv/bin/activate                 # 常に最初に実行
python manage.py runserver 127.0.0.1:8765 # 開発サーバー
python manage.py check                   # 設定検証
python manage.py makemigrations && python manage.py migrate
pytest                                   # 全テスト(カバレッジ付き, pytest.iniで設定済み)
pytest analytics/ -q                     # アプリ単位
```

### ログインアカウント（ローカル開発用）

- `yuki` / `pmoagent-demo1`（一般・デモデータ紐付き）
- `admin` / `password`（スーパーユーザー、/admin/ 可）
- デモ案件「基幹システム刷新」に欠陥9件・通知・ODC分類1件が投入済み

## 3. アプリ構成マップ

| アプリ | 責務 | 主要ファイル |
|---|---|---|
| `accounts` | 認証・プロフィール・パスワード変更 | urls.py(login/logout/profile/password) |
| `engagements` | 案件（旧projects）。LLMプロバイダ設定・分析設定を保持 | models.Engagement |
| `tickets` | チケット同期(JIRA/Redmine)・停滞検知・通知 | adapters/, services.py, tasks.py |
| `analytics` | 品質分析（欠陥メトリクス・ODC分類） | services.py, models.OdcClassification |
| `dashboard` | ホーム画面 | views.home |
| `config` | settings/urls | |

Phase 3以降で新設予定: `llm` `copilot` `reports` `knowledge` `tpi`（各フェーズ仕様書参照）。

## 4. 既存モデル一覧（フィールドを推測せずここを見る）

### engagements.Engagement
`name` `description` `status`(active/on_hold/completed) `progress`(int) `members`(M2M User) `owner`(FK User) `llm_provider`(openai/claude/ollama, 既定ollama) `defect_ticket_types`(JSON list) `size_metric_name`(str) `size_metric_value`(Decimal null) `updated_at` `created_at`

### engagements.ActivityLog
`engagement` `actor`(FK User) `message` `created_at`

### tickets.TicketSource
`engagement` `kind`(jira/redmine) `name` `base_url` `project_key` `username` `api_token` `is_active` `last_synced_at`

### tickets.Ticket
`source`(FK TicketSource) `external_id` `external_url` `summary` `description` `status`(元システム生文字列) `is_done`(bool) `priority` `ticket_type`(生文字列) `assignee_name` `reporter_name` `due_date`(Date) `source_created_at` `source_updated_at` `closed_at`(DateTime null) `raw_payload`(JSON) `synced_at`。unique(source, external_id)。`engagement`プロパティあり

### tickets.SyncRun / StagnationRule / Notification
SyncRun: `source` `status`(running/success/failed) `tickets_synced` `error_message` `started_at` `finished_at`
StagnationRule: `engagement`(O2O) `stale_after_days`(既定5) `notify_on_overdue`
Notification: `engagement` `ticket` `kind`(stagnant/overdue) `message` `is_read`。unique(ticket, kind)

### analytics.OdcClassification
`ticket`(O2O) `defect_type` `trigger` `activity` `impact`（各TextChoices、blank可） `source`(field/llm/manual) `status`(pending/confirmed) `classified_by`(FK User null) 。choicesの値は `analytics/models.py` を参照

## 5. 既存サービス関数（再利用すること。再実装禁止）

```python
# tickets/services.py
sync_ticket_source(source: TicketSource) -> SyncRun
sync_engagement(engagement) -> list[SyncRun]
detect_stagnant_tickets(engagement) -> list[Notification]

# tickets/tasks.py (Procrastinateタスク)
sync_engagement_sources(engagement_id)
sync_and_detect_engagement(engagement_id)
sync_and_detect_all_engagements(timestamp)  # @app.periodic(cron="0 * * * *")

# analytics/services.py
defect_type_values(engagement) -> list[str]
get_defects(engagement) -> QuerySet[Ticket]      # 欠陥のみ(種別マッピング適用)
summarize_defects(engagement) -> dict            # total/open/closed/overdue/density/avg_open_age_days
convergence_series(engagement) -> list[dict]     # 週次累積 {label, opened, closed}
convergence_svg_points(series) -> dict           # SVG polyline座標
odc_distribution(engagement) -> dict             # 確定済みODCの軸別分布
```

## 6. 画面実装の規約

### セッションと案件コンテキスト
- 選択中の案件は `request.session["current_engagement_id"]`（と `current_engagement_name`）
- 各アプリのviews.pyに `_current_engagement(request)` ヘルパーを置くのが既存パターン（tickets/views.py参照）。案件未選択なら `redirect("engagements:select")`

### テンプレート構造
アプリ画面は必ずこの骨格（`templates/analytics/analysis.html` を雛形にする）:
```html
{% extends "base.html" %}
{% block extra_css %}<link ... app_shell.css> <link ... dashboard.css> （必要なら専用css）{% endblock %}
{% block body %}
<div class="app-shell">
  {% include "partials/sidebar.html" %}
  <div style="flex:1; display:flex; flex-direction:column; min-width:0;">
    {% include "partials/header.html" %}
    <main class="app-main"> ... </main>
  </div>
</div>
{% endblock %}
```
- サイドバーの現在地は context の `nav_active` で制御。既存値: `home` `tickets` `analytics` `settings`。新画面は sidebar.html にリンクを追加し新しい nav_active 値を定義
- 設定系画面は `{% include "partials/settings_tabs.html" %}` を使い `settings_tab` を渡す（既存値: profile/password/llm/tickets）
- フラッシュメッセージ: `{% if messages %}{% for message in messages %}<div class="alert">{{ message }}</div>{% endfor %}{% endif %}`
- CSSは既存トークン（`--primary` `--surface` `--border` `--ink` `--ink-2` 等）だけを使う。ライト/ダーク両対応は変数側で担保済み。**色の直書き禁止**
- 既存部品: `.card` `.panel` `.stat-grid`/`.stat-card` `.btn .btn-primary/.btn-secondary` `.form-input/.form-select/.form-group/.form-label` `.tabs` `.badge` `.empty-note`

### URL規約
- 各アプリに `urls.py` + `app_name`。config/urls.py に `path("<app>/", include("<app>.urls"))` を追加
- 名前空間例: `analytics:analysis` `tickets:list` `engagements:select` `accounts:profile`

## 7. コーディング規約（抜粋・必須）

- 関数シグネチャに型ヒント。モデルのverbose_nameは日本語
- コメントは「非自明なWHY」のみ。何をしているかの説明コメントは書かない
- ファイルは800行以内・関数50行以内目安。ロジックはviews直書きせず `services.py` へ
- ミューテーション回避（frozen dataclass等）。既存 `tickets/adapters/base.py` の `NormalizedTicket` がお手本
- ユーザー向け文言・コミットメッセージは日本語。コミットは `feat:` `fix:` `test:` `docs:` プレフィックス
- 秘密情報（APIキー等）は必ず環境変数。ハードコード禁止。`.env.example` にキー名を追記する

## 8. 既知の落とし穴（過去に踏んだもの）

1. **`Q(owner=user) | Q(members=user)` はJOINで重複行を返す** → 必ず `.distinct()` を付ける（MultipleObjectsReturnedで500になる）
2. **`<tr>`の中に`<form>`を書かない**（不正HTML）→ ボタン側のtdに`<form id="x">`を置き、他セルの入力には `form="x"` 属性を付ける（analysis.htmlの実例参照）
3. DateFieldに `|date:"H:i"` など時刻フォーマットを使うとTypeError → 日付は `n/j` 等
4. ログイン画面は常にライトテーマ固定（login.css内で変数を再定義済み）。壊さないこと
5. テンプレートで `{{ list|last.attr }}` は不正 → `{% with x=list|last %}{{ x.attr }}{% endwith %}`
6. zshでは `pip install "psycopg[binary]"` のようにブラケットをクォート
7. 通知ヘッダーは context processor `tickets.context_processors.notifications` が全画面に `header_notifications` / `header_unread_count` を供給している。画面側で用意不要

## 9. Definition of Done（全タスク共通）

1. `python manage.py check` エラーなし
2. `pytest` 全件パス（既存62件を壊さない）。新ロジックには単体テストを追加（DBを使うものは `@pytest.mark.django_db`、HTTPは `responses` か `unittest.mock`）
3. 対象画面をブラウザ（Playwright MCPまたは手動）で開き、正常系を1回通す
4. `requirements.txt`（本番依存）/`requirements-dev.txt`（開発依存）をバージョン固定で更新
5. 日本語コミット→ `git push origin main`
