# PMO Agent

第三者検証（ソフトウェア品質検証）会社向けの **AI PMO 支援システム**。JIRA / Redmine のチケットを取り込み、品質メトリクス・ODC 分析・リスク管理・テスト計画・レポート生成・自律運転（オートパイロット）を、案件（Engagement）単位で支援します。

An **AI-assisted PMO (Project Management Office) support system** for third-party software-verification companies. It ingests JIRA / Redmine tickets and supports quality metrics, ODC analysis, risk management, test planning, report generation, and an autonomous "autopilot" — all scoped per engagement (customer project).

> 🇯🇵 日本語 / 🇬🇧 English 併記。各セクションは日本語→英語の順です。
> Each section is written in Japanese first, then English.

---

## 概要 / Overview

🇯🇵 本システムは「検証会社が複数の顧客案件のPMO業務を回す」ことを主眼に設計されています。チケット管理システム（JIRA / Redmine）への **読み取り専用** 連携でデータを集約し、欠陥の定量分析（ODC 分類・収束曲線）、品質リスク台帳、テスト進捗・品質ゲート、AIによる報告書ドラフト、そして日次巡回で異常を検知し提案する自律エージェントを備えます。LLM は案件ごとに OpenAI / Claude / ローカル（Ollama）を選択できます。

🇬🇧 The system is designed around a verification company running PMO work across multiple client engagements. It aggregates data via **read-only** integration with ticketing systems (JIRA / Redmine), and provides quantitative defect analysis (ODC classification, convergence curves), a quality-risk register, test progress & quality gates, AI-drafted reports, and an autonomous agent that patrols daily to detect anomalies and propose actions. The LLM provider is selectable per engagement: OpenAI / Claude / local (Ollama).

---

## 主要機能 / Key Features

🇯🇵 / 🇬🇧

| 領域 / Area | 機能 / Feature |
|---|---|
| 案件管理 / Engagements | 案件（顧客×対象×契約期間）単位のスコープ、メンバー管理、ポートフォリオ横断ビュー / Per-engagement scoping, member management, portfolio view |
| チケット連携 / Tickets | JIRA / Redmine の読み取り専用同期、停滞・期限超過検知、ステータス履歴取込 / Read-only sync, stagnation/overdue detection, status-history import |
| 品質分析 / Analytics | 欠陥メトリクス、収束曲線、ODC 4軸分類（手動＋LLM推定）、再オープン率、月次推移 / Defect metrics, convergence curves, ODC classification (manual + LLM), reopen rate, monthly trends |
| リスク・改善 / Risks | 5×5 リスクマトリクス、AI候補提案、改善アクション（かんばん） / 5×5 risk matrix, AI suggestions, improvement-action kanban |
| テスト管理 / Test Mgmt | テスト計画（AIドラフト＋承認）、進捗トラッキング、品質ゲート / Test plans (AI draft + approval), progress tracking, quality gates |
| TPI評価 / TPI | TPI NEXT ベースのテストプロセス成熟度評価 / TPI NEXT test-process maturity assessment |
| レポート / Reports | メトリクスからのAI報告書ドラフト、テンプレート管理、承認、印刷 / AI report drafts from metrics, template management, approval, print |
| Copilot | 案件文脈＋RAG を使ったチャット、能動要約 / Context+RAG chat, proactive summaries |
| ナレッジ / Knowledge | 文書取込（txt/md/pdf/docx）、pgvector によるRAG検索 / Document ingest, pgvector RAG search |
| 自律運転 / Autopilot | ルールベース異常検知＋LLM分析、人の承認キュー / Rule-based detection + LLM analysis, human approval queue |
| 管理 / Admin | ユーザー・案件・トークン・通知チャネル・LLM利用状況・監査ログ・案件間比較 / Users, engagements, tokens, notification channels, LLM usage, audit log, benchmarks |

---

## 技術スタック / Tech Stack

🇯🇵 / 🇬🇧

