import os

import requests

from llm.providers.base import LlmError

from .models import Document, DocumentChunk

MAX_CHARS = 800
OVERLAP_CHARS = 200
REQUEST_TIMEOUT_SECONDS = 60


def extract_text(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext in (".txt", ".md"):
        with open(path, encoding="utf-8") as f:
            return f.read()
    if ext == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(path)
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    if ext == ".docx":
        from docx import Document as DocxDocument

        doc = DocxDocument(path)
        return "\n".join(p.text for p in doc.paragraphs)
    raise ValueError(f"未対応のファイル形式です: {ext}")


def split_chunks(text: str, max_chars: int = MAX_CHARS, overlap: int = OVERLAP_CHARS) -> list[str]:
    if not text.strip():
        return []

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        paragraphs = [text.strip()]

    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        while len(paragraph) > max_chars:
            head, paragraph = paragraph[:max_chars], paragraph[max_chars:]
            if current:
                chunks.append(current)
                current = ""
            chunks.append(head)
        candidate = f"{current}\n\n{paragraph}" if current else paragraph
        if len(candidate) > max_chars and current:
            chunks.append(current)
            tail = current[-overlap:] if len(current) > overlap else current
            current = f"{tail}\n\n{paragraph}"
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def embed_texts(texts: list[str]) -> list[list[float]]:
    provider = os.environ.get("EMBEDDING_PROVIDER", "ollama")
    if provider == "openai":
        return _embed_openai(texts)
    return _embed_ollama(texts)


def _embed_ollama(texts: list[str]) -> list[list[float]]:
    base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    model = os.environ.get("OLLAMA_EMBED_MODEL", "nomic-embed-text")
    vectors = []
    for text in texts:
        try:
            response = requests.post(
                f"{base_url.rstrip('/')}/api/embeddings",
                json={"model": model, "prompt": text},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise LlmError(str(exc)) from exc
        vectors.append(response.json()["embedding"])
    return vectors


def _embed_openai(texts: list[str]) -> list[list[float]]:
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        raise LlmError("OPENAI_API_KEYが未設定です。")
    model = os.environ.get("OPENAI_EMBED_MODEL", "text-embedding-3-small")
    try:
        response = requests.post(
            "https://api.openai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": model, "input": texts},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise LlmError(str(exc)) from exc
    data = response.json()["data"]
    return [item["embedding"] for item in data]


def ingest_document(document_id: int) -> None:
    document = Document.objects.get(pk=document_id)
    document.status = Document.Status.PROCESSING
    document.save(update_fields=["status"])

    try:
        text = extract_text(document.file.path)
        chunks = split_chunks(text)
        if not chunks:
            document.status = Document.Status.FAILED
            document.error_message = "本文を抽出できませんでした。"
            document.save(update_fields=["status", "error_message"])
            return

        vectors = embed_texts(chunks)
        DocumentChunk.objects.filter(document=document).delete()
        DocumentChunk.objects.bulk_create(
            [
                DocumentChunk(document=document, index=i, content=chunk, embedding=vector)
                for i, (chunk, vector) in enumerate(zip(chunks, vectors))
            ]
        )
        document.status = Document.Status.INDEXED
        document.error_message = ""
        document.save(update_fields=["status", "error_message"])
    except (ValueError, LlmError) as exc:
        document.status = Document.Status.FAILED
        document.error_message = str(exc)
        document.save(update_fields=["status", "error_message"])
