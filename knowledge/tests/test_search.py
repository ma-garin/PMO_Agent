from unittest.mock import patch

import pytest
from django.contrib.auth.models import User

from engagements.models import Engagement
from knowledge.models import Document, DocumentChunk
from knowledge.search import search_knowledge

DIM = 768


def _fake_embed(texts):
    return [[0.1] * DIM for _ in texts]


@pytest.fixture
def engagement(db) -> Engagement:
    owner = User.objects.create_user(username="pmo", password="x")
    return Engagement.objects.create(name="検証案件", owner=owner)


@pytest.fixture
def other_engagement(db) -> Engagement:
    owner = User.objects.create_user(username="other", password="x")
    return Engagement.objects.create(name="他案件", owner=owner)


def _make_indexed_document(engagement, title) -> Document:
    doc = Document.objects.create(engagement=engagement, title=title, status=Document.Status.INDEXED)
    DocumentChunk.objects.create(document=doc, index=0, content=f"{title}の内容", embedding=[0.1] * DIM)
    return doc


@pytest.mark.django_db
class TestSearchKnowledge:
    def test_engagement_scoped_document_only_visible_in_own_engagement(
        self, engagement, other_engagement
    ):
        _make_indexed_document(other_engagement, "他案件専用文書")
        with patch("knowledge.search.embed_texts", side_effect=_fake_embed):
            hits = search_knowledge(engagement, "クエリ")
        assert hits == []

    def test_common_document_visible_to_all(self, engagement):
        Document.objects.create(engagement=None, title="共通文書", status=Document.Status.INDEXED)
        doc = Document.objects.get(title="共通文書")
        DocumentChunk.objects.create(document=doc, index=0, content="共通の内容", embedding=[0.1] * DIM)

        with patch("knowledge.search.embed_texts", side_effect=_fake_embed):
            hits = search_knowledge(engagement, "クエリ")
        assert len(hits) == 1
        assert hits[0].document_title == "共通文書"

    def test_results_ordered_by_distance(self, engagement):
        doc = _make_indexed_document(engagement, "文書A")
        DocumentChunk.objects.create(
            document=doc, index=1, content="遠いチャンク", embedding=[0.9] * DIM
        )
        with patch("knowledge.search.embed_texts", side_effect=_fake_embed):
            hits = search_knowledge(engagement, "クエリ", top_k=2)
        assert len(hits) == 2
        assert hits[0].distance <= hits[1].distance
