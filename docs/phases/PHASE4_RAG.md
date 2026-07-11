# Phase 4 実装仕様: RAG（ナレッジ管理・ベクトル検索・根拠付き回答）

前提: [../HANDBOOK.md](../HANDBOOK.md) と Phase 3 完了（`llm.services.run_completion` が存在すること）。

## 全体像と非スコープ

- 作るもの: `knowledge`アプリ（文書アップロード→チャンク化→埋め込み→pgvector検索）、Copilotチャットと報告書生成への出典付き文脈注入
- 作らないもの: Wiki/Confluence等の外部システム連携（ファイルアップロードのみ）、OCR、画像対応

## 事前決定事項（このまま実装する）

| 論点 | 決定 |
|---|---|
| 埋め込みプロバイダ | Ollama `/api/embeddings`（モデル: `nomic-embed-text`、次元768）を既定。環境変数 `EMBEDDING_PROVIDER=ollama|openai` で OpenAI `text-embedding-3-small`（次元1536）にも切替可 |
| ベクトル次元 | `EMBEDDING_DIM` 環境変数（既定768）。**VectorFieldの次元はマイグレーション時に固定されるため、変更したら手動でマイグレーション再作成が必要**とREADMEに注記 |
| チャンク方式 | 段落（空行）区切りで結合し、1チャンク最大800文字・オーバーラップ200文字 |
| 対応形式 | `.txt` `.md`（そのまま） / `.pdf`（pypdf） / `.docx`（python-docx）。それ以外は拒否 |
| スコープ | `Document.engagement` が null=全社共通、非null=案件固有。検索時は「共通 OR 現在案件」 |
| 非同期化 | 取込（パース→チャンク→埋め込み）はProcrastinateタスク。画面は即時レスポンスしステータス表示 |

## Step 1: 依存とモデル

```bash
pip install pgvector pypdf python-docx
# requirements.txt に3つともバージョン固定で追記
```

`.env.example` 追記:
```
EMBEDDING_PROVIDER=ollama
EMBEDDING_DIM=768
OLLAMA_EMBED_MODEL=nomic-embed-text
OPENAI_EMBED_MODEL=text-embedding-3-small
```

`config/settings.py` に `MEDIA_ROOT = BASE_DIR / "media"`、`MEDIA_URL = "media/"` を追加し、`.gitignore` に `media/` を追記。

`knowledge/models.py`:
```python
import os
from pgvector.django import VectorField

EMBEDDING_DIM = int(os.environ.get("EMBEDDING_DIM", "768"))

class Document(models.Model):
    class Status(models.TextChoices):
        UPLOADED = "uploaded", "取込待ち"
        PROCESSING = "processing", "処理中"
        INDEXED = "indexed", "検索可能"
        FAILED = "failed", "失敗"
    engagement = models.ForeignKey("engagements.Engagement", null=True, blank=True,
                                   on_delete=models.CASCADE, related_name="documents")  # null=全社共通
    title = models.CharField("タイトル", max_length=200)
    file = models.FileField("ファイル", upload_to="knowledge/%Y/%m/")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.UPLOADED)
    error_message = models.TextField(blank=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ["-created_at"]

class DocumentChunk(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="chunks")
    index = models.PositiveIntegerField("順序")
    content = models.TextField("本文")
    embedding = VectorField(dimensions=EMBEDDING_DIM)
    class Meta:
        ordering = ["document", "index"]
        constraints = [models.UniqueConstraint(fields=["document", "index"], name="unique_chunk_per_document")]
```
マイグレーション先頭に pgvector拡張の有効化を入れる（開発DBでは有効化済みだが冪等に）:
```python
from pgvector.django import VectorExtension
operations = [VectorExtension(), ...]
```

## Step 2: パース・チャンク・埋め込み（knowledge/ingest.py）

