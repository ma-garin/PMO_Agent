import pytest
from django.contrib.auth.models import User
from django.core.management import call_command

from engagements.models import Engagement
from pmo_agent.models import PmoTaskStore

NAME = "POS-TAX0 レジシステム 消費税0%対応"


@pytest.mark.django_db
def test_seed_sample_project_creates_delayed_project():
    User.objects.create_user(username="admin", password="x", is_superuser=True, is_staff=True)
    call_command("seed_sample_project")

    eng = Engagement.objects.get(name=NAME)
    assert eng.status == "active"
    store = PmoTaskStore.objects.get(engagement=eng)
    assert len(store.tasks) == 8
    # 適度に遅延: 遅延またはブロックが複数、完了も一部
    delayed = [t for t in store.tasks if t["status"] in ("delayed", "blocked") or t["delay"] > 0]
    assert len(delayed) >= 3
    assert any(t["status"] == "blocked" for t in store.tasks)
    assert any(t["status"] == "done" for t in store.tasks)


@pytest.mark.django_db
def test_seed_sample_project_is_idempotent():
    User.objects.create_user(username="admin", password="x", is_superuser=True)
    call_command("seed_sample_project")
    call_command("seed_sample_project")
    assert Engagement.objects.filter(name=NAME).count() == 1
    assert PmoTaskStore.objects.filter(engagement__name=NAME).count() == 1
