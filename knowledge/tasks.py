from procrastinate.contrib.django import app

from .ingest import ingest_document as _ingest_document


@app.task(name="knowledge.process_document")
def process_document(document_id: int) -> None:
    _ingest_document(document_id)
