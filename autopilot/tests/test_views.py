import pytest
from django.contrib.auth.models import User
from django.test import Client

from autopilot.models import AgentProposal, AgentRun, AgentSettings
from engagements.models import Engagement


@pytest.fixture
def logged_in_client(client: Client, owner, engagement) -> Client:
    client.force_login(owner)
    session = client.session
    session["current_engagement_id"] = engagement.pk
    session.save()
    return client


def _make_proposal(engagement, kind=AgentProposal.Kind.SUMMARY_ONLY, payload=None, dedup_key="k"):
    run = AgentRun.objects.create(engagement=engagement, trigger="manual")
    return AgentProposal.objects.create(
        engagement=engagement, run=run, kind=kind, dedup_key=dedup_key,
        title="提案タイトル", evidence={"observed": 5}, body="分析文", payload=payload or {},
    )


@pytest.mark.django_db
class TestQueueAccess:
    def test_member_can_view_and_approve(self, logged_in_client, engagement):
        proposal = _make_proposal(engagement)
        response = logged_in_client.get("/autopilot/")
        assert response.status_code == 200
        assert proposal.title in response.content.decode()

        approve_response = logged_in_client.post(f"/autopilot/{proposal.pk}/approve/")
        assert approve_response.status_code == 302
        proposal.refresh_from_db()
        assert proposal.status == AgentProposal.Status.APPROVED

    def test_proposal_from_other_engagement_is_404(self, logged_in_client, owner):
        other_engagement = Engagement.objects.create(name="別案件", owner=owner)
        other_proposal = _make_proposal(other_engagement)

        response = logged_in_client.get(f"/autopilot/{other_proposal.pk}/approve/")
        assert response.status_code == 404


@pytest.mark.django_db
class TestRejectView:
    def test_reject_records_note(self, logged_in_client, engagement):
        proposal = _make_proposal(engagement)
        response = logged_in_client.post(
            f"/autopilot/{proposal.pk}/reject/", {"note": "不要と判断"}
        )
        assert response.status_code == 302
        proposal.refresh_from_db()
        assert proposal.status == AgentProposal.Status.REJECTED
        assert proposal.decision_note == "不要と判断"


@pytest.mark.django_db
class TestSettingsView:
    def test_get_creates_default_settings(self, logged_in_client, engagement):
        response = logged_in_client.get("/autopilot/settings/")
        assert response.status_code == 200
        assert AgentSettings.objects.filter(engagement=engagement).exists()

    def test_post_updates_settings(self, logged_in_client, engagement):
        logged_in_client.post(
            "/autopilot/settings/",
            {
                "enabled": "on",
                "stagnant_spike_threshold": "10",
                "defect_spike_threshold": "8",
                "overdue_threshold": "4",
                "max_llm_calls_per_day": "30",
            },
        )
        agent_settings = AgentSettings.objects.get(engagement=engagement)
        assert agent_settings.enabled is True
        assert agent_settings.stagnant_spike_threshold == 10
        assert agent_settings.max_llm_calls_per_day == 30


@pytest.mark.django_db
class TestHistoryView:
    def test_proposals_tab_excludes_pending(self, logged_in_client, engagement):
        pending = _make_proposal(engagement, dedup_key="pending-key")
        decided = _make_proposal(engagement, dedup_key="decided-key")
        decided.status = AgentProposal.Status.APPROVED
        decided.save(update_fields=["status"])

        response = logged_in_client.get("/autopilot/history/")
        content = response.content.decode()
        assert decided.title in content
        # pendingは提案キューにのみ表示され、履歴には出ない(件数で判定)
        assert list(response.context["page_obj"]) == [decided]
        assert pending not in list(response.context["page_obj"])

    def test_runs_tab_lists_agent_runs(self, logged_in_client, engagement):
        AgentRun.objects.create(engagement=engagement, trigger="scheduled")
        response = logged_in_client.get("/autopilot/history/?tab=runs")
        assert response.status_code == 200
        assert len(response.context["page_obj"]) == 1


@pytest.mark.django_db
class TestRunNowView:
    def test_manual_patrol_reports_result(self, logged_in_client, engagement):
        response = logged_in_client.post("/autopilot/run-now/")
        assert response.status_code == 302
        assert AgentRun.objects.filter(engagement=engagement, trigger="manual").exists()
