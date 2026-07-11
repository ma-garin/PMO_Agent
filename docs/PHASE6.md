# Phase 6 実装仕様: 管理者ロール分離 ＋ 改善バックログ

前提: [HANDBOOK.md](HANDBOOK.md) を読了していること。第1部は確定仕様（このまま実装する）、第2部は優先度付きの改善アイデア集（着手時に個別にグリル/設計する）。

---

# 第1部: 管理者ロール分離（確定仕様）

## 要件

- ユーザーを**管理者**と**一般ユーザー**に分ける
- 管理者だけができること: ①案件の管理（作成・編集・メンバー割当・アーカイブ） ②トークン管理（JIRA/RedmineのAPIトークン等の接続情報の登録・更新・削除） ③ユーザー管理 ④LLM呼び出しログの閲覧
- 一般ユーザー: 参加している案件の利用（ダッシュボード・チケット・分析・Copilot・レポート閲覧/作成）のみ。案件の新規作成は不可になる（**現状は誰でも作成できるので挙動変更**）

## 設計判断（このまま実装する）

| 論点 | 決定 | 理由 |
|---|---|---|
| ロールの持ち方 | Django標準の `User.is_staff` を「管理者」として使う。新モデルは作らない | マイグレーション不要・/admin/との整合・小規模社内ツールに十分 |
| 権限チェック | 自作デコレータ `admin_required`（未ログイン→ログインへ、権限なし→メッセージ付きでダッシュボードへredirect。403画面は出さない） | 社内ツールとして親切な挙動 |
| トークンの表示 | 画面には**末尾4桁のみ**表示（`****abcd`）。入力欄は常に空で、入力があった時だけ更新 | 平文の再表示を防ぐ |
| 既存ユーザー | `admin`は管理者(既にis_staff=True)、`yuki`は一般のまま | |

## Step 1: 権限デコレータ（accounts/decorators.py 新規）

```python
from functools import wraps
from django.contrib import messages
from django.shortcuts import redirect

def admin_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        if not request.user.is_staff:
            messages.error(request, "この操作には管理者権限が必要です。")
            return redirect("dashboard:home")
        return view_func(request, *args, **kwargs)
    return _wrapped
```

## Step 2: 既存画面への適用（挙動変更）

1. `engagements/views.py`
   - `EngagementCreateView` に管理者チェックを追加（CBVなので `UserPassesTestMixin` を使い `test_func = lambda self: self.request.user.is_staff`、`handle_no_permission` でメッセージ＋ダッシュボードへredirect）
   - 案件選択画面（select.html）: 「＋新規案件」ボタンと`new-project-card`を `{% if user.is_staff %}` で囲む
2. `tickets/views.py`
   - `source_settings` と `sync_source_now` はそのまま（同期実行は一般ユーザーも可）だが、**接続の追加フォームとトークン項目は管理者のみ**: source_settings のPOST処理冒頭に `if not request.user.is_staff: messages.error(...); return redirect(...)` を追加し、テンプレートの追加フォームを `{% if user.is_staff %}` で囲む。一般ユーザーには登録済み接続の一覧と「今すぐ同期」だけ見せる
3. `templates/tickets/source_settings.html`: 登録済み接続の `api_token` は表示しない（現状も表示していないことを確認）。接続情報の表示に「トークン: ****{{ source.api_token|slice:"-4:" }}」を追加（管理者のみ）

## Step 3: 管理セクション（adminpanelアプリ新規）

Djangoの/admin/はそのまま残すが、業務UIとして管理画面を作る。

```bash
python manage.py startapp adminpanel
```
INSTALLED_APPS登録、`config/urls.py` に `path("manage/", include("adminpanel.urls"))`。**全ビューに `admin_required`**。

| URL | name | 画面内容 |
|---|---|---|
| GET `/manage/` | `adminpanel:home` | 管理トップ: ユーザー数・案件数・接続数・直近LLM呼び出し数のカード＋各管理画面へのリンク |
| GET/POST `/manage/users/` | `adminpanel:users` | ユーザー一覧（ユーザー名/氏名/メール/管理者か/有効か/最終ログイン）。新規作成フォーム（ユーザー名・メール・初期パスワード・管理者フラグ）。各行に「管理者にする/外す」「無効化/有効化」ボタン（POST）。**自分自身の管理者権限は外せない**（ガード必須） |
| GET/POST `/manage/engagements/` | `adminpanel:engagements` | 全案件一覧（メンバー数・状態・LLMプロバイダ）。編集リンク・アーカイブ（status=completedへ変更）ボタン |
| GET/POST `/manage/engagements/<pk>/` | `adminpanel:engagement_edit` | 案件の編集（EngagementFormを再利用）＋メンバー割当（全ユーザーのチェックボックスリスト、membersをset()で更新） |
| GET/POST `/manage/tokens/` | `adminpanel:tokens` | 全案件のTicketSource一覧（案件名・種別・接続先・トークン末尾4桁・最終同期・有効フラグ）。トークン更新フォーム（新しい値を入れた時だけ更新）、削除ボタン（確認付き）、有効/無効切替 |
| GET `/manage/llm-logs/` | `adminpanel:llm_logs` | LlmCallLog一覧（ページネーション20件、案件/プロバイダ/用途/状態/所要時間/日時）。Phase 3未実装の間はこの画面だけ後回しにしてよい |

