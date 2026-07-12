"""F-9: CSV数式インジェクション対策のテスト。"""

import pytest

from config.csv_utils import csv_response, sanitize_cell


@pytest.mark.unit
class TestSanitizeCell:
    @pytest.mark.parametrize("payload", ["=SUM(A1:A2)", "+1+1", "-2+3", "@cmd", "\tTAB", "\rCR"])
    def test_risky_prefixes_are_neutralized(self, payload):
        result = sanitize_cell(payload)
        assert result.startswith("'")
        assert result == "'" + payload

    def test_normal_values_pass_through(self):
        assert sanitize_cell("PROJ-1") == "PROJ-1"
        assert sanitize_cell("ログイン画面の不具合") == "ログイン画面の不具合"
        assert sanitize_cell("2026-07-12") == "2026-07-12"

    def test_none_becomes_empty_string(self):
        assert sanitize_cell(None) == ""

    def test_non_string_is_stringified(self):
        assert sanitize_cell(42) == "42"

    def test_embedded_but_not_leading_symbol_is_untouched(self):
        # 先頭以外の記号は無害なのでそのまま
        assert sanitize_cell("A=B") == "A=B"


@pytest.mark.unit
class TestCsvResponse:
    def _body(self, response) -> str:
        return b"".join(response.streaming_content).decode("utf-8")

    def test_formula_row_is_sanitized_in_output(self):
        response = csv_response("t.csv", ["概要"], [["=SUM(1,2)"]])
        body = self._body(response)
        assert "'=SUM(1,2)" in body
        # 生の数式(先頭=)が単独では現れない
        assert ",=SUM" not in body

    def test_header_and_normal_rows_render(self):
        response = csv_response("t.csv", ["ID", "概要"], [["PROJ-1", "正常な概要"]])
        body = self._body(response)
        assert "ID" in body
        assert "PROJ-1" in body
        assert "正常な概要" in body

    def test_content_disposition_and_type(self):
        response = csv_response("export.csv", ["a"], [])
        assert response["Content-Disposition"] == 'attachment; filename="export.csv"'
        assert "text/csv" in response["Content-Type"]
