# PMO Agent 作り込み計画 2026-07-12

> 世界最高水準のエンジニアリング、Webデザイン、CSS実装の3視点によるコードベース静的監査。優先順位は全チーム横断の1〜30。各チーム10件ずつ。

## 監査スコープ

- Djangoアプリ: 16（`accounts`〜`autopilot`）
- テストモジュール: 63
- HTMLテンプレート: 48
- CSS: 12ファイル
- UI負債の代表値: 43テンプレートに152件のインラインstyle
- 参照資料: `CONTEXT.md`、`docs/DESIGN.md`、`docs/HANDBOOK.md`、`docs/adr/0001`〜`0003`
- 実施内容: ファイル構成、主要model/view/service/adapter/task、共通テンプレート、CSS/JS、テスト、運用文書の静的監査
- 未実施: DB接続を伴うテスト、ビルド、ブラウザ実機確認、負荷試験

## 進め方

| Phase | 優先順位 | 目的 | 完了判定 |
|---|---:|---|---|
| A | 1〜3 | 情報漏えいと二重反映を止める | 権限・外部送信・並行承認テストが通る |
| B | 4〜9 | 同期・ジョブ・通知を回復可能にする | 再試行しても重複せず、失敗が残る |
| C | 10〜17 | 操作性と品質ゲートを上げる | 主要業務が安全に完遂できる |
| D | 18〜26 | 情報設計・可視化・状態設計を磨く | PC/タブレット/モバイルで業務導線が通る |
| E | 27〜30 | CSS基盤を仕上げる | 視覚回帰とアクセシビリティ基準が固定される |

## 優先順位 1〜30

### 1. 案件コンテキストを1つの深いmoduleへ集約

**チーム:** Engineering / **強度:** Strong / **対象:** `reports/views.py:14-18`、`knowledge/views.py:18-22`、`tickets/views.py:17-21`、`dashboard/views.py:22-28`ほか

- 問題: 各viewの`_current_engagement`がセッションIDだけで案件を取得し、案件メンバー確認が同じseamにない。案件から外されたユーザーの既存セッションが残る。
- Before → After: 10以上の浅い取得関数 → membershipを検証する1つのinterface
- 実施: owner/member/staff規則、未選択、無効案件、セッション掃除を`engagements`配下の案件コンテキストmoduleへ集約する。
- 完了条件: メンバー解除後、全案件URLが403/404。全viewとテストが同じinterfaceを使用。

### 2. LLM外向き送信ポリシーをcompletion/embeddingで統一

**チーム:** Engineering / **強度:** Strong / **対象:** `docs/adr/0002-llm-provider-per-engagement.md`、`llm/services.py`、`knowledge/ingest.py:61-65,105-125`

- 問題: completionは案件設定を参照する一方、embeddingはグローバル設定で外部へ送れる。機密案件のOllama指定をすり抜ける可能性がある。
- Before → After: 送信経路ごとの判断 → 案件・目的・データ区分を受けるegress interface
- 実施: fail-closedの送信判定、監査ログ、provider/model選択を1つの深いmoduleへ集約する。
- 完了条件: Ollama案件のcompletion/embeddingで外部HTTP 0件。違反設定は送信前に失敗。

### 3. 自律提案の承認・却下を原子的にする

**チーム:** Engineering / **強度:** Strong / **対象:** `autopilot/services.py:267-303`

- 問題: 状態確認、成果物作成、提案更新、監査がtransaction外で、二重POSTや並行承認により重複生成できる。
- Before → After: 分散した副作用 → `select_for_update`付き承認module
- 実施: 1 transaction内で行ロック、状態遷移、成果物作成、監査記録を完結する。
- 完了条件: 並行承認テストで成果物1件、判断記録1件。失敗時は全ロールバック。

### 4. モバイルのアプリシェルをオフキャンバス化

**チーム:** Web Design / **強度:** Strong / **対象:** `static/css/app_shell.css:34-59,253-275`、`templates/partials/header.html`

- 問題: 900px以下でも68pxのアイコン-onlyサイドバーと過密ヘッダーが残り、本文と現在地を圧迫する。
- Before → After: 常設68pxレール → メニュー、オーバーレイ、フォーカストラップ付きドロワー
- 実施: モバイル専用ヘッダー、案件名、検索入口、ドロワー、本文スクロール制御を設計する。
- 完了条件: 360/768/1024pxで、意図した表以外に横スクロールなし。現在案件と主要CTAを常時判別可能。

