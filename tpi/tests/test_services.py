import pytest
from django.contrib.auth.models import User

from engagements.models import Engagement
from tpi.models import TpiAnswer, TpiAssessment, TpiCheckpoint, TpiKeyArea
from tpi.services import level_status


@pytest.fixture
def engagement(db) -> Engagement:
    owner = User.objects.create_user(username="pmo", password="x")
    return Engagement.objects.create(name="検証案件", owner=owner)


@pytest.fixture
def assessment(engagement) -> TpiAssessment:
    return TpiAssessment.objects.create(engagement=engagement, title="評価1")


@pytest.fixture
def key_area(db) -> TpiKeyArea:
    return TpiKeyArea.objects.create(name="テスト戦略")


def _answer(assessment, checkpoint, result):
    TpiAnswer.objects.create(assessment=assessment, checkpoint=checkpoint, result=result)


@pytest.mark.django_db
class TestLevelStatus:
    def test_controlled_fully_met_only_reaches_controlled(self, assessment, key_area):
        c1 = TpiCheckpoint.objects.create(key_area=key_area, level="controlled", text="c1")
        c2 = TpiCheckpoint.objects.create(key_area=key_area, level="controlled", text="c2")
        e1 = TpiCheckpoint.objects.create(key_area=key_area, level="efficient", text="e1")
        _answer(assessment, c1, TpiAnswer.Result.MET)
        _answer(assessment, c2, TpiAnswer.Result.MET)
        _answer(assessment, e1, TpiAnswer.Result.NOT_MET)

        status = level_status(assessment, key_area)
        assert status["achieved_level"] == "controlled"

    def test_all_levels_fully_met_reaches_optimizing(self, assessment, key_area):
        for level in ("controlled", "efficient", "optimizing"):
            cp = TpiCheckpoint.objects.create(key_area=key_area, level=level, text=level)
            _answer(assessment, cp, TpiAnswer.Result.MET)

        status = level_status(assessment, key_area)
        assert status["achieved_level"] == "optimizing"

    def test_lower_level_incomplete_blocks_upper_level(self, assessment, key_area):
        c1 = TpiCheckpoint.objects.create(key_area=key_area, level="controlled", text="c1")
        e1 = TpiCheckpoint.objects.create(key_area=key_area, level="efficient", text="e1")
        _answer(assessment, c1, TpiAnswer.Result.NOT_MET)
        _answer(assessment, e1, TpiAnswer.Result.MET)

        status = level_status(assessment, key_area)
        assert status["achieved_level"] is None

    def test_na_only_level_counts_as_complete(self, assessment, key_area):
        c1 = TpiCheckpoint.objects.create(key_area=key_area, level="controlled", text="c1")
        e1 = TpiCheckpoint.objects.create(key_area=key_area, level="efficient", text="e1")
        _answer(assessment, c1, TpiAnswer.Result.NA)
        _answer(assessment, e1, TpiAnswer.Result.NOT_MET)

        status = level_status(assessment, key_area)
        assert status["levels"]["controlled"]["complete"] is True
        assert status["achieved_level"] == "controlled"

    def test_level_with_zero_checkpoints_is_skipped_as_complete(self, assessment, key_area):
        c1 = TpiCheckpoint.objects.create(key_area=key_area, level="controlled", text="c1")
        o1 = TpiCheckpoint.objects.create(key_area=key_area, level="optimizing", text="o1")
        _answer(assessment, c1, TpiAnswer.Result.MET)
        _answer(assessment, o1, TpiAnswer.Result.MET)
        # efficientにはチェックポイントを作らない(0件)

        status = level_status(assessment, key_area)
        assert status["levels"]["efficient"]["total"] == 0
        assert status["levels"]["efficient"]["complete"] is True
        assert status["achieved_level"] == "optimizing"

    def test_all_levels_empty_key_area_has_no_achieved_level(self, assessment, key_area):
        status = level_status(assessment, key_area)
        assert status["achieved_level"] is None
        assert all(status["levels"][lv]["total"] == 0 for lv in ("controlled", "efficient", "optimizing"))
