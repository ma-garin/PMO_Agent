# 運用手順（バックアップ・リストア）

## 対象

1. PostgreSQLデータベース（`pmo_agent_dev` 等）— チケット・分析・レポート等の全データ
2. `media/` ディレクトリ — ナレッジ文書のアップロードファイル
3. `.env` の `FIELD_ENCRYPTION_KEY` — **これを失うと全案件のAPIトークンが復号不能になる**（別経路で厳重に保管すること。パスワードマネージャ等、DBバックアップとは別の場所に）

## 日次バックアップ

### pg_dump スクリプト例

```bash
#!/bin/bash
# scripts/backup_db.sh
set -euo pipefail

BACKUP_DIR="$HOME/pmo_agent_backups"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p "$BACKUP_DIR"

pg_dump -Fc pmo_agent_dev > "$BACKUP_DIR/pmo_agent_${DATE}.dump"

# 30日より古いバックアップを削除
find "$BACKUP_DIR" -name "pmo_agent_*.dump" -mtime +30 -delete
```

### media/ のバックアップ

```bash
rsync -a /path/to/PMO_Agent/media/ "$HOME/pmo_agent_backups/media_$(date +%Y%m%d)/"
```

### launchd での日次自動実行例（macOS）

`~/Library/LaunchAgents/com.pmoagent.backup.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.pmoagent.backup</string>
  <key>ProgramArguments</key>
  <array>
    <string>/path/to/PMO_Agent/scripts/backup_db.sh</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>3</integer>
    <key>Minute</key>
    <integer>0</integer>
  </dict>
</dict>
</plist>
```

登録: `launchctl load ~/Library/LaunchAgents/com.pmoagent.backup.plist`

## リストア手順

```bash
# DBの復元(既存DBを一度削除して作り直す場合)
dropdb pmo_agent_dev
createdb pmo_agent_dev
psql -d pmo_agent_dev -c "CREATE EXTENSION IF NOT EXISTS vector;"
pg_restore -d pmo_agent_dev /path/to/pmo_agent_20260101_030000.dump

# mediaの復元
rsync -a "$HOME/pmo_agent_backups/media_20260101/" /path/to/PMO_Agent/media/
```

**重要**: `FIELD_ENCRYPTION_KEY` が復元先の `.env` にリストア元と同じ値で設定されていないと、`TicketSource.api_token` が復号できず空文字になる（`config/crypto.py::decrypt` の仕様）。鍵は必ずDBバックアップとは別経路（パスワードマネージャ等）で保管し、リストア時に手動で設定すること。

## 鍵のローテーション（将来的な運用）

`FIELD_ENCRYPTION_KEY` をローテーションする場合、全 `TicketSource` を旧鍵で復号→新鍵で再暗号化するワンショットスクリプトが必要（現時点では未実装。Phase 8時点のスコープ外）。
