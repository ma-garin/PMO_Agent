# R-04 自律提案の承認・却下の原子性

- ステータス: reviewed
- 担当: Codexサブエージェント `/root/implement_r04_approval`
- ブランチ: `codex-r04-approval`
- worktree: `/private/tmp/PMO_Agent-r04-approval`
- 実装コミット: `25ed4af`
- 未コミット差分: なし（本台帳の追記前時点）

## 目的と受け入れ条件

- 承認・却下対象を`select_for_update`でロックする。
- 状態確認、成果物作成、判断更新、監査記録を同一トランザクションで実行する。
- 再送・並行承認で成果物を重複生成しない。
- 既に判断済みの場合は安全に拒否する。
- 途中失敗時は成果物と判断状態をすべてロールバックする。

## 実施内容

- `apply_proposal`と`reject_proposal`を`transaction.atomic`化した。
- 呼び出し元が保持するモデル状態を信用せず、トランザクション内で対象行を再取得・ロックする共通処理を追加した。
- PostgreSQLの別接続2本による並行承認テストを追加し、成功1件・判断済み拒否1件・成果物1件を確認した。
- 古いモデルインスタンスによる再送、監査記録失敗時の承認・却下ロールバックを追加検証した。

## テスト結果

- `autopilot/tests/test_services.py`: 20 passed
- `autopilot/tests/test_services.py autopilot/tests/test_views.py audit/tests/test_recording_points.py`: 43 passed、既存の`TestPlan`収集警告1件

## 自己レビュー

- Standards: リポジトリ固有の規約ファイルは検出されず、差分に重大なコードスメルなし。承認・却下の重複ロック処理は共通関数へ集約済み。
- Spec: 行ロック、全副作用の同一トランザクション化、並行時の成果物1件、失敗時の全ロールバックを満たす。
- 留意点: 報告書ドラフト承認ではLLM呼び出し中も行ロックを保持する。原子性要件を優先した現仕様であり、将来Outbox化する場合は別設計が必要。

## 次の操作

1. 統合担当が`25ed4af`を統合ブランチへ取り込む。
2. 統合後に対象テストを再実行する。
3. PMO Agent上のR-04改善アクションへ実装・検証結果を反映する。
