from unittest.mock import patch

import pytest
from django.contrib.auth.models import User

from analytics.llm_suggest import suggest_classification
from analytics.models import OdcClassification
from engagements.models import Engagement
from llm.providers.base import LlmError
from tickets.models import Ticket, TicketSource


@pytest.fixture
def engagement(db) -> Engagement:
    owner = User.objects.create_user(username="pmo", password="x")
    return Engagement.objects.create(name="検証案件", owner=owner)


@pytest.fixture
def ticket(engagement) -> Ticket:
    source = TicketSource.objects.create(
        engagement=engagement,
        kind=TicketSource.Kind.JIRA,
        name="JIRA",
        base_url="https://example.atlassian.net",
        project_key="T",
    )
    return Ticket.objects.create(
        source=source, external_id="T-1", summary="ログインで例外", ticket_type="Bug"
    )


@pytest.mark.django_db
class TestSuggestClassification:
    def test_valid_json_creates_pending_classification(self, ticket):
        raw = '{"defect_type": "function", "trigger": "coverage", "activity": "unit_test", "impact": "major"}'
        with patch("analytics.llm_suggest.run_completion", return_value=raw):
            classification = suggest_classification(ticket)

        assert classification.status == OdcClassification.Status.PENDING
        assert classification.source == OdcClassification.Source.LLM
        assert classification.defect_type == "function"
        assert classification.impact == "major"

    def test_confirmed_classification_is_not_overwritten(self, ticket):
        OdcClassification.objects.create(
            ticket=ticket,
            defect_type="algorithm",
            status=OdcClassification.Status.CONFIRMED,
            source=OdcClassification.Source.MANUAL,
        )
        with patch("analytics.llm_suggest.run_completion") as mock_run:
            result = suggest_classification(ticket)

        mock_run.assert_not_called()
        assert result.defect_type == "algorithm"
        assert result.status == OdcClassification.Status.CONFIRMED

    def test_broken_json_results_in_empty_axes(self, ticket):
        with patch("analytics.llm_suggest.run_completion", return_value="not json"):
            classification = suggest_classification(ticket)

        assert classification.status == OdcClassification.Status.PENDING
        assert classification.defect_type == ""
        assert classification.trigger == ""

    def test_out_of_choice_values_become_empty(self, ticket):
        raw = '{"defect_type": "not_a_real_value", "trigger": "coverage"}'
        with patch("analytics.llm_suggest.run_completion", return_value=raw):
            classification = suggest_classification(ticket)

        assert classification.defect_type == ""
        assert classification.trigger == "coverage"

    def test_llm_error_still_creates_pending_with_empty_axes(self, ticket):
        with patch("analytics.llm_suggest.run_completion", side_effect=LlmError("down")):
            classification = suggest_classification(ticket)

        assert classification.status == OdcClassification.Status.PENDING
        assert classification.defect_type == ""
