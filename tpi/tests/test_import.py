import pytest
from django.core.management import call_command

from tpi.models import TpiCheckpoint, TpiKeyArea


@pytest.mark.django_db
class TestImportTpiCheckpoints:
    def test_valid_csv_creates_key_areas_and_checkpoints(self, tmp_path):
        csv_path = tmp_path / "checkpoints.csv"
        csv_path.write_text(
            "key_area,level,text,order\n"
            "テスト戦略,controlled,戦略が文書化されている,1\n"
            "テスト戦略,efficient,戦略がレビューされている,2\n",
            encoding="utf-8",
        )
        call_command("import_tpi_checkpoints", str(csv_path))

        assert TpiKeyArea.objects.filter(name="テスト戦略").exists()
        assert TpiCheckpoint.objects.count() == 2

    def test_invalid_level_row_is_skipped(self, tmp_path):
        csv_path = tmp_path / "checkpoints.csv"
        csv_path.write_text(
            "key_area,level,text,order\n"
            "テスト戦略,controlled,正常行,1\n"
            "テスト戦略,invalid_level,不正行,2\n",
            encoding="utf-8",
        )
        call_command("import_tpi_checkpoints", str(csv_path))

        assert TpiCheckpoint.objects.count() == 1

    def test_duplicate_rows_are_not_duplicated(self, tmp_path):
        csv_path = tmp_path / "checkpoints.csv"
        csv_path.write_text(
            "key_area,level,text,order\n"
            "テスト戦略,controlled,重複行,1\n"
            "テスト戦略,controlled,重複行,1\n",
            encoding="utf-8",
        )
        call_command("import_tpi_checkpoints", str(csv_path))

        assert TpiCheckpoint.objects.count() == 1
