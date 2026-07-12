from unittest.mock import patch

import pytest

from autopilot.models import AgentSettings
from autopilot.tasks import daily_patrol, event_patrol
from engagements.models import Engagement


@pytest.mark.django_db
class TestDailyPatrol:
    def test_only_enabled_engagements_are_patrolled(self, engagement, owner):
        AgentSettings.objects.create(engagement=engagement, enabled=True)

        disabled_engagement = Engagement.objects.create(name="無効案件", owner=owner)
        AgentSettings.objects.create(engagement=disabled_engagement, enabled=False)

        no_settings_engagement = Engagement.objects.create(name="設定なし案件", owner=owner)

        with patch("autopilot.tasks.run_patrol") as mock_run:
            daily_patrol(timestamp=0)

        called_engagements = [call.args[0] for call in mock_run.call_args_list]
        assert engagement in called_engagements
        assert disabled_engagement not in called_engagements
        assert no_settings_engagement not in called_engagements


@pytest.mark.django_db
class TestEventPatrol:
    def test_missing_engagement_is_skipped_without_error(self):
        with patch("autopilot.tasks.run_patrol") as mock_run:
            event_patrol(engagement_id=999999)
        mock_run.assert_not_called()

    def test_existing_engagement_triggers_run_patrol(self, engagement):
        with patch("autopilot.tasks.run_patrol") as mock_run:
            event_patrol(engagement_id=engagement.pk)
        mock_run.assert_called_once_with(engagement, trigger="event")
