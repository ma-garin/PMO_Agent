from dataclasses import dataclass

from django.db.models import Q
from pgvector.django import CosineDistance

from .ingest import embed_texts
from .models import Document, DocumentChunk


@dataclass(frozen=True)
class SearchHit:
    content: str
    document_title: str
    chunk_index: int
    distance: float


def search_knowledge(engagement, query: str, top_k: int = 5) -> list[SearchHit]:
    query_vector = embed_texts([query])[0]
    chunks = (
        DocumentChunk.objects.filter(document__status=Document.Status.INDEXED)
        .filter(Q(document__engagement__isnull=True) | Q(document__engagement=engagement))
        .select_related("document")
        .annotate(distance=CosineDistance("embedding", query_vector))
        .order_by("distance")[:top_k]
    )
    return [
        SearchHit(
            content=chunk.content,
            document_title=chunk.document.title,
            chunk_index=chunk.index,
            distance=chunk.distance,
        )
        for chunk in chunks
    ]
