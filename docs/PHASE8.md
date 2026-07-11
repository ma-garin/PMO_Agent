# Phase 8 実装仕様: 改善バックログの実装

前提: [HANDBOOK.md](HANDBOOK.md) 読了。発生源は [PHASE6.md](PHASE6.md) 第2部のバックログ（B1〜B20）。**B18（品質ゲート）はPhase 7に吸収済みのため対象外**。

依存関係があるため4バッチに分けて順に実装する。各バッチ完了ごとにテスト→コミット→push。

| バッチ | テーマ | 前提フェーズ |
|---|---|---|
| A | セキュリティ・基盤 | なし（今すぐ可能） |
| B | 画面・導線 | なし（B2はPhase 2済でOK） |
| C | 自動化・連携 | Phase 3（LLM）、B8/B19は Phase 6（管理画面） |
| D | 管理・分析 | Phase 3（B9/B10）、Phase 6（管理画面） |

---

## バッチA: セキュリティ・基盤

### A-1. APIトークンの暗号化保存（B1）

- 依存追加: `pip install cryptography`（requirements.txtへ）
- `.env` / `.env.example` に `FIELD_ENCRYPTION_KEY=`（生成方法をコメントで書く: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`）
- 新規 `config/crypto.py`:
```python
import os
from cryptography.fernet import Fernet, InvalidToken

def _fernet() -> Fernet:
    key = os.environ.get("FIELD_ENCRYPTION_KEY")
    if not key:
        raise RuntimeError("FIELD_ENCRYPTION_KEYが未設定です。.envに追加してください")
    return Fernet(key.encode())