### 5. チケット同期を明示的な状態機械へ深化

**チーム:** Engineering / **強度:** Strong / **対象:** `tickets/services.py:35-96`

- 問題: 接続例外以外では`SyncRun`がRUNNINGのまま残り、逐次更新中の例外で部分同期になる。
- Before → After: 成功経路中心の手続き → running/success/partial/failedを保証する同期interface
- 実施: 例外分類、try/finally、transaction/checkpoint、同期件数と失敗理由を明文化する。
- 完了条件: 任意位置の例外注入後もRUNNING 0件。再実行で整合性が回復する。

### 6. 承認・却下・状態変更を意思決定UIにする

**チーム:** Web Design / **強度:** Strong / **対象:** `autopilot/templates/autopilot/queue.html:38-69`、`templates/risks/list.html:84-91`

- 問題: 影響範囲、生成差分、理由、確認、Undoなしで重要操作を即時確定できる。
- Before → After: 横並びの即時操作 → 根拠→影響→差分→確認の決定フロー
- 実施: 承認先と生成物のプレビュー、却下理由必須、二重送信防止、結果と再試行を設計する。
- 完了条件: 判断前に「誰が・何を・どこへ反映するか」を確認でき、誤操作を戻せる。

### 7. 非同期ジョブに再試行・backoff・重複抑止を導入

**チーム:** Engineering / **強度:** Strong / **対象:** `tickets/tasks.py:22-86`、`autopilot/tasks.py`

- 問題: 同期→検知→通知→要約→巡回の途中失敗で後続が欠落し、再実行規約もない。
- Before → After: 直列タスク → idempotency key付きの再実行可能なjob module
- 実施: retry分類、指数backoff、案件×時刻窓の重複抑止、失敗隔離、管理画面からの再実行を追加する。
- 完了条件: 一時障害から自動回復し、同じ入力の再実行で成果物が増えない。

### 8. 自律巡回のLLM利用枠をDBで予約

**チーム:** Engineering / **強度:** Strong / **対象:** `autopilot/services.py:48-54,140-156`

- 問題: 巡回開始時のcountだけで全findingを処理し、1巡回内・並行巡回とも日次上限を超えられる。
- Before → After: 非原子的count → conditional updateによるquota ledger
- 実施: `run_completion`前のseamで利用枠を予約し、失敗時の返却規則も定義する。
- 完了条件: 並行巡回でも案件ごとの上限超過0件。残量と利用理由を監査可能。

### 9. 通知配信をOutbox/DeliveryAttempt化

**チーム:** Engineering / **強度:** Strong / **対象:** `tickets/tasks.py:33-44`、`tickets/notify.py:37-54`

- 問題: チャネル別の配信状態とidempotency keyがなく、再試行は重複送信、失敗は回復不能になる。
- Before → After: fire-and-forget → Notification×Channelの配信試行module
- 実施: pending/sent/failed、試行回数、次回時刻、応答概要を保存するoutboxを導入する。
- 完了条件: 再実行で重複通知0件。失敗だけを管理画面から再送可能。

### 10. アクセシビリティ基盤を共通interface化

**チーム:** Web Design / **強度:** Strong / **対象:** `templates/analytics/analysis.html:83-89,254-264`、`templates/partials/header.html`、共通form

- 問題: skip link、`aria-current`、タブのrole/キーボード操作、エラー関連付け、live regionが不足する。
- Before → After: ページごとの部分対応 → shell/form/tab/messageの共通アクセシブルpattern
- 実施: WAI-ARIAタブ、label/error関連付け、main識別、通知読み上げ、キーボード順序を標準化する。
- 完了条件: キーボードのみで主要フロー完遂。状態変化とエラーを支援技術で認識可能。

### 11. チケット一覧をPMOの作業キューへ再設計

**チーム:** Web Design / **強度:** Strong / **対象:** `templates/tickets/list.html:31-105`、`static/css/tickets.css`

- 問題: 件名検索と4タブ中心で、担当、期限、優先度、接続元の複合条件や保存ビューがない。
- Before → After: 閲覧テーブル → 絞り込み・並べ替え・保存ビュー付き作業キュー
- 実施: クイックフィルタ、条件チップ、件数、sticky header、外部リンク表示を追加する。
- 完了条件: 「今週・高優先度・未割当」を3操作以内で作成し、条件と件数を常時確認できる。

