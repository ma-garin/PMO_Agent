"""F-4: 数値入力バリデーションのテスト。"""

import pytest

from config.http_utils import parse_int, parse_optional_number


@pytest.mark.unit
class TestParseInt:
    def test_valid_number(self):
        assert parse_int("5", 0) == 5

    def test_non_numeric_returns_default(self):
        assert parse_int("abc", 3) == 3
        assert parse_int("", 3) == 3
        assert parse_int(None, 3) == 3

    def test_clamps_to_range(self):
        assert parse_int("99", 3, minimum=1, maximum=5) == 5
        assert parse_int("-4", 3, minimum=1, maximum=5) == 1
        assert parse_int("4", 3, minimum=1, maximum=5) == 4


@pytest.mark.unit
class TestParseOptionalNumber:
    def test_empty_is_none(self):
        assert parse_optional_number("", as_float=False) is None
        assert parse_optional_number(None, as_float=True) is None

    def test_non_numeric_is_none(self):
        assert parse_optional_number("abc", as_float=True) is None

    def test_int_and_float(self):
        assert parse_optional_number("7", as_float=False) == 7
        assert parse_optional_number("80.5", as_float=True) == 80.5
