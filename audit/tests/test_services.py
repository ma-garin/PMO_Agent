import pytest
from django.contrib.auth.models import User

from audit.models import AuditLog
from audit.services import record
from engagements.models import Engagement


@pytest.fixture
def user(db) -> User:
    return User.objects.create_user(username="pmo", password="x")


@pytest.mark.django_db
class TestRecord:
    def test_creates_log_with_target_info(self, user):
        engagement = Engagement.objects.create(name="検証案件", owner=user)
        log = record(user, "engagement_edit", engagement, detail="検証案件")

        assert AuditLog.objects.count() == 1
        assert log.actor == user
        assert log.action == "engagement_edit"
        assert log.target_type == "Engagement"
        assert log.target_id == engagement.pk
        assert log.detail == "検証案件"

    def test_target_none_leaves_type_and_id_empty(self, user):
        log = record(user, "system_event")
        assert log.target_type == ""
        assert log.target_id is None
