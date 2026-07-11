import csv

from django.http import StreamingHttpResponse

BOM = "﻿"


class _Echo:
    def write(self, value):
        return value


def csv_response(filename: str, header: list[str], rows) -> StreamingHttpResponse:
    writer = csv.writer(_Echo())

    def generate():
        yield BOM.encode("utf-8")
        yield writer.writerow(header).encode("utf-8")
        for row in rows:
            yield writer.writerow(row).encode("utf-8")

    response = StreamingHttpResponse(generate(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
