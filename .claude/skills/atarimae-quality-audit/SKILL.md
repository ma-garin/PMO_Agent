---
name: atarimae-quality-audit
description: PMO_Agent の「当たり前品質(Kano must-be)」を発見者として徹底監査する。ユーザーが「徹底的に」「洗い出して」「品質を上げて」「似たようなものが大量にある」「exhaustive review」「quality audit」等を求めたとき、または画面・機能の当たり前(表示崩れ/ラベル欠落/確認ダイアログ/二重送信/ページネーション/内部表現の露出 等)を点検・修正するときに使う。反応的な逐次修正ではなく、症状の裏の欠陥クラスを先に全列挙する。
---

# 当たり前品質 徹底監査 (PMO_Agent)

PMO_Agent は Django 6 の Web アプリ（`localhost:8000`、PostgreSQL+pgvector）。
このスキルは**当たり前品質の欠陥を発見者として洗い出し、実機で目視検証し、
系統的に一括修正する**ための手順。パスは repo ルート基準。

## このプロジェクトのオーナーの要求（最優先の作法）
- **追認者でなく発見者**。「その通り」で終わらせない。指摘された1点は"症状"として扱い、
  その裏の**欠陥クラスを自分で全列挙**してから着手する。
- **机上で満足しない**。コード読解/テストだけでOKにしない。**実機の描画を必ず目視**する
  （QA検証会社のオーナー。探索的テストの水準を求める）。
- **虚偽の断定をしない**。「確実に通る」等は禁物。verified / 未verified を正直に区別する。
- **系統的な欠陥は共通基盤で一括修正**（テンプレ個別に貼らない）。

## 手順（エージェント経路）

### 1. 静的スキャンで候補を出す（発見の起点）
```bash
bash .claude/skills/atarimae-quality-audit/scan.sh
```
当たり前欠陥の**候補**をクラス別に列挙する（インライン塗りバグ / 破壊的操作の確認欠如 /
内部表現の露出 / 軸なしチャート / ページネーション欠如 / オートフィル対策 / 桁区切り 等）。
**ヒットは候補であって結論ではない**（偽陽性が混じる。例: `削除`の語だけ拾う等）。必ず 2. で実機確認。

### 2. 実機で描画を目視する（机上で終わらせない）
dev サーバは通常起動済み。落ちていれば標準コマンドで起動:
```bash
python manage.py runserver 0.0.0.0:8000   # 別プロセスで
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8000/planning/  # 到達確認(302/200)
```
ブラウザ操作は **Playwright MCP**（`mcp__playwright__browser_navigate` / `browser_take_screenshot` /
`browser_evaluate`）。認証は永続プロファイルのセッションを再利用する（**パスワード入力は不可**。
ログアウトしていたらユーザーにログインを依頼）。データのある案件は「PMO Agent R-04〜R-10 実装」
「基幹システム刷新」。

**CSS/JS を変えたら必ずキャッシュを破棄してからスクショ**（Playwrightブラウザは古いCSSを掴む）:
```js
// browser_evaluate で実行
document.querySelectorAll('link[rel=stylesheet]').forEach(l=>{ l.href=l.href.split('?')[0]+'?v='+Date.now(); });
```
スクショは**必ず目視**する。空/エラー/崩れが見えたら未完了。

### 3. 系統的に直し、検証する
```bash
python manage.py check
python -m pytest --reuse-db -q      # 現状 450 tests green を維持
```
直したら再度 2. で実機スクショ。テスト期待値が文言変更で古くなったら更新する。

## 当たり前欠陥カタログ（本セッションで実在を確認・修正した型と、正しい直し場所）
- **インライン塗りバグ**: `<span>` を進捗塗りに使い width/height 指定 → inline は寸法無視で不可視。
  → CSS に `display:block`。（例: `.wbs-progress-fill`。`.progress-bar-fill`/`.axis-bar .fill` は `<div>` で正常）
- **チャートの識別不能**: バーがどの項目か分からない/軸目盛なし。
  → 標準の2ペイン（左に固定ラベル列）＋Y軸ラベル(HTML)＋グリッド線。時間軸は前後に余白、既定を横スクロール可能に。
- **二重送信・無反応**: LLM等の長時間ボタンが押下後も無反応で多重送信可。
  → `static/js/theme.js` の全フォーム共通ハンドラ（`aria-busy`＋「処理中…」、`disabled`は使わない）。
- **破壊的操作の確認欠如**: 削除等に確認なし。→ フォームに `data-confirm="…"`（共通ハンドラが処理）。
- **内部表現の露出**: `None`/`[]`/Python dict/英語ステータス/`manage.py`等が画面に。
  → プロンプト/表示前に人間可読な日本語へ整形。状態は日本語ラベルに正規化。
- **一覧のページネーション/検索欠如**: → `templates/partials/pagination.html` を include、view で `Paginator`。
- **オートフィル暴発**: 認証系フォームに admin 資格情報が自動挿入 → `autocomplete="off"/"new-password"`。
- **桁区切りなし**: → `{% load humanize %}` ＋ `|intcomma`。
- **時刻非依存の挨拶** 等のハードコード → view で時間帯判定して渡す。

## Gotchas（このセッションで踏んだ罠）
- **共有ブラウザの汚染**: Playwright の Chrome プロファイルは永続・共有で、過去/並行セッションの
  残タブ(GitHub/YouTube/広告等)が居座る。アクティブタブが勝手に遷移することがある。作業タブを固定し、
  想定外タブは無視。プロセス確認は `ps ax | grep -E 'playwright-mcp|claude'`。
- **CSS変更が反映されない** = ブラウザキャッシュ。上のキャッシュ破棄JSを毎回。サーバ側は
  `curl -s localhost:8000/static/css/xxx.css | grep <新ルール>` で配信を確認できる。
- **`--reuse-db` のフレーク**: `reports ... test_default_template_exists_after_migration` 等が稀に落ちる。
  `--create-db` でクリーンに再実行すると通る（DB状態の残りカス）。
- **LLM(Ollama)不通**: 既定モデルはローカルに存在するもの（`ollama list` で確認。qwen2.5:3b 等）。
  未取得モデルを指定すると404。エラーは「どのモデルをpullすべきか」を示す。
- **禁止事項**: 私(エージェント)はパスワード入力・アカウント作成・権限/共有変更・恒久的削除を行わない。
  検証で作ったテストデータは「検証:」表記にし、後で掃除する。

## human path
ブラウザで `http://localhost:8000` を開きログイン。ヘッドレスでは意味がないので上の Playwright 経路を使う。
