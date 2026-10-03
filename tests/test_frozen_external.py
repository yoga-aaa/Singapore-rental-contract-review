import copy
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch

from src.frozen_external import (
    BudgetStop, MeteredTransport, byte_hash, safe_member, verify_authorization, verify_bundle,
)


CONFIG = {
    "models": {"draft": "openai/gpt-4.1", "verifier": "openai/gpt-4o"}, "retrieval_limit": 4,
    "max_model_calls": 40, "max_total_tokens": 200000, "max_cost_usd": "1.00",
    "prices": {
        "openai/gpt-4.1": {"input_usd_per_million": "2.00", "output_usd_per_million": "8.00",
                           "max_completion_tokens": 1600},
        "openai/gpt-4o": {"input_usd_per_million": "2.50", "output_usd_per_million": "10.00",
                          "max_completion_tokens": 1300},
    },
}
PAYLOAD = {"model": "openai/gpt-4.1", "temperature": 0, "max_tokens": 1600,
           "messages": [{"role": "system", "content": "Synthetic test instruction"},
                        {"role": "user", "content": "Synthetic contract data"}],
           "response_format": {"type": "json_schema", "json_schema": {"name": "test", "schema": {}}}}


def body():
    return {"id": "gen-synthetic", "model": "openai/gpt-4.1",
            "choices": [{"message": {"content": '{"synthetic": true}'}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120, "cost": 0.001}}


class TransportTests(unittest.TestCase):
    def meter(self, response=None, config=None):
        self.log = io.StringIO()
        self.request = Mock(return_value=body() if response is None else response)
        return MeteredTransport(copy.deepcopy(CONFIG if config is None else config), self.log, self.request)

    def test_both_model_stages_receive_price_caps_without_prompt_edits(self):
        meter = self.meter()
        for model, cap, input_rate, output_rate in (
            ("openai/gpt-4.1", 1600, 2.0, 8.0), ("openai/gpt-4o", 1300, 2.5, 10.0),
        ):
            payload = {**PAYLOAD, "model": model, "max_tokens": cap}
            parsed, usage = meter(payload, "synthetic-key-never-log")
            sent = self.request.call_args.args[0]
            self.assertEqual(sent["messages"], payload["messages"])
            self.assertEqual(sent["response_format"], payload["response_format"])
            self.assertEqual(sent["provider"]["max_price"],
                             {"prompt": input_rate, "completion": output_rate, "request": 0})
            self.assertEqual(sent["provider"]["only"], ["openai"])
            self.assertFalse(sent["provider"]["allow_fallbacks"])
            self.assertTrue(parsed["synthetic"])
            self.assertEqual(usage["total_tokens"], 120)
        self.assertEqual(meter.accounting()["api_calls"], 2)
        self.assertEqual(meter.accounting()["cost_usd"], "0.002")
        self.assertNotIn("synthetic-key-never-log", self.log.getvalue())
        self.assertNotIn("provider", PAYLOAD)

    def test_call_cap_stops_before_next_transport(self):
        config = {**CONFIG, "max_model_calls": 1}
        meter = self.meter(config=config)
        meter(PAYLOAD, "synthetic-key")
        with self.assertRaises(BudgetStop):
            meter(PAYLOAD, "synthetic-key")
        self.assertEqual(self.request.call_count, 1)

    def test_token_and_dollar_reservations_stop_before_transport(self):
        for update in ({"max_total_tokens": 10}, {"max_cost_usd": "0.000001"}):
            with self.subTest(update=update):
                meter = self.meter(config={**CONFIG, **update})
                with self.assertRaises(BudgetStop):
                    meter(PAYLOAD, "synthetic-key")
                self.request.assert_not_called()

    def test_missing_cost_stops_and_never_retries(self):
        response = body()
        del response["usage"]["cost"]
        meter = self.meter(response)
        with self.assertRaisesRegex(ValueError, "Missing provider cost"):
            meter(PAYLOAD, "synthetic-key")
        self.assertTrue(meter.unaccounted_attempt)
        with self.assertRaises(BudgetStop):
            meter(PAYLOAD, "synthetic-key")
        self.assertEqual(self.request.call_count, 1)

    def test_invalid_tokens_or_non_finite_cost_are_rejected(self):
        for update in ({"total_tokens": True}, {"total_tokens": 121}, {"cost": "NaN"}):
            response = body()
            response["usage"].update(update)
            meter = self.meter(response)
            with self.subTest(update=update), self.assertRaises(ValueError):
                meter(PAYLOAD, "synthetic-key")
            self.assertTrue(meter.stopped)

    def test_malformed_completion_still_accounts_charged_response(self):
        response = body()
        response["choices"][0]["message"]["content"] = "not valid JSON"
        meter = self.meter(response)
        with self.assertRaises(json.JSONDecodeError):
            meter(PAYLOAD, "synthetic-key")
        self.assertEqual(meter.accounting()["cost_usd"], "0.001")
        self.assertFalse(meter.unaccounted_attempt)
        self.assertTrue(meter.stopped)

    def test_charged_over_reservation_stops_without_hiding_spend(self):
        response = body()
        response["usage"]["cost"] = 1.1
        meter = self.meter(response)
        with self.assertRaises(BudgetStop):
            meter(PAYLOAD, "synthetic-key")
        self.assertEqual(meter.accounting()["cost_usd"], "1.1")
        self.assertTrue(meter.stopped)

    def test_network_failure_writes_attempt_and_stops_without_retry(self):
        meter = self.meter()
        self.request.side_effect = TimeoutError("synthetic timeout")
        with self.assertRaises(TimeoutError):
            meter(PAYLOAD, "synthetic-key")
        self.assertTrue(meter.unaccounted_attempt)
        events = [json.loads(line) for line in self.log.getvalue().splitlines()]
        self.assertEqual([event["event"] for event in events], ["attempt", "stop"])
        with self.assertRaises(BudgetStop):
            meter(PAYLOAD, "synthetic-key")
        self.assertEqual(self.request.call_count, 1)

    def test_unapproved_model_and_completion_limit_never_reach_transport(self):
        for update in ({"model": "unapproved/model"}, {"max_tokens": 1601}, {"tools": []}):
            meter = self.meter()
            with self.subTest(update=update), self.assertRaises(ValueError):
                meter({**PAYLOAD, **update}, "synthetic-key")
            self.request.assert_not_called()


class FreezeIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="frozen-evaluation-test-")
        self.root = Path(self.temporary.name).resolve()
        self.assertTrue(self.root.is_relative_to(Path(tempfile.gettempdir()).resolve()))
        self.addCleanup(self.temporary.cleanup)
        self.repo = self.root / "repo"
        self.bundle = self.root / "private/freeze"
        self.bundle.mkdir(parents=True)
        self.write(self.repo / "src/synthetic.py", "SYNTHETIC = True\n")
        self.write(self.repo / "scripts/run_frozen_external.py", "# synthetic harness\n")
        self.write(self.repo / "requirements.txt", "# synthetic fixture\n")
        cases = [{"case_id": f"NEW_{number:02d}", "housing_type": "HDB" if number <= 10 else "Private Residential",
                  "clause_text": "Synthetic clause: pay the agreed rent."} for number in range(1, 21)]
        self.write_json(self.bundle / "inputs/cases.json", cases)
        self.write_json(self.bundle / "configuration.json", CONFIG)
        # Intentionally invalid annotation JSON proves the predictor does not parse it.
        self.write(self.bundle / "scoring/labels.json", "GOLD_SENTINEL_NOT_MODEL_INPUT")
        self.write(self.bundle / "index.jsonl", "")
        runtime = [{"repo_path": relative, "sha256": byte_hash(self.repo / relative)}
                   for relative in ("src/synthetic.py", "scripts/run_frozen_external.py", "requirements.txt")]
        artifacts = [{"path": path.relative_to(self.bundle).as_posix(), "sha256": byte_hash(path)}
                     for path in sorted(self.bundle.rglob("*")) if path.is_file()]
        self.manifest = {
            "status": "labels_confirmed_api_authorization_pending", "hash_method": "sha256_exact_bytes",
            "case_count": 20, "runtime_files": runtime, "artifacts": artifacts,
            "input_path": "inputs/cases.json", "configuration_path": "configuration.json",
            "section_index_path": "index.jsonl",
        }
        self.save_manifest()

    @staticmethod
    def write(path, text):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def write_json(self, path, data):
        self.write(path, json.dumps(data))

    def save_manifest(self):
        self.write_json(self.bundle / "manifest.json", self.manifest)

    def test_preflight_does_not_parse_gold_or_read_key_or_run_predictions(self):
        from scripts import run_frozen_external
        with patch.object(run_frozen_external, "REPO_ROOT", self.repo), \
                patch.object(sys, "argv", ["run", "--bundle", str(self.bundle)]), \
                patch.object(run_frozen_external, "local_api_key", side_effect=AssertionError("key read")), \
                patch.object(run_frozen_external, "review_clause", side_effect=AssertionError("prediction")), \
                redirect_stdout(io.StringIO()) as output:
            run_frozen_external.main()
        self.assertEqual(json.loads(output.getvalue())["api_calls"], 0)
        self.assertFalse((self.bundle.parent / "run_v16").exists())

    def test_changed_cases_code_or_added_runtime_file_are_rejected(self):
        path = self.bundle / "inputs/cases.json"
        original = path.read_bytes()
        self.write(path, "[]")
        with self.assertRaisesRegex(ValueError, "Frozen artifact changed"):
            verify_bundle(self.bundle, self.repo)
        path.write_bytes(original)
        self.write(self.repo / "src/added.py", "SYNTHETIC = True")
        with self.assertRaisesRegex(ValueError, "Runtime file set changed"):
            verify_bundle(self.bundle, self.repo)
        (self.repo / "src/added.py").unlink()
        self.write(self.repo / "src/synthetic.py", "SYNTHETIC = False")
        with self.assertRaisesRegex(ValueError, "Runtime code changed"):
            verify_bundle(self.bundle, self.repo)

    def test_input_annotations_are_rejected_even_with_updated_hash(self):
        path = self.bundle / "inputs/cases.json"
        cases = json.loads(path.read_text())
        cases[0]["ground_truth_label"] = "review_required"
        self.write_json(path, cases)
        for entry in self.manifest["artifacts"]:
            if entry["path"] == "inputs/cases.json":
                entry["sha256"] = byte_hash(path)
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, "annotation"):
            verify_bundle(self.bundle, self.repo)

    def test_path_traversal_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "escapes"):
            safe_member(self.bundle, "../../outside.json")

    def test_live_mode_requires_new_authorization_before_key_or_output(self):
        from scripts import run_frozen_external
        with patch.object(run_frozen_external, "REPO_ROOT", self.repo), \
                patch.object(sys, "argv", ["run", "--bundle", str(self.bundle), "--live"]), \
                patch.object(run_frozen_external, "local_api_key", side_effect=AssertionError("key read")):
            with self.assertRaisesRegex(ValueError, "new human authorization"):
                run_frozen_external.main()
        self.assertFalse((self.bundle.parent / "run_v16").exists())

    def test_authorization_is_bound_to_exact_batch_and_dollar_cap(self):
        path = self.root / "authorization.synthetic.json"
        authorization = {"bundle_manifest_sha256": "synthetic-hash", "approved_by": "project_owner",
                         "synthetic_no_personal_data_confirmed": True, "send_to_openrouter_approved": True,
                         "authorization_message": "Synthetic test only", "authorized_at_utc": "synthetic",
                         "max_cost_usd": "1.00"}
        self.write_json(path, authorization)
        self.assertEqual(verify_authorization(path, "synthetic-hash", CONFIG), authorization)
        with self.assertRaisesRegex(ValueError, "another freeze"):
            verify_authorization(path, "different-hash", CONFIG)
        authorization["max_cost_usd"] = "0.50"
        self.write_json(path, authorization)
        with self.assertRaisesRegex(ValueError, "too low"):
            verify_authorization(path, "synthetic-hash", CONFIG)


if __name__ == "__main__":
    unittest.main()
