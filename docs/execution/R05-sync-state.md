# R-05 同期状態遷移 実行台帳

- ステータス: verified
- 担当: Codex親エージェント
- ブランチ: `codex-r05-sync`
- worktree: `/private/tmp/PMO_Agent-r05-sync`
- 目的: `SyncRun`のRUNNINGから終端状態への遷移を一度に限定し、予期しない例外でもRUNNINGを残さない。
- 対象ファイル: `tickets/models.py`、`tickets/services.py`、`tickets/tests/test_services_sync.py`
- 変更禁止範囲: 通知Outbox、共通ジョブUI、push、mainへのマージ。
- 依存関係: R-05の共通ジョブ契約・Outboxは後続。
- 設計判断: DBの条件付き更新で終端遷移を一度に限定する。接続エラーは従来どおり失敗Runを返し、未知の例外は失敗記録後に再送出する。
- テスト結果: `tickets/tests/test_services_sync.py` 9 passed（2026-07-12、PostgreSQL）。
- 未解決事項: 同一TicketSourceの並行起動防止、retry/backoff、冪等キー、Outbox、共通ジョブUI。
- 次の操作: 差分レビュー、コミット、親ブランチへの統合待ち。
- 最終確認コミット: `8338a8b`
- 未コミット差分: あり。
