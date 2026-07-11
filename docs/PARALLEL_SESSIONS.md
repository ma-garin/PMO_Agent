# 並行セッション運用ガイド（再発防止策）

## 背景

Phase 6(管理者ロール分離)の実装中、別セッションが同じ作業ディレクトリでPhase 3/4/5(`llm` `copilot` `reports` `knowledge` `tpi`)を並行実装していたため、`config/settings.py` `config/urls.py` `templates/partials/sidebar.html` などの共有ファイルが数秒単位で競合・上書きし合う状態になった。結果として、通常の編集ではなくgitオブジェクトレベル(`hash-object`/`update-index`)での差分抽出が必要になり、実装そのものより並行作業の衝突回避に多くの時間を要した。

## 再発防止策

### 1. フェーズごとにgit worktreeを切る(最重要)

複数フェーズを同時に進める場合、同一ディレクトリで直接作業しない。

```bash
git worktree add ../PMO_Agent-phaseN -b phaseN
```

- 各セッション/エージェントは自分専用のworktree(別ディレクトリ・別ブランチ)で作業する
- `config/settings.py` `config/urls.py` などの共有ファイルへの同時書き込みが物理的に発生しなくなる
- 完了後は各ブランチを順にmainへマージする(競合が起きてもこの時点なら通常のgit conflict解消で済む)
- Claude Code / Codexへの委譲時も、可能な限り `isolation: "worktree"` を指定して隔離する

### 2. 依頼時に前提を明示する

「実装済みか確認して」ではなく「未実装前提でPhase Xを実装して」のように、状態確認が不要なら明示する。前提確認の往復を1回省略できる。

### 3. 検証範囲を事前に指定する

「pytestが通ればOK、ブラウザ確認は不要」など、必要な検証レベルを先に指定する。Playwright MCP等のツールが他セッションで競合している場合の代替検証(curl等)を省略でき、時間短縮になる。

## 適用範囲

今後、複数フェーズ(Phase 3〜9等)を同時に着手する場合は、着手前に本ドキュメントに従いworktreeを分離すること。単一フェーズを単独で進める場合はこの制約は不要。