### 12. CIと静的品質ゲートを全16アプリへ拡張

**チーム:** Engineering / **強度:** Strong / **対象:** `pytest.ini:4`、リポジトリ直下

- 問題: coverage対象が4アプリに限定され、CI、lint、type/security gateがない。
- Before → After: ローカル任意検証 → PR必須の品質interface
- 実施: 全pytest/coverage、ruff、型検査、pip-audit、`manage.py check --deploy`をCI化する。
- 完了条件: 全16アプリがcoverage集計対象。主要branchで必須チェックが通らない限りmerge不可。

### 13. サイドバーをPMO業務単位へ再編

**チーム:** Web Design / **強度:** Strong / **対象:** `templates/partials/sidebar.html:8-31`

- 問題: 13項目が同階層で連続し、絵文字アイコンの環境差と視覚ノイズも大きい。
- Before → After: 機能一覧 → 日次運用/品質管理/成果物/AI支援/設定の情報設計
- 実施: 未処理件数バッジ、統一アイコン、`aria-current`、優先導線を導入する。
- 完了条件: 初見利用者が主要業務の入口と未処理量を遷移前に判断できる。

### 14. 40ページのアプリシェルを共通テンプレートへ集約

**チーム:** CSS / **強度:** Strong / **対象:** `templates/**`、`adminpanel/templates/**`、`audit/templates/**`

- 問題: `app-shell`内部のflex/overflow指定が40ページで反復し、`min-width:0`の有無も揺れる。
- Before → After: 40個の浅いレイアウト → `app_layout.html`の1つの深いlayout module
- 実施: shell、content column、page header、action slotを共通blockへ移す。
- 完了条件: 全ページが同じ縮小・overflow規約を使い、レイアウト修正箇所が1つになる。

### 15. 分析グラフを意思決定可能な可視化へ

**チーム:** Web Design / **強度:** Strong / **対象:** `templates/analytics/analysis.html:89-129`、`templates/risks/list.html:53-70`

- 問題: 軸、単位、基準線、前期間差、アクセシブルな値が不足し、色だけに依存する。
- Before → After: 装飾的な線/色 → 目標・差分・注記・ドリルダウン付きチャート
- 実施: 集計表、線種/パターン/ラベル、データ鮮度、要対応レコードへの導線を追加する。
- 完了条件: 色覚やスクリーンリーダー利用でも値を取得でき、次の調査先へ遷移できる。

### 16. 構造化ログ・correlation ID・healthを導入

**チーム:** Engineering / **強度:** Worth exploring / **対象:** `config/settings.py`、`autopilot/services.py:185-189`、各task/provider

- 問題: 案件、run、provider、外部呼出しを横断する観測seamがなく、例外が局所文字列や黙殺で終わる。
- Before → After: ファイルごとのログ → correlation ID付きobservability module
- 実施: JSONログ、health/readiness、job/provider latency、失敗率、案件IDの安全な相関を追加する。
- 完了条件: 1リクエスト/1ジョブの全経路を追跡でき、SLOアラート条件を定義できる。

### 17. 主要クエリへ複合indexとquery budgetを設定

**チーム:** Engineering / **強度:** Worth exploring / **対象:** `tickets/models.py`、`llm/models.py`、`autopilot/models.py`、主要view/service

- 問題: `engagement+status+created_at`等の常用条件に対するindexと回帰検知が弱い。
- Before → After: ORM任せ → EXPLAIN根拠付きindexとquery-count test
- 実施: 実データ分布でEXPLAINし、必要な複合indexだけを追加。主要画面にquery budgetを固定する。
- 完了条件: 代表データ量で主要画面のp95とquery数が目標内。不要indexは追加しない。

### 18. 全データテーブルへレスポンシブ基盤を導入

**チーム:** CSS / **強度:** Strong / **対象:** 23テーブル、特に`templates/tickets/list.html`、`templates/risks/list.html`

- 問題: 横スクロールcontainerは9件だけで、見出し固定、列優先度、最小幅の規約がない。
- Before → After: ページ固有table → `.table-scroll` + sticky header + priority column
- 実施: 比較可能性を保つ横スクロール、固定列、長文処理、captionを標準化する。
- 完了条件: 200% zoomと360px幅でも操作列・主要識別列へ到達できる。

