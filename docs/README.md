# ドキュメント索引 / Documentation Index

🇯🇵 このディレクトリの設計・運用・計画ドキュメントの一覧です。プロジェクト全体像は
リポジトリ直下の [../README.md](../README.md) を参照してください。

🇬🇧 An index of the design, operations, and planning documents in this directory.
For the overall project overview, see [../README.md](../README.md).

---

## 設計・仕様 / Design & Specs

| ドキュメント / Document | 内容 / Contents |
|---|---|
| [../CONTEXT.md](../CONTEXT.md) | 用語集（ドメインモデルのグロッサリ）/ Glossary of the domain model |
| [DESIGN.md](DESIGN.md) | 全体設計、フェーズ別ロードマップ / Overall design and phase roadmap |
| [HANDBOOK.md](HANDBOOK.md) | 実装ハンドブック（既存コード・画面規約・落とし穴・完了条件）/ Implementation handbook (existing code, UI conventions, pitfalls, DoD) |
| [adr/](adr/) | アーキテクチャ決定記録（ADR）/ Architecture Decision Records |

### フェーズ仕様 / Phase Specs
| ドキュメント / Document | 内容 / Contents |
|---|---|
| [phases/PHASE3_LLM.md](phases/PHASE3_LLM.md) | LLM抽象化・ODC推定・Copilot・レポート / LLM layer, ODC suggestion, Copilot, reports |
| [phases/PHASE4_RAG.md](phases/PHASE4_RAG.md) | ナレッジ管理・pgvector RAG / Knowledge management, pgvector RAG |
| [phases/PHASE5_TPI.md](phases/PHASE5_TPI.md) | TPI NEXT 成熟度評価 / TPI NEXT maturity |
| [PHASE6.md](PHASE6.md) | 管理者ロール分離＋改善バックログ20件 / Admin roles + 20-item backlog |
| [PHASE7.md](PHASE7.md) | 検証PMO支援モジュール / Verification PMO modules |
| [PHASE8.md](PHASE8.md) | 改善バックログの実装（4バッチ）/ Backlog implementation (4 batches) |
| [PHASE9.md](PHASE9.md) | 自律エージェント運転 / Autonomous agent (autopilot) |

---

## 運用・セキュリティ / Operations & Security

| ドキュメント / Document | 内容 / Contents |
|---|---|
| [OPERATIONS.md](OPERATIONS.md) | バックアップ・リストア、本番公開前チェックリスト、暗号鍵ローテーション / Backup/restore, go-live checklist, key rotation |
| [SECURITY_FIXES.md](SECURITY_FIXES.md) | セキュリティ診断の所見と修正指示（CWE付き）/ Security findings & fix instructions (with CWE) |

---

## 計画・調査 / Plans & Research

| ドキュメント / Document | 内容 / Contents |
|---|---|
| [plan_0712_claude.md](plan_0712_claude.md) | UI/UX品質 見直し計画（Claude）/ UI/UX quality improvement plan (Claude) |
| [plan_712_codex.md](plan_712_codex.md) | 作り込み計画・静的監査30件（Codex）/ Polish plan, 30-item static audit (Codex) |
| [PARALLEL_SESSIONS.md](PARALLEL_SESSIONS.md) | 並行セッションの分業メモ / Notes on parallel session workflow |

> 🇯🇵 `plan0712.html` は上記計画の HTML 版です。`plan_*` は設計ドキュメントであり、実装は承認後に行います。
> 🇬🇧 `plan0712.html` is an HTML rendering of the plan. `plan_*` docs are design docs; implementation follows approval.