- **Python 3.13**, **Django 6.0.7**
- **PostgreSQL** + **pgvector**（RAG のベクトル検索 / vector search for RAG）
- **Procrastinate**（PostgreSQL ネイティブの非同期ジョブキュー。Celery/Redis は不使用 / PostgreSQL-native async job queue; no Celery/Redis）
- **LLM**: OpenAI / Anthropic Claude / Ollama（案件単位で選択 / selectable per engagement）
- 暗号化 / Crypto: `cryptography`（Fernet でAPIトークンを暗号化保存 / Fernet-encrypted API tokens）
- ログイン保護 / Login hardening: `django-axes`
- HTML サニタイズ / Sanitizer: `nh3`
- テスト / Testing: `pytest` + `pytest-django`

> 方針: **Docker やビジネス契約が必要なサービスは使わない**（PostgreSQL は Homebrew 等でローカル運用）。
> Policy: **No Docker and no services requiring a business contract** (PostgreSQL runs locally, e.g. via Homebrew).

---

## アーキテクチャ / Architecture

🇯🇵 機能ごとに Django アプリを分割しています。/ 🇬🇧 The project is split into feature-focused Django apps.

```
accounts      認証・プロフィール・テーマ設定        Auth, profile, theme
engagements   案件・メンバー・LLM設定              Engagements, members, LLM settings
dashboard     ホーム・検索・カレンダー             Home, search, calendar
tickets       チケット同期・停滞検知・通知          Ticket sync, stagnation, notifications
analytics     欠陥メトリクス・ODC・週次サマリー      Defect metrics, ODC, weekly digest
llm           LLM抽象化層・呼び出しログ            LLM abstraction, call logging
copilot       AIチャット（RAG）                   AI chat with RAG
reports       品質報告書（AIドラフト）             Quality reports (AI drafts)
knowledge     ナレッジ取込・pgvector RAG          Knowledge ingest, pgvector RAG
tpi           TPI NEXT 成熟度評価                 TPI NEXT maturity
risks         リスク台帳・改善アクション            Risk register, improvement actions
testmgmt      テスト計画・進捗・品質ゲート          Test plans, progress, quality gates
members       表示名⇔ユーザーの対応付け            Member alias mapping
adminpanel    管理セクション                      Admin section
audit         操作監査ログ                        Operation audit log
autopilot     自律運転エージェント                 Autonomous agent
```

🇯🇵 全LLM呼び出しは `llm.services.run_completion()` を単一の入口として通します。RAG 文脈は `copilot.context_builder.build_rag_context()` を各アプリが再利用します。
🇬🇧 All LLM calls go through the single entry point `llm.services.run_completion()`. RAG context is provided by `copilot.context_builder.build_rag_context()`, reused across apps.

---

## セットアップ / Getting Started

### 前提 / Prerequisites
🇯🇵 / 🇬🇧
- Python 3.13
- PostgreSQL（`vector` 拡張が使えること / with the `vector` extension available）
- （任意 / optional）ローカルLLMを使う場合は Ollama / Ollama if you use a local LLM

### 手順 / Steps

```bash
# 1. 仮想環境 / virtualenv
python3 -m venv venv && source venv/bin/activate

# 2. 依存 / dependencies
pip install -r requirements.txt

# 3. データベース / database（例 / example: pmo_agent_dev）
createdb pmo_agent_dev
psql -d pmo_agent_dev -c "CREATE EXTENSION IF NOT EXISTS vector;"

# 4. 環境変数 / environment (.env)
cp .env.example .env
#   DJANGO_DB_* を設定 / set DB settings
#   FIELD_ENCRYPTION_KEY を生成して設定 / generate & set the field-encryption key:
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# 5. マイグレーション / migrations
python manage.py migrate

# 6. デモデータ（開発のみ / dev only）/ demo data
python manage.py seed_demo   # admin / password（開発環境のみ。本番は実行不可）

# 7. 起動 / run
python manage.py runserver

# 8. 非同期ワーカー（同期・巡回など）/ async worker (sync, patrol, etc.)
python manage.py procrastinate worker
```