def encrypt(value: str) -> str:   # 空文字はそのまま返す
def decrypt(value: str) -> str:   # 復号失敗(InvalidToken)は空文字を返しログ出力
```
- `TicketSource` 変更: DB列を `_api_token_encrypted = models.TextField(blank=True, db_column="api_token_encrypted")` にし、`api_token` はproperty（getterでdecrypt、setterでencrypt）。フォーム(`TicketSourceForm`)はfieldsから`api_token`を外し、明示の`CharField(required=False)`＋save()オーバーライドで「入力があった時だけ更新」
- マイグレーション3段: ①新列追加 ②データ移行（RunPythonで平文→暗号化。**reverseも書く**）③旧列削除
- テスト: encrypt/decryptラウンドトリップ、鍵未設定でRuntimeError、復号失敗で空文字、フォーム空入力で既存値維持
- **注意**: 既存の同期テスト（adapterがsource.api_tokenを読む）が壊れないこと（propertyなので透過のはず）

### A-2. セッション・ログイン保護（B16）

- `config/settings.py`: `SESSION_COOKIE_AGE = 8 * 60 * 60`、`SESSION_SAVE_EVERY_REQUEST = True`、`MinimumLengthValidator` のオプションを `{"min_length": 12}` に変更
- 依存追加: `django-axes`（OSS）。INSTALLED_APPS・AUTHENTICATION_BACKENDS・MIDDLEWAREを公式手順どおり設定。`AXES_FAILURE_LIMIT = 5`、`AXES_COOLOFF_TIME = 0.5`（30分）
- テスト: 5回失敗でロック→正しいパスワードでも拒否、クールオフはモック時間で確認（axes標準のテストユーティリティ利用可）
- 既存ユーザーのパスワードが12字未満でもログインは可能（バリデータは変更時のみ効く）ことを確認

### A-3. デモデータ生成コマンド（B14）

- `accounts/management/commands/seed_demo.py`: 冪等（何度実行しても重複しない）に以下を作成: ユーザー2名（yuki一般/admin管理者）、案件3件、TicketSource1件、チケット11件（欠陥9件・クローズ日時付き）、ODC確定1件、通知3件。**現在shell手作業で入れているデモデータと同内容**をコード化する
- テスト: 2回実行して件数が変わらないこと

### A-4. テーマ設定の永続化（B13）

- `accounts/models.py` に `UserPreference(user O2O, theme CharField choices auto/light/dark, default "auto")`
- POST `/accounts/preference/theme/`（`accounts:set_theme`）: theme値を保存
- `base.html`: `<html data-theme="{{ user.preference.theme }}">` をサーバー側で出す（auto時は属性なし）。theme.jsはトグル時にfetchでPOSTしつつlocalStorageも維持（未ログイン画面用）
- context processorは作らずテンプレートで `user.preference.theme` を参照（O2Oが無い場合に備え `{% firstof %}` で安全に）

### A-5. バックアップ手順書（B20）

- `docs/OPERATIONS.md` 新規: `pg_dump`の日次バックアップスクリプト例（launchd plist例付き）、リストア手順、`media/`のバックアップ、`FIELD_ENCRYPTION_KEY`の別保管の注意（**鍵を失うと全トークン復号不能**）

---

## バッチB: 画面・導線

### B-1. ポートフォリオダッシュボード（B2）

- `engagements:select`（案件選択画面）を拡張: 各カードに欠陥未クローズ数・期限超過数・未読通知数・最終同期日時を表示。管理者(is_staff)は非参加案件も一覧に含める（「参加していません」バッジ付き）
- **N+1禁止**: `Ticket.objects.filter(source__engagement__in=ids).values("source__engagement").annotate(...)` 形式の集計クエリ3本で辞書を作り、テンプレートに渡す
- テスト: 集計値の正しさ、一般ユーザーに他案件が見えない、管理者には見える

### B-2. グローバル検索（B4）

- GET `/search/?q=`（`search:results`、新規searchアプリ or dashboardに追加→**dashboardアプリに追加**でよい）
- 検索対象と表示グループ: チケット（summary/external_id、現在案件のみ）／案件（name、参加案件）／テスト計画・レポート・ナレッジ文書（タイトル、実装済みフェーズの分だけ。**モデルの存在をappsレジストリで判定して段階対応**: `django.apps.apps.is_installed("knowledge")` 等）
- `icontains` で各10件まで。結果ページはグループ見出し＋リンクリスト
- header.htmlの検索ボックスを実フォーム化（`<form action="/search/" method="get">`）。`⌘K/Ctrl+K` でフォーカスする5行のJSをtheme.js末尾に追加
- テスト: 案件スコープ絞り込み、クエリ空のとき空状態表示

### B-3. CSVエクスポート（B11）

- GET `/tickets/export.csv`（現在のタブ・検索条件を反映）、`/analytics/export/odc.csv`（確定済みODC）、`/testmgmt/progress/export.csv`
- 実装: `csv.writer`＋`StreamingHttpResponse`、先頭にBOM(`﻿`)。ヘッダは日本語
- 各一覧画面に「CSVエクスポート」ボタン
- テスト: レスポンスのContent-Type/BOM/行数

### B-4. カレンダー画面（B6）

- GET `/calendar/?year=&month=`（dashboardアプリに追加、nav_active: `calendar`、サイドバーのダミーを差し替え）
- `dashboard/services.py::month_grid(engagement, year, month) -> list[list[dict]]`（月曜始まりの週配列。各日: date/当月フラグ/チケット期限リスト/ゲート判定日）
- 表示: `<table>`グリッド。期限チケットはdangerドット＋タイトル省略表示、日クリックで `/tickets/?q=` に飛ばす程度でよい
- テスト: month_gridの境界（月初が日曜/2月/12月→1月遷移）

### B-5. メンバー画面（B7）

- 新規モデル `engagements.MemberAlias(engagement, user FK, external_name CharField)`: チケットの `assignee_name`（元システムの表示名）とシステムユーザーの対応表。unique(engagement, external_name)
- GET `/members/`（engagementsアプリ、nav_active: `members`）: 案件メンバー一覧＋各自の担当チケット数・未クローズ数・停滞数（assignee_name in その人のalias群で集計）。エイリアス追加/削除フォーム（管理者のみ）
- テスト: エイリアス経由の集計、未マッピングの担当者名一覧が「未対応付け」として出る

### B-6. レスポンシブ・サイドバー折りたたみ（B15）

- サイドバー右上にシェブロンボタン→アイコンのみ表示（幅220px→64px、`.sidebar.collapsed`クラス。ラベルは`display:none`、案件名ブロックはアイコン化）。状態はlocalStorage（`pmo-sidebar`）
- `@media (max-width: 900px)`: サイドバーを初期折りたたみ
- 参考デザイン（galleryinline.htmlの折りたたみ状態）に寄せる。JSはtheme.jsに追記（依存追加なし）

---

## バッチC: 自動化・連携（Phase 3完了後）

### C-1. 週次サマリー自動生成（B3）

- 新規モデル `analytics.WeeklyDigest(engagement, week_start DateField, body TextField, metrics JSONField, created_at)`。unique(engagement, week_start)
- Procrastinate periodic `@app.periodic(cron="0 9 * * 1")` `generate_weekly_digests`: 全アクティブ案件について、先週分の増減（新規/クローズ欠陥数、新規通知数、進捗率変化）をmetricsに集計し、`run_completion(purpose="weekly_digest")` で3〜5行の日本語サマリーを生成（LlmErrorなら定型文にフォールバック）
- ダッシュボードに「今週のハイライト」パネル（最新Digest表示）
- テスト: 集計ロジック（週境界）、冪等（同週2回で上書き）、LLM失敗時フォールバック

### C-2. チケット履歴取込と再オープン率（B5）

- 新規モデル `tickets.TicketStatusTransition(ticket FK, from_status, to_status, occurred_at DateTimeField)`。unique(ticket, occurred_at, to_status)
- アダプタ拡張（**読み取り専用は維持**）:
  - JIRA: `GET /rest/api/3/issue/{key}/changelog`（`startAt`ページング）から `field == "status"` の履歴
  - Redmine: `GET /issues/{id}.json?include=journals` から `details[].name == "status_id"` の履歴
  - **API負荷対策**: 履歴取得は「前回同期以降に更新されたチケット」のみ。`sync_ticket_source`に`fetch_history: bool = True`引数を追加
- 再オープン判定: doneステータス→not doneステータスへの遷移。`analytics/services.py` に `reopen_stats(engagement) -> dict`（reopened_count, closed_count, reopen_rate）
- 分析画面にstatカード「再オープン率」を追加
- テスト: responsesでchangelog/journalsをモックし遷移が保存される、再オープン率の計算（0除算含む）

### C-3. 通知の外部連携（B8）

- 新規モデル `tickets.NotificationChannel(engagement, kind email/slack_webhook, target CharField, is_active)`。管理者のみ設定可（管理画面 or 接続設定タブ）
- 送信はProcrastinateタスク `deliver_notification(notification_id)`。停滞検知で新規Notificationが作られた時にdefer
- メール: Django標準 `send_mail`（SMTP設定は環境変数 `EMAIL_HOST` 等、`.env.example`に追記）。Slack: Incoming WebhookへのPOST（requests）
- **文面はテンプレート固定**（`「{summary}」が{n}日以上更新されていません` 等）。LLM生成文の自動送信はしない
- テスト: チャネル無効時に送られない、Slack POSTのpayload（responsesでモック）

### C-4. Copilot能動要約（B19）

- 停滞検知後、未読通知が10件以上になった案件に対し、Copilotスレッド「(自動) 状況サマリー YYYY-MM-DD」を自動作成（1日1回まで。同日既存ならスキップ）し、通知一覧の要約と推奨アクションをASSISTANTメッセージとして投稿
- 実装: `copilot/services.py::create_auto_summary(engagement)` を `sync_and_detect_engagement` の末尾から条件付き呼び出し
- テスト: 閾値未満で作られない、同日重複防止

---

## バッチD: 管理・分析（Phase 6完了後）

### D-1. LLM利用状況ダッシュボード（B9）

- `/manage/llm-usage/`: 当月・先月の呼び出し回数/合計文字数/失敗率を、案件別×プロバイダ別×用途別にテーブル表示。機密案件（provider=ollama指定）がクラウドを呼んでいたら警告行表示
- `LlmCallLog`への集計クエリのみ（新モデル不要）。テスト: 集計値・警告条件

### D-2. レポートテンプレート管理（B10）

- 新規モデル `reports.ReportTemplate(name, system_prompt TextField, is_default Boolean)`。管理者が管理画面でCRUD
- `reports:create` にテンプレート選択を追加し、generate_draftのsystemを差し替え
- マイグレーションで既定テンプレート1件（Phase 3の固定章立てと同内容）をdata migrationで投入
- テスト: 既定選択、テンプレ差し替えがpromptに反映

### D-3. 監査ログ（B12）

- 新規アプリ `audit`: `AuditLog(actor FK, action CharField, target_type CharField, target_id int, detail CharField, created_at)`＋`audit.services.record(actor, action, target, detail="")`
- 記録ポイント（明示呼び出し。シグナル不使用）: トークン登録/更新/削除、案件作成/編集/メンバー変更、ユーザー作成/権限変更/無効化、ODC確定、レポート承認、ゲート判定、テスト計画承認
- `/manage/audit/`: ページネーション付き一覧（actor/action/期間フィルタ）
- テスト: 各記録ポイントで1行増える、一般ユーザーは閲覧不可

### D-4. ODC時系列・案件間比較（B17）

- 分析画面に「月次推移」タブ: 確定済みODCの `updated_at` 月別×欠陥タイプの積み上げ棒（SVG。バーはrectで描画、convergence実装を参考）
- 管理者向け `/manage/benchmark/`: 全案件のODC分布・再オープン率・平均滞留を**案件名を「案件A/B/C…」に匿名化**して比較表示（機密のため実名は出さない）
- テスト: 月別集計、匿名化ラベルの安定性（同一リクエスト内で一貫）

---

## Done（Phase 8全体）

1. バッチA〜D全項目の個別テストがパスし、既存テストも全パス
2. トークンがDB上で暗号化されていることをpsqlで目視確認（平文が残っていない）
3. デモデータコマンドから新規環境を立ち上げ、主要画面が動くこと
4. DESIGN.mdのPhase 8を実装済みに更新、PHASE6.md第2部の各項目に「Phase 8で実装済み」注記
5. コミット＆push
