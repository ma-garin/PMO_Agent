#!/usr/bin/env bash
# 当たり前品質スキャン — PMO_Agent 用の静的検出器
# 目的: 「症状の裏の欠陥クラス」を先に全列挙するための候補リストを出す。
# これは"発見の起点"であって最終判定ではない。各ヒットは必ず実機(ブラウザ)で
# 描画を目視し、症状の裏に同種が無いか横断確認してから直すこと。
#
# 使い方: bash .claude/skills/atarimae-quality-audit/scan.sh
set -uo pipefail
cd "$(git rev-parse --show-toplevel 2>/dev/null || echo .)"

TPL='templates */templates'
inc='--include=*.html'
say() { printf '\n\033[1m== %s ==\033[0m\n' "$1"; }
hits() { grep -rn $inc "$@" $TPL 2>/dev/null | grep -v venv; }

say "1) インライン塗りバグ（.wbs-progress-fill 型: span に width:% で塗りが0サイズ）"
# width:% を持つ <span>。CSSで display:block が無いと塗りが不可視になる（既往インシデント）
grep -rn $inc '<span[^>]*style="[^"]*width:\s*{{' $TPL 2>/dev/null | grep -v venv \
  || echo "  (該当なし)"

say "2) 破壊的操作なのに data-confirm が無いフォーム（誤クリックでデータ喪失）"
for f in $(grep -rln $inc 'method="post"' $TPL 2>/dev/null | grep -v venv); do
  grep -qiE '削除|却下|除去|revoke|delete|remove' "$f" || continue
  grep -q 'data-confirm' "$f" || echo "  [確認なし] $f"
done

say "3) 生の内部表現の露出（Python の None/[]/dict, 英語ステータス, 開発者コマンド）"
hits -E "manage\.py|os\.environ|: \[\]|'[a-z_]+':|In Progress|To Do| None<|>None<" \
  | grep -vE 'json_script|csrf' | head -20 || echo "  (該当なし)"

say "4) 軸/目盛の無いチャート（SVGは目視必須。凡例/軸ラベルの有無を確認）"
grep -rln $inc '<svg' $TPL 2>/dev/null | grep -v venv || echo "  (SVGなし)"

say "5) 一覧のページネーション欠如（件数増で全件表示 → スケール破綻）"
for app in risks members reports tpi knowledge testmgmt autopilot audit; do
  n=$(grep -rl 'Paginator' "$app/views.py" 2>/dev/null | wc -l | tr -d ' ')
  [ "$n" = 0 ] && echo "  [Paginatorなし] $app"
done

say "6) 一覧テンプレの空状態（{% empty %}）欠如"
for f in $(grep -rln $inc '{% for ' $TPL 2>/dev/null | grep -v venv | grep -iE 'list|index'); do
  grep -q '{% empty %}' "$f" || echo "  [空状態なし?] $f"
done

say "7) 認証情報系フォームのオートフィル対策（autocomplete）欠如"
for f in $(grep -rln $inc 'type="password"\|api_token\|password' $TPL 2>/dev/null | grep -v venv); do
  grep -q 'autocomplete' "$f" || echo "  [autocomplete対策なし] $f"
done

say "8) 大きな数値の桁区切り（intcomma）未使用のテンプレ"
grep -rLn $inc 'intcomma' $(grep -rln $inc 'count\|total\|回数\|件数' $TPL 2>/dev/null | grep -v venv) 2>/dev/null | head

say "9) 時刻非依存の固定挨拶・ハードコード文言（例: 常に「おはよう」）"
hits -E 'おはよう|こんにちは|こんばんは' | head || echo "  (該当なし)"

say "10) Django 健全性 & テスト（緑であること）"
if [ -d venv ]; then . venv/bin/activate 2>/dev/null; fi
python manage.py check 2>&1 | grep -E 'System check|Error' | tail -1 || echo "  (check未実行)"

printf '\n\033[1m--- 次にやること ---\033[0m\n'
cat <<'EOF'
- 各ヒットは"候補"。実機で描画を目視し、症状の裏に同種が無いか横断確認する。
- 系統的なもの(2,7 等)はテンプレ個別でなく共通基盤(theme.js/base.css/partials)で一括修正。
- 直したら実機スクショ + 全テスト(pytest --reuse-db)で確認。verified/未verifiedを正直に区別。
EOF