```python
def extract_text(path: str) -> str
    # 拡張子で分岐。.pdf: pypdf.PdfReaderで全ページextract_text() を"\n"連結
    # .docx: python-docx Documentのparagraphsを"\n"連結 / .txt .md: そのままread
    # 未対応拡張子: ValueError

def split_chunks(text: str, max_chars: int = 800, overlap: int = 200) -> list[str]
    # 空行で段落分割→順に連結し800字を超える直前で区切る。
    # 単一段落が800字超なら強制分割。次チャンクは前チャンク末尾200字を先頭に含める。
    # 空リストにならないよう、空テキストは[]を返す

def embed_texts(texts: list[str]) -> list[list[float]]
    # EMBEDDING_PROVIDERで分岐(requestsのみ使用):
    # ollama: POST {OLLAMA_BASE_URL}/api/embeddings {"model": OLLAMA_EMBED_MODEL, "prompt": text} を1件ずつ→resp["embedding"]
    # openai: POST /v1/embeddings {"model": OPENAI_EMBED_MODEL, "input": texts} 一括→data[i]["embedding"]
    # 失敗はLlmError(llm.providers.base から import)

def ingest_document(document_id: int) -> None
    # status=PROCESSING→extract→split→embed→DocumentChunk一括作成(bulk_create)→INDEXED
    # 例外時: status=FAILED, error_message記録(raise しない)
```

`knowledge/tasks.py`（tickets/tasks.pyのProcrastinateパターンを踏襲）:
```python
@app.task(name="knowledge.process_document")
def process_document(document_id: int) -> None: ...
```

## Step 3: 検索（knowledge/search.py）

```python
from pgvector.django import CosineDistance

@dataclass(frozen=True)
class SearchHit:
    content: str
    document_title: str
    chunk_index: int
    distance: float

def search_knowledge(engagement, query: str, top_k: int = 5) -> list[SearchHit]:
    # embed_texts([query])[0] でクエリベクトル化
    # DocumentChunk.objects.filter(document__status=INDEXED)
    #   .filter(Q(document__engagement__isnull=True) | Q(document__engagement=engagement))
    #   .annotate(distance=CosineDistance("embedding", qvec)).order_by("distance")[:top_k]
```

## Step 4: 画面（templates/knowledge/list.html）

| URL | name | 動作 |
|---|---|---|
| GET `/knowledge/` | `knowledge:list` | 文書一覧（タイトル・スコープ・状態・チャンク数）＋アップロードフォーム |
| POST `/knowledge/upload/` | `knowledge:upload` | Document作成→`process_document.defer(document_id=...)`→一覧へ。「共通/この案件」のスコープ選択ラジオ付き |
| POST `/knowledge/<pk>/delete/` | `knowledge:delete` | 確認付き削除（文書とチャンク） |
| POST `/knowledge/<pk>/reindex/` | `knowledge:reindex` | FAILED文書の再取込 |

- sidebar.htmlに `&#128218; ナレッジ`（nav_active: `knowledge`）
- ファイルサイズ上限10MBをビューで検証（超過はエラーメッセージ）
- フォームのenctypeは `multipart/form-data` を忘れない

## Step 5: Copilot・報告書への出典付き注入

`copilot/context_builder.py` を拡張:
```python
def build_rag_context(engagement, query: str) -> str:
    # search_knowledge(top_k=5)の結果を
    # "[出典1: {title} 第{index}節]\n{content}" 形式で連結。ヒット0件なら空文字
```
- copilotのsendビュー: ユーザーの質問をqueryにRAG文脈を取得し、promptの先頭に「## 参考資料\n{rag_context}\n\n## 質問\n...」形式で注入。systemに「参考資料を使う場合は文末に [出典n] を明記」と追記
- reportsのgenerate_draft: 「品質基準」等の固定クエリで検索し同様に注入（ヒットなしなら従来通り）

## Step 6: テスト（knowledge/tests/）

- `test_ingest.py`: split_chunksの境界（800字丁度/巨大段落/空文字/オーバーラップ内容）、extract_textの未対応拡張子ValueError（PDF/docxは実ファイル生成が重いのでtxt/mdのみ実テスト）
- `test_search.py`: embed_textsをpatchして固定ベクトルを返し、①案件スコープの絞り込み（他案件文書が出ない）②共通文書が出る ③distance順
- `test_views.py`: アップロード→Document作成＋deferが呼ばれる（process_documentをpatch）、10MB超の拒否
- コミット例: `feat: RAGナレッジ基盤(pgvector)と出典付き回答を追加`

## Done

1. Ollama環境で: .mdファイルをアップロード→「検索可能」になる→Copilotで文書内容に関する質問をすると出典付きで回答される
2. `pytest` 全パス／DESIGN.mdのPhase 4を実装済みに更新／コミット＆push