実装メモ:
- ビューはFBVで素朴に。フォームは `adminpanel/forms.py` に `UserCreateForm`（`User`のModelForm＋`password`はCharField、保存時 `set_password`）、`TokenUpdateForm` を定義
- テンプレートは既存骨格（sidebar+header）を使い、`nav_active: "manage"`。sidebar.htmlに管理者のみ表示のリンクを追加:
  ```html
  {% if user.is_staff %}
  <div class="sidebar-section-label">管理</div>
  <a href="{% url 'adminpanel:home' %}" class="nav-item{% if nav_active == 'manage' %} active{% endif %}">&#128737; 管理</a>
  {% endif %}
  ```
- ユーザー無効化は `is_active=False`（削除はしない。監査のため）

## Step 4: テスト（adminpanel/tests/ ＋ 既存アプリのテスト追加）

- 一般ユーザーで `/manage/` 系すべて→ダッシュボードへredirect＋エラーメッセージ
- 管理者でユーザー作成→ログインできる／無効化→ログインできない
- 自分自身の管理者権限剥奪が拒否される
- 一般ユーザーで案件作成POST→拒否。管理者→作成できる
- 一般ユーザーでTicketSource追加POST→拒否。同期実行は可能
- トークン更新: 空文字POSTでは既存値が変わらない／新値POSTで更新される
- コミット例: `feat: 管理者ロール分離と管理画面(ユーザー/案件/トークン)を追加`

## Done

1. `yuki`（一般）でログイン: 「＋新規案件」が見えない・/manage/に入れない・チケット同期は使える
2. `admin`でログイン: 管理メニューからユーザー作成・案件編集・トークン更新ができる
3. `pytest`全パス、DESIGN.md更新、コミット＆push

---

# 第2部: 改善バックログ（アイデア集・優先度付き）

着手時はこの見出しをグリルセッションの入力にすること。各項目: 概要→価値→実装メモ。

## 優先度: 高（次の1〜2フェーズで検討すべき）

### 6-B1. APIトークンの暗号化保存【セキュリティ】
- 概要: 現状 `TicketSource.api_token` はDBに平文保存。`cryptography`のFernetで暗号化し、鍵は環境変数 `FIELD_ENCRYPTION_KEY` から読む
- 価値: DBダンプ流出時に顧客環境のトークンが漏れない。検証会社として顧客接続情報の保護は必須級
- 実装メモ: モデルのsave/取得をプロパティでラップ（`_api_token_encrypted`列＋`api_token`プロパティ）。既存データのマイグレーション（平文→暗号化）を忘れない

### 6-B2. ポートフォリオダッシュボード（全案件横断ビュー）
- 概要: 案件選択の前に、担当全案件の状態（進捗・期限超過数・停滞数・直近同期）を1画面で俯瞰。管理者は全社案件を見られる
- 価値: PMOは複数案件を掛け持ちするのが常態。案件に「入らないと分からない」現状はPMOの巡回コストが高い
- 実装メモ: `engagements:select` を拡張するのが最短。カードに `summarize_defects` のサマリー数値を追加（N+1に注意、集計は一括で）

### 6-B3. 週次サマリーの自動生成（Procrastinate定期タスク）
- 概要: 毎週月曜朝に案件ごとの週次品質サマリー（新規/クローズ欠陥、停滞、ODC変化）を自動生成し、ダッシュボードに「今週のハイライト」として表示。Phase 3後はLLMで文章化
- 価値: 「追い回しからの解放」の次の一手＝報告準備の自動化
- 実装メモ: `@app.periodic(cron="0 9 * * 1")`。結果は新モデル `WeeklyDigest(engagement, week_start, body, metrics_json)`

### 6-B4. グローバル検索（⌘K）の実装
- 概要: ヘッダーの検索ボックスは現在ダミー。チケット（summary/external_id）・案件・ナレッジ文書を横断検索するモーダルを実装
- 価値: 画面遷移の起点になる。ダミーUIを放置するとユーザーの信頼を損なう
- 実装メモ: `/search/?q=` のJSONエンドポイント＋素朴なJSモーダル（依存追加なし）。PostgreSQLの `SearchVector` で日本語は限界があるため、まずは `icontains` で十分

