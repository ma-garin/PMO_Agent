import asyncio
import json
import logging

from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase

from config.observability import (
    JsonFormatter,
    RequestContextFilter,
    RequestIDMiddleware,
    bind_request_id,
    get_request_id,
    reset_request_id,
    valid_request_id,
)


class RequestIDMiddlewareTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_accepts_safe_incoming_id_and_exposes_it_during_request(self):
        observed = []

        def view(request):
            observed.append((request.request_id, get_request_id()))
            return HttpResponse("ok")

        response = RequestIDMiddleware(view)(
            self.factory.get("/", headers={"X-Request-ID": "edge_01.trace-2"})
        )

        self.assertEqual(response["X-Request-ID"], "edge_01.trace-2")
        self.assertEqual(observed, [("edge_01.trace-2", "edge_01.trace-2")])
        self.assertIsNone(get_request_id())

    def test_replaces_unsafe_incoming_id(self):
        response = RequestIDMiddleware(lambda request: HttpResponse("ok"))(
            self.factory.get("/", headers={"X-Request-ID": "bad\nforged-log"})
        )

        generated = response["X-Request-ID"]
        self.assertNotEqual(generated, "bad\nforged-log")
        self.assertTrue(valid_request_id(generated))

    def test_replaces_oversized_incoming_id(self):
        response = RequestIDMiddleware(lambda request: HttpResponse("ok"))(
            self.factory.get("/", headers={"X-Request-ID": "a" * 129})
        )
        self.assertNotEqual(response["X-Request-ID"], "a" * 129)
        self.assertTrue(valid_request_id(response["X-Request-ID"]))

    def test_context_is_reset_when_view_raises(self):
        def view(request):
            raise RuntimeError("boom")

        with self.assertRaises(RuntimeError):
            RequestIDMiddleware(view)(self.factory.get("/"))
        self.assertIsNone(get_request_id())

    def test_async_request_keeps_and_then_resets_context(self):
        observed = []

        async def view(request):
            await asyncio.sleep(0)
            observed.append(get_request_id())
            return HttpResponse("ok")

        async def run_request():
            request = self.factory.get("/", headers={"X-Request-ID": "async-1"})
            return await RequestIDMiddleware(view)(request)

        response = asyncio.run(run_request())
        self.assertEqual(response["X-Request-ID"], "async-1")
        self.assertEqual(observed, ["async-1"])
        self.assertIsNone(get_request_id())


class StructuredLoggingTests(SimpleTestCase):
    def test_filter_and_formatter_add_request_context(self):
        token = bind_request_id("req-42")
        try:
            record = logging.LogRecord(
                name="pmo_agent.test",
                level=logging.WARNING,
                pathname=__file__,
                lineno=1,
                msg="処理 %s",
                args=("失敗",),
                exc_info=None,
            )
            self.assertTrue(RequestContextFilter().filter(record))
            payload = json.loads(JsonFormatter().format(record))
        finally:
            reset_request_id(token)

        self.assertEqual(payload["level"], "WARNING")
        self.assertEqual(payload["logger"], "pmo_agent.test")
        self.assertEqual(payload["message"], "処理 失敗")
        self.assertEqual(payload["request_id"], "req-42")
        self.assertIn("timestamp", payload)

    def test_filter_uses_placeholder_outside_request(self):
        record = logging.LogRecord("test", logging.INFO, __file__, 1, "ok", (), None)
        RequestContextFilter().filter(record)
        self.assertEqual(record.request_id, "-")

    def test_filter_preserves_explicit_request_id(self):
        record = logging.LogRecord("test", logging.INFO, __file__, 1, "ok", (), None)
        record.request_id = "job-17"
        RequestContextFilter().filter(record)
        self.assertEqual(record.request_id, "job-17")
