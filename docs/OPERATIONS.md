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

## 本番公開前チェックリスト（F-3）

本番環境（`DJANGO_DEBUG=false`）では以下を必ず設定する。設定不備は起動失敗または
セキュリティ低下につながる。

- [ ] `DJANGO_SECRET_KEY` を強力な値で設定（未設定だと起動失敗する）。
      生成例: `python -c "import secrets; print(secrets.token_urlsafe(50))"`
- [ ] `DJANGO_DEBUG=false` を設定（トレースバック露出防止）。
- [ ] `DJANGO_ALLOWED_HOSTS` を実際のドメインに設定。
- [ ] TLS終端はリバースプロキシ（nginx等）で行い、`X-Forwarded-Proto` を渡す構成にする
      （`SECURE_PROXY_SSL_HEADER` がこれを前提にHTTPS判定する）。プロキシを使わず
      アプリで直接TLSする構成なら、この行の要否を再確認すること。
- [ ] `FIELD_ENCRYPTION_KEY`（トークン暗号鍵）を設定・別保管。
- [ ] `python manage.py check --deploy` を実行し、警告を確認・解消する。
- [ ] `seed_demo` は本番で実行しない（実行が必要なら `--force` と `SEED_ADMIN_PASSWORD` を使い、
      投入後に必ずパスワードを変更）。

`DEBUG=false` のとき、`config/settings.py` は自動で HTTPS 強制・セキュアCookie・HSTS・
Content-Type-nosniff を有効化する。

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

## 鍵のローテーション（F-14）

`config/crypto.py` は `MultiFernet` に対応し、複数鍵での無停止ローテーションが可能。

手順:
1. 新しい鍵を生成: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
2. `.env` に `FIELD_ENCRYPTION_KEYS="新鍵,旧鍵"` を設定（**新鍵を先頭**。旧 `FIELD_ENCRYPTION_KEY` は後方互換で読まれるが、ローテーション時は `KEYS` を使う）。
   - この時点で、旧鍵で暗号化済みの値も復号でき、新規暗号化は新鍵で行われる。
3. 既存データを再暗号化: `python manage.py rotate_encryption_keys`
4. 動作確認後、`.env` を `FIELD_ENCRYPTION_KEYS="新鍵"` のみに更新し、旧鍵を安全に破棄。

本番のシークレット配布は、`.env` 直置きではなくシークレットマネージャ（AWS Secrets Manager / Vault 等）を推奨。鍵は必ずDBバックアップとは別経路で保管すること。
