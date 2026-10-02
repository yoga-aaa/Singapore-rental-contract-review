import io
import unittest
from unittest.mock import Mock

from scripts.run_v13_development_check import MeteredRequests


PAYLOAD = {"model": "synthetic-model", "max_tokens": 10, "messages": []}


class MeteredCheckTests(unittest.TestCase):
    def test_call_limit_stops_before_network(self):
        request = Mock(return_value=({}, {"total_tokens": 20}))
        meter = MeteredRequests(request, io.StringIO(), max_calls=1, max_tokens=10000)
        meter(PAYLOAD, "synthetic-key")
        with self.assertRaisesRegex(RuntimeError, "Before-call"):
            meter(PAYLOAD, "synthetic-key")
        self.assertEqual(request.call_count, 1)

    def test_token_reservation_stops_before_network(self):
        request = Mock()
        meter = MeteredRequests(request, io.StringIO(), max_tokens=50)
        with self.assertRaisesRegex(RuntimeError, "Before-call"):
            meter(PAYLOAD, "synthetic-key")
        request.assert_not_called()

    def test_actual_usage_replaces_reservation(self):
        request = Mock(return_value=({}, {"total_tokens": 20}))
        meter = MeteredRequests(request, io.StringIO(), max_tokens=10000)
        meter(PAYLOAD, "synthetic-key")
        meter(PAYLOAD, "synthetic-key")
        self.assertEqual(meter.tokens, 40)

    def test_missing_usage_stops_and_records_response_without_key(self):
        log = io.StringIO()
        meter = MeteredRequests(Mock(return_value=({"label": "example"}, None)), log)
        with self.assertRaisesRegex(RuntimeError, "usage is missing"):
            meter(PAYLOAD, "synthetic-secret")
        self.assertIn("example", log.getvalue())
        self.assertNotIn("synthetic-secret", log.getvalue())
        with self.assertRaisesRegex(RuntimeError, "Before-call"):
            meter(PAYLOAD, "synthetic-secret")

    def test_exceeded_provider_reservation_stops_after_recording(self):
        log = io.StringIO()
        used = MeteredRequests.reservation(PAYLOAD) + 1
        meter = MeteredRequests(Mock(return_value=({}, {"total_tokens": used})), log)
        with self.assertRaisesRegex(RuntimeError, "exceeded the reservation"):
            meter(PAYLOAD, "synthetic-key")
        self.assertTrue(log.getvalue())


if __name__ == "__main__":
    unittest.main()
