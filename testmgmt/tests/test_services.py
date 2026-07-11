import pytest
from django.contrib.auth.models import User

from engagements.models import Engagement
from risks.models import RiskItem
from testmgmt.models import QualityGate, TestProgressEntry
from testmgmt.services import evaluate_gate, import_progress_csv, progress_summary


@pytest.fixture
def engagement(db) -> Engagement:
    owner = User.objects.create_user(username="pmo", password="x")
    return Engagement.objects.create(name="検証案件", owner=owner)


@pytest.mark.django_db
class TestProgressSummary:
    def test_execution_and_pass_rate_computed_from_latest_entry(self, engagement):
        TestProgressEntry.objects.create(
            engagement=engagement, test_level="システムテスト", date="2026-07-01",
            planned_cases=100, executed_cases=50, passed_cases=40,
        )
        TestProgressEntry.objects.create(
            engagement=engagement, test_level="システムテスト", date="2026-07-05",
            planned_cases=100, executed_cases=95, passed_cases=90,
        )
        rows = progress_summary(engagement)
        assert len(rows) == 1
        assert rows[0]["execution_rate"] == 95.0
        assert rows[0]["pass_rate"] == pytest.approx(94.7, abs=0.1)

    def test_zero_planned_does_not_divide_by_zero(self, engagement):
        TestProgressEntry.objects.create(
            engagement=engagement, test_level="単体テスト", date="2026-07-01",
            planned_cases=0, executed_cases=0, passed_cases=0,
        )
        rows = progress_summary(engagement)
        assert rows[0]["execution_rate"] == 0
        assert rows[0]["pass_rate"] == 0


@pytest.mark.django_db
class TestEvaluateGate:
    def test_execution_rate_boundary_exactly_met_passes(self, engagement):
        TestProgressEntry.objects.create(
            engagement=engagement, test_level="システムテスト", date="2026-07-01",
            planned_cases=100, executed_cases=95, passed_cases=95,
        )
        gate = QualityGate.objects.create(
            engagement=engagement, name="ゲート", criteria={"min_execution_rate": 95}
        )
        result = evaluate_gate(gate)
        assert result["results"][0]["ok"] is True
        assert result["all_ok"] is True

    def test_unknown_criteria_keys_are_ignored(self, engagement):
        gate = QualityGate.objects.create(
            engagement=engagement, name="ゲート", criteria={"unknown_key": 1}
        )
        result = evaluate_gate(gate)
        assert result["results"] == []
        assert result["all_ok"] is False

    def test_max_high_risks_criterion(self, engagement):
        RiskItem.objects.create(engagement=engagement, title="高リスク", probability=5, impact=5)
        gate = QualityGate.objects.create(
            engagement=engagement, name="ゲート", criteria={"max_high_risks": 0}
        )
        result = evaluate_gate(gate)
        assert result["results"][0]["ok"] is False


@pytest.mark.django_db
class TestImportProgressCsv:
    def test_valid_rows_imported(self, engagement):
        import io

        csv_content = (
            "test_level,date,planned_cases,executed_cases,passed_cases,note\n"
            "結合テスト,2026-07-01,50,30,28,順調\n"
        )
        file = io.BytesIO(csv_content.encode("utf-8"))
        imported, errors = import_progress_csv(engagement, file)
        assert imported == 1
        assert errors == []
        assert TestProgressEntry.objects.filter(test_level="結合テスト").exists()

    def test_duplicate_date_updates_existing_row(self, engagement):
        import io

        TestProgressEntry.objects.create(
            engagement=engagement, test_level="結合テスト", date="2026-07-01",
            planned_cases=10, executed_cases=5, passed_cases=5,
        )
        csv_content = (
            "test_level,date,planned_cases,executed_cases,passed_cases,note\n"
            "結合テスト,2026-07-01,50,40,38,更新\n"
        )
        file = io.BytesIO(csv_content.encode("utf-8"))
        import_progress_csv(engagement, file)
        assert TestProgressEntry.objects.filter(test_level="結合テスト").count() == 1
        entry = TestProgressEntry.objects.get(test_level="結合テスト")
        assert entry.executed_cases == 40
