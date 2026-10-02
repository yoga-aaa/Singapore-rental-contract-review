import hashlib
import json
import unittest

from scripts.replay_v13_development_check import RecordedRequests


class RecordedRequestTests(unittest.TestCase):
    def setUp(self):
        self.payload = {"model": "synthetic-model", "messages": [{"role": "user", "content": "Synthetic clause."}]}
        self.entry = {"case_id": "TEST_01", "request_sha256": hashlib.sha256(
            json.dumps(self.payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest(),
            "response": {"label": "review_required"}, "usage": {"total_tokens": 12}}

    def test_only_an_identical_request_can_reuse_a_response(self):
        replay = RecordedRequests([self.entry])
        replay.case_id = "TEST_01"
        response, usage = replay(self.payload, "not-a-real-key")
        self.assertEqual(usage["total_tokens"], 12)
        response["label"] = "changed-locally"
        self.assertEqual(self.entry["response"]["label"], "review_required")
        with self.assertRaisesRegex(RuntimeError, "unrecorded"):
            replay(self.payload, "not-a-real-key")

    def test_changed_request_or_case_is_rejected(self):
        for case_id, payload in (("TEST_02", self.payload), ("TEST_01", {**self.payload, "model": "different-model"})):
            replay = RecordedRequests([self.entry])
            replay.case_id = case_id
            with self.assertRaisesRegex(RuntimeError, "differs"):
                replay(payload, "not-a-real-key")
            self.assertEqual(replay.position, 0)


if __name__ == "__main__":
    unittest.main()