🇯🇵 デモの管理者は `admin` / `password`（`seed_demo` は本番 `DEBUG=False` では `--force` なしに実行できません）。
🇬🇧 The demo admin is `admin` / `password` (`seed_demo` refuses to run in production `DEBUG=False` without `--force`).

---

## 環境変数 / Configuration

🇯🇵 主要な環境変数（詳細は `.env.example`）/ 🇬🇧 Key variables (see `.env.example` for the full list):

| 変数 / Variable | 用途 / Purpose |
|---|---|
| `DJANGO_SECRET_KEY` | 本番で必須（未設定だと起動失敗）/ Required in prod (startup fails if unset) |
| `DJANGO_DEBUG` | `true`=開発 / `false`=本番（HTTPS・セキュアCookie・HSTS を自動有効化）/ dev vs prod (prod auto-enables HTTPS, secure cookies, HSTS) |
| `DJANGO_DB_*` | データベース接続 / DB connection |
| `FIELD_ENCRYPTION_KEY` / `FIELD_ENCRYPTION_KEYS` | APIトークン暗号鍵（複数指定で無停止ローテーション）/ token encryption key(s), comma-separated for rotation |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` | クラウドLLMのキー / cloud LLM keys |
| `OLLAMA_BASE_URL` | ローカルLLMの接続先 / local LLM endpoint |
| `EMAIL_*` | 通知メール送信 / notification email |

---

## テスト / Testing

```bash
source venv/bin/activate
python -m pytest -q            # 全テスト / full suite（約 390 件 / ~390 tests）
python manage.py check --deploy  # 本番設定の点検 / production settings check
```

🇯🇵 分業方針: テストコードは Claude、実装コードは Codex が担当することがあります（プロジェクト運用ルール）。
🇬🇧 Division of labor: tests may be authored by Claude and implementation by Codex (project convention).

---

## ドキュメント / Documentation

🇯🇵 設計・運用ドキュメントは `docs/` 配下にあります。索引は [docs/README.md](docs/README.md)。
🇬🇧 Design and operations docs live under `docs/`. Index: [docs/README.md](docs/README.md).

- [CONTEXT.md](CONTEXT.md) — 用語集（ドメインモデル）/ Glossary (domain model)
- [docs/DESIGN.md](docs/DESIGN.md) — 全体設計・ロードマップ / Overall design & roadmap
- [docs/HANDBOOK.md](docs/HANDBOOK.md) — 実装ハンドブック / Implementation handbook
- [docs/OPERATIONS.md](docs/OPERATIONS.md) — バックアップ・本番設定・鍵ローテーション / Backup, prod config, key rotation
- [docs/SECURITY_FIXES.md](docs/SECURITY_FIXES.md) — セキュリティ診断と修正指示 / Security findings & fixes
- [docs/adr/](docs/adr/) — アーキテクチャ決定記録 / Architecture Decision Records

---

## セキュリティと運用 / Security & Operations

🇯🇵 / 🇬🇧
- APIトークンは Fernet で暗号化保存（DBに平文なし）/ API tokens stored Fernet-encrypted (no plaintext in DB).
- ログイン失敗ロック（django-axes）、パスワード12文字以上 / Login lockout (django-axes), 12-char minimum password.
- 監査ログ、CSRF・クリックジャッキング対策、CSV/XSS/SSRF 対策済み / Audit logging; CSRF, clickjacking, CSV/XSS/SSRF protections.
- 本番公開前チェックリストは [docs/OPERATIONS.md](docs/OPERATIONS.md) 参照 / See the go-live checklist in OPERATIONS.md.

---

## ステータス / Status

🇯🇵 Phase 0〜9 まで実装済み（認証〜自律運転）。継続してUI/UX品質の底上げと、プロジェクト管理基盤（WBS/ガント）の方向性を検討中。
🇬🇧 Phases 0–9 implemented (auth through autopilot). Ongoing work on UI/UX polish and the direction of a project-management foundation (WBS / Gantt).

---

## ライセンス / License

🇯🇵 社内向けツール（現時点で公開ライセンスは未設定）。
🇬🇧 Internal tool (no public license set at this time).