### 19. 状態・フィードバック・空状態を統一

**チーム:** Web Design / **強度:** Strong / **対象:** `static/css/base.css:108-114`、`templates/dashboard/home.html`、`autopilot/templates/autopilot/queue.html`

- 問題: success/info/warning/error、loading、empty、disabledの表現と次の操作が画面ごとに異なる。
- Before → After: 一行メッセージ → 理由・鮮度・権限・次のCTAを持つ状態pattern
- 実施: message、skeleton、empty state、再試行、最終更新時刻を共通化する。
- 完了条件: 保存/同期/AI/承認の結果と復旧手段が、全画面で同じ視覚言語になる。

### 20. 全操作要素へ`:focus-visible`を実装

**チーム:** CSS / **強度:** Strong / **対象:** `static/css/base.css:104`、`templates/partials/header.html:11`

- 問題: フォーム以外のbutton/link/summary/tab/navにフォーカス表示がなく、検索inputは`outline:none`。
- Before → After: 不可視フォーカス → トークン化した共通focus ring
- 実施: `.btn`、`.icon-btn`、`.nav-item`、`summary`、tab、paginationへ適用する。
- 完了条件: キーボード操作中、フォーカス位置が常に3:1以上のコントラストで見える。

### 21. 152件のインラインstyleをCSS interfaceへ移行

**チーム:** CSS / **強度:** Strong / **対象:** 43テンプレート、特に`templates/analytics/analysis.html`、`templates/risks/list.html`

- 問題: 余白、幅、flex、文字サイズがテンプレートへ漏れ、テーマ変更とCSP強化のlocalityを失う。
- Before → After: 152個の局所指定 → `.cluster`、`.stack`、`.table-scroll`、`.panel-narrow`
- 実施: 動的値だけCSS custom propertyに残し、固定値を共通classへ段階移行する。
- 完了条件: 固定インラインstyle 0件。CSPの`style-src`強化候補を提示できる。

### 22. デザイントークンを余白・文字・寸法まで拡張

**チーム:** CSS / **強度:** Worth exploring / **対象:** `static/css/base.css:1-15`、全CSS

- 問題: 色以外のspacing、radius、type scale、control height、z-index、motionが直値で散在する。
- Before → After: 色token中心 → UI寸法を含むsemantic token system
- 実施: space/type/radius/control/elevation/z/duration/content-widthを定義し、用途名で使う。
- 完了条件: 主要画面の余白・文字・操作高さをtoken変更だけで調整できる。

### 23. warning配色とダークテーマのコントラストを修正

**チーム:** CSS / **強度:** Strong / **対象:** `static/css/base.css:127`、`app_shell.css:120`、`analytics.css`、`risks.css`、`tpi.css`

- 問題: `#FFF3E0`が直書きされ、warning文字との組合せはライト/ダーク双方で小文字のAAを満たさない。
- Before → After: 固定色 → `--warning-ink/surface/border`のテーマ別組合せ
- 実施: WCAG AAを満たすsemantic colorへ置換し、高コントラストmodeも確認する。
- 完了条件: 通常文字4.5:1、UI境界3:1以上。直書きwarning色0件。

### 24. 横断検索を情報探索の中心へ深化

**チーム:** Web Design / **強度:** Worth exploring / **対象:** `templates/partials/header.html:9-13`、`templates/dashboard/search.html:14-28`

- 問題: 結果に件数、snippet、案件、状態、更新日、filter、ハイライトがなく同名対象を識別しにくい。
- Before → After: タイトル一覧 → 種別/状態/期間で絞れる検索interface
- 実施: suggestion、recent、meta情報、キーボード選択、ゼロ件時の条件解除を追加する。
- 完了条件: 結果画面だけで対象を識別でき、同名レコードへの誤遷移を防げる。

### 25. Copilotを根拠付きPMO支援へ再設計

**チーム:** Web Design / **強度:** Worth exploring / **対象:** `templates/copilot/thread.html:32-58`、`static/css/copilot.css`

- 問題: 引用元、対象期間、データ鮮度、関連レコード、生成状態が会話内で確認しにくい。
- Before → After: 会話欄 → 引用と業務レコードを往復できる相談interface
- 実施: 推奨質問、citation、期間/鮮度、関連チケット、copy/regenerate/feedback、生成中断を追加する。
- 完了条件: 回答根拠と対象範囲を確認でき、引用元レコードへ直接遷移できる。

