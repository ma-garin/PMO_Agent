import csv

from django.http import StreamingHttpResponse

BOM = "﻿"

# Excel/Sheetsが数式として解釈しうる先頭文字。これらで始まるセルは無効化する。
# 参考: CSVインジェクション(CWE-1236)。チケット概要等は外部システム由来のため必須。
_RISKY_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def sanitize_cell(value) -> str:
    """CSV数式インジェクション対策。危険な先頭文字を持つ値の前にシングルクォートを付ける。"""
    text = "" if value is None else str(value)
    if text and text[0] in _RISKY_PREFIXES:
        return "'" + text
    return text


class _Echo:
    def write(self, value):
        return value


def csv_response(filename: str, header: list[str], rows) -> StreamingHttpResponse:
    writer = csv.writer(_Echo())

    def generate():
        yield BOM.encode("utf-8")
        yield writer.writerow(header).encode("utf-8")
        for row in rows:
            safe_row = [sanitize_cell(cell) for cell in row]
            yield writer.writerow(safe_row).encode("utf-8")

    response = StreamingHttpResponse(generate(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
