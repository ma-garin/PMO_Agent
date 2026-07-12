import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from django.urls import reverse

from audit.models import AuditLog
from engagements.models import Engagement
from risks.management.commands.init_roadmap_project import PROJECT_NAME, ROADMAP_ACTIONS
from risks.models import ImprovementAction


@pytest.mark.django_db
def test_init_roadmap_project_is_idempotent():
    owner = User.objects.create_user(username="admin", password="x", is_staff=True)

    call_command("init_roadmap_project", owner=owner.username)
    action = ImprovementAction.objects.get(origin_note="ROADMAP:R-04")
    action.status = ImprovementAction.Status.DONE
    action.save(update_fields=["status"])
    call_command("init_roadmap_project", owner=owner.username)

    engagement = Engagement.objects.get(name=PROJECT_NAME)
    assert engagement.owner == owner
    assert engagement.members.filter(pk=owner.pk).exists()
    assert engagement.improvement_actions.count() == len(ROADMAP_ACTIONS)
    assert engagement.progress == 14
    action.refresh_from_db()
    assert action.status == ImprovementAction.Status.DONE
    assert AuditLog.objects.filter(action="roadmap_project_initialized").count() == 2


@pytest.mark.django_db
def test_action_status_updates_roadmap_project_progress(client):
    owner = User.objects.create_user(username="admin", password="x", is_staff=True)
    call_command("init_roadmap_project", owner=owner.username)
    engagement = Engagement.objects.get(name=PROJECT_NAME)
    action = engagement.improvement_actions.get(origin_note="ROADMAP:R-04")
    client.force_login(owner)
    session = client.session
    session["current_engagement_id"] = engagement.pk
    session.save()

    response = client.post(
        reverse("risks:action_status", args=[action.pk]),
        {"status": ImprovementAction.Status.DONE},
    )

    assert response.status_code == 302
    engagement.refresh_from_db()
    assert engagement.progress == 14
    assert AuditLog.objects.filter(
        action="improvement_action_status_change", target_id=action.pk
    ).exists()
