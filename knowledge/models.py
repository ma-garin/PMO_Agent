import os

from django.conf import settings
from django.db import models
from pgvector.django import VectorField

EMBEDDING_DIM = int(os.environ.get("EMBEDDING_DIM", "768"))


class Document(models.Model):
    class Status(models.TextChoices):
        UPLOADED = "uploaded", "取込待ち"
        PROCESSING = "processing", "処理中"
        INDEXED = "indexed", "検索可能"
        FAILED = "failed", "失敗"

    engagement = models.ForeignKey(
        "engagements.Engagement",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="documents",
    )
    title = models.CharField("タイトル", max_length=200)
    file = models.FileField("ファイル", upload_to="knowledge/%Y/%m/")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.UPLOADED)
    error_message = models.TextField(blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.title


class DocumentChunk(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="chunks")
    index = models.PositiveIntegerField("順序")
    content = models.TextField("本文")
    embedding = VectorField(dimensions=EMBEDDING_DIM)

    class Meta:
        ordering = ["document", "index"]
        constraints = [
            models.UniqueConstraint(
                fields=["document", "index"], name="unique_chunk_per_document"
            )
        ]