### 6-B5. チケット履歴の取込と再オープン率
- 概要: JIRA changelog / Redmine journals を同期し、ステータス遷移履歴を保存。再オープン率・ステータス滞留時間の実測を可能にする（Phase 2で除外した残論点）
- 価値: 「修正品質」の指標が取れる。ODCと組み合わせると再発分析ができる
- 実装メモ: 新モデル `TicketStatusTransition(ticket, from_status, to_status, occurred_at)`。API呼び出し回数が増えるため同期は増分方式（updated以降のみ）に改修してから着手

## 優先度: 中

### 6-B6. カレンダー画面の実装
- 概要: サイドバーのダミー「カレンダー」を実装。チケット期限・欠陥クローズ予定・アセスメント予定を月表示
- 実装メモ: JSライブラリなしで `<table>` による月グリッド生成（services側で週配列を組む）

### 6-B7. メンバー画面の実装
- 概要: ダミー「メンバー」を実装。案件メンバー一覧＋担当チケット数・停滞数（assignee_nameとの突合はマッピング設定で）
- 実装メモ: チケットの `assignee_name` は元システムの表示名なので、User⇔表示名の対応表 `MemberAlias(engagement, user, external_name)` が必要

### 6-B8. 通知の外部連携（メール / Slack Webhook）
- 概要: 停滞・期限超過通知をメールまたはSlack Incoming Webhookへ転送（案件単位でON/OFF・宛先設定）
- 価値: システムを開いていない時にも督促が届く
- 実装メモ: 送信は必ずProcrastinateタスク経由。Webhook URLはトークン管理画面（第1部）で管理。**自動送信の文面はテンプレート固定とし、LLM生成文の無承認送信はしない**（誤送信リスク）

### 6-B9. LLMコスト・利用状況ダッシュボード
- 概要: LlmCallLogを集計し、案件別・用途別・プロバイダ別の呼び出し回数/文字量/失敗率を管理画面に表示
- 価値: クラウドLLMのコスト統制と、機密案件がOllamaを使っているかの監査
- 実装メモ: 第1部の `/manage/llm-logs/` の拡張。トークン数課金の概算は文字数×係数で近似

### 6-B10. レポートテンプレート管理と定期ドラフト
- 概要: 報告書の章立てをテンプレートとしてDB管理（案件ごとに選択）。月次で自動ドラフト生成
- 実装メモ: `ReportTemplate(name, system_prompt, sections_json)`。Phase 3のgenerate_draftのsystemを差し替える形

### 6-B11. CSV/Excelエクスポート
- 概要: チケット一覧・ODC分類・メトリクスをCSVダウンロード（Excelはまず不要、CSVで開ける）
- 実装メモ: `csv`標準ライブラリのStreamingHttpResponse。BOM付きUTF-8（Excel文字化け対策）

### 6-B12. 監査ログ（操作履歴）
- 概要: 誰がいつ「トークン更新・案件作成・ODC確定・報告書承認」をしたかを記録し管理画面で閲覧
- 価値: 検証会社の内部統制・顧客監査対応
- 実装メモ: `AuditLog(actor, action, target_type, target_id, detail, created_at)`＋各ビューでの明示記録（シグナルより明示が読みやすい）

## 優先度: 低（余裕があれば）

### 6-B13. テーマ設定の永続化
- 概要: ライト/ダーク選択をlocalStorageだけでなくユーザー設定（DB）に保存し、端末をまたいで維持
### 6-B14. デモデータ生成コマンド
- 概要: `python manage.py seed_demo` で案件・チケット・ODC・通知を一括生成（現在はshellスクリプト手作業）。新環境の立ち上げとE2Eテストが楽になる
### 6-B15. レスポンシブ改善（タブレット対応）
- 概要: サイドバーの折りたたみ（参考デザインの折りたたみ状態を実装）と1000px以下のレイアウト調整
### 6-B16. セッション/セキュリティ強化
- 概要: セッションタイムアウト（8時間）、ログイン失敗ロック（django-axes）、パスワードポリシー強化
### 6-B17. ODC分析の時系列・案件間比較
- 概要: ODC分布の月次推移、匿名化した案件間ベンチマーク（自社ナレッジとしての蓄積）
### 6-B18. 品質ゲート（リリース判定チェックリスト）
- 概要: 「未クローズ致命欠陥0件」「収束率90%以上」等の判定条件を案件に設定し、ダッシュボードに合否表示。検証会社の出荷判定業務を直接支援
### 6-B19. Copilotの能動要約
- 概要: 停滞通知が閾値を超えたらCopilotが状況要約スレッドを自動作成（本人が開いた時に見える。push通知はしない）
### 6-B20. バックアップ手順の整備
- 概要: `pg_dump` の定期実行スクリプトとリストア手順書（docs/OPERATIONS.md）

---

## ロードマップへの反映

- 第1部（管理者ロール分離）を「Phase 6」として実装する
- 第2部は各フェーズの隙間に優先度順で差し込む。着手時に必ずグリルセッションで要件を確定してから実装すること