### 26. ページヘッダー・タブ・フィルターの狭幅規約を統一

**チーム:** Web Design / **強度:** Worth exploring / **対象:** `static/css/app_shell.css:273-276`、`static/css/tickets.css:1-19`、各page header

- 問題: header action、tab、filterに折返し/横スクロール規約がなく、ページ別CSSの大半にbreakpointがない。
- Before → After: 画面ごとの崩れ方 → 共通responsive behavior
- 実施: header縦積み、action wrap、tab横スクロール、filter 1列化を共通classで実装する。
- 完了条件: 主要48テンプレートで見出し・CTA・filterが重ならない。

### 27. 固定grid/幅をcontainer依存へ置換

**チーム:** CSS / **強度:** Worth exploring / **対象:** `static/css/analytics.css:43`、`tpi.css:19-20`、`risks.css:15`

- 問題: 4列form、220px input、3列kanbanが利用可能幅を無視して固定される。
- Before → After: viewport依存 → `auto-fit/minmax`とcontainer query
- 実施: 各moduleが自身のcontainer幅で再配置するinterfaceを持つ。
- 完了条件: sidebar状態や埋込み位置が変わってもレイアウトが破綻しない。

### 28. 操作ターゲットを44px相当へ統一

**チーム:** CSS / **強度:** Strong / **対象:** `app_shell.css:185-190`、`tickets.css:68-74`、header icons

- 問題: sidebar toggle 24px、pagination 28px、header icon 36pxでタッチ操作が難しい。
- Before → After: 見た目=hit area → 視覚寸法を保った44px hit area
- 実施: padding/pseudo elementでhit領域を拡張し、隣接target間隔も確保する。
- 完了条件: 主要操作が44×44px相当、または十分な間隔を持つ。

### 29. reduced motionとテーマ初期表示を整備

**チーム:** CSS / **強度:** Worth exploring / **対象:** `templates/base.html:9`、`static/js/theme.js:4-6`、各transition

- 問題: defer後にテーマを適用してflashし得る。motion削減設定と`color-scheme`もない。
- Before → After: 描画後補正 → server/headで初期テーマ確定 + reduced-motion
- 実施: 初期属性、`color-scheme`、transition/transform停止規則を追加する。
- 完了条件: 保存テーマのFOUCなし。OSの動き削減設定に従う。

### 30. CSSの重複・衝突をcascade layerと視覚回帰で固定

**チーム:** CSS / **強度:** Worth exploring / **対象:** `analytics.css`と`autopilot.css`のtab、page内style、`reports/print.html`

- 問題: 同名classとページ内CSSが重複し、変更の影響範囲が予測しにくい。
- Before → After: 暗黙のcascade → reset/token/layout/pattern/pageの明示layer
- 実施: 名前空間、共通pattern統合、print stylesheet、主要viewportのscreenshot回帰を導入する。
- 完了条件: 重複tab定義0件。desktop/mobile/dark/printの基準画像をCIで比較できる。

## チーム別チェック

| チーム | 対象順位 | 件数 |
|---|---|---:|
| Engineering | 1, 2, 3, 5, 7, 8, 9, 12, 16, 17 | 10 |
| Web Design | 4, 6, 10, 11, 13, 15, 19, 24, 25, 26 | 10 |
| CSS | 14, 18, 20, 21, 22, 23, 27, 28, 29, 30 | 10 |

## 最初の2週間

1. 順位1〜3だけを独立PRに分け、権限・外部送信・並行承認の回帰テストを先に置く。
2. 順位4〜6をFigma相当の静的HTMLプロトタイプで確認し、360/768/1440pxの導線を確定する。
3. 順位7〜9はjob/outboxのデータモデルと再実行規約をADRとして決めてから実装する。
4. 順位10〜12でアクセシビリティとCIを「今後の変更が後退しない」品質ゲートにする。

## Top recommendation

最初に取り組むのは **順位1「案件コンテキストを1つの深いmoduleへ集約」**。ADR-0001が案件単位アクセス制御を機密性の中心に置く一方、現在はそのinterfaceが多数のviewへ漏れている。ここを深めると、1回の修正が全画面・全テストへleverageを生み、権限バグのlocalityを回復できる。
