"""HTTP adapter checks: unchanged offline results and no credential/model access."""
import json
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    from fastapi.testclient import TestClient
    from webapp import app, source_status
except ImportError:
    TestClient = None

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipIf(TestClient is None, "Install requirements-web.txt for HTTP adapter tests")
class PublicOfflineTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.data = {
            "housing_type": "HDB", "review_version": "v17",
            "synthetic_confirmed": True, "extraction_confirmed": True,
            "clauses": [{"clause_id": "CL_01", "pages": [],
                         "text": "All matters will be managed appropriately by the parties."}]
        }

    def post(self, data=None):
        return self.client.post("/api/review", json=data if data is not None else self.data)

    def test_home_and_assets(self):
        for path, text in [("/", "OFFLINE DEMONSTRATION"), ("/app.js", "renderReport"),
                           ("/styles.css", "--ink")]:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertIn(text, response.text)

    def test_security_headers(self):
        response = self.client.get("/")
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")
        self.assertIn("script-src 'self'", response.headers["content-security-policy"])

    def test_health_verified_sources(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["template_sections"], 135)
        self.assertEqual(response.json()["official_sections"], 49)
        self.assertFalse(response.json()["live_enabled"])

    def test_missing_sources_fail_closed(self):
        source_status.cache_clear()
        try:
            with patch("webapp.load_retriever", side_effect=ValueError("Internal path")):
                response = self.client.get("/api/health")
                self.assertEqual(response.status_code, 503)
                self.assertNotIn("Internal path", response.text)
        finally:
            source_status.cache_clear()

    def test_only_demo_inputs_in_config(self):
        data = self.client.get("/api/config").json()
        self.assertEqual(len(data["examples"]), 5)
        self.assertEqual(len(data["sources"]), 9)
        self.assertFalse(data["live_enabled"])
        self.assertNotIn("OPENROUTER", json.dumps(data))

    def test_five_original_examples_unchanged_and_zero_credits(self):
        samples = json.loads((ROOT / "data/demo_examples.json").read_text(encoding="utf-8"))
        expected = ["review_required", "no_material_difference_found", "insufficient_evidence",
                    "no_material_difference_found", "model_needed"]
        with patch("src.application.local_api_key", side_effect=AssertionError("No key access")), \
             patch("src.live_review._request_openrouter", side_effect=AssertionError("No model")), \
             patch("src.review_v18._request_openrouter", side_effect=AssertionError("No model")), \
             patch.dict("os.environ", {"RENTAL_ENABLE_LIVE": "1", "OPENROUTER_API_KEY": "not-a-real-key"}):
            for sample, label in zip(samples, expected):
                with self.subTest(sample=sample["title"]):
                    data = {**self.data, "housing_type": sample["housing_type"],
                            "clauses": [{"clause_id": "CL_01", "pages": [], "text": sample["clauses"][0]}]}
                    response = self.post(data)
                    self.assertEqual(response.status_code, 200, response.text)
                    report = response.json()
                    row = report["clauses"][0]
                    self.assertEqual(row["result"]["label"] if row["result"] else row["status"], label)
                    self.assertEqual(report["accounting"]["api_calls"], 0)
                    self.assertEqual(report["accounting"]["cost_usd"], "0")
                    self.assertEqual(report["mode"], "offline")

    def test_v18_retrieval_reports_failed_historical_run_not_new_model_result(self):
        response = self.post({**self.data, "review_version": "v18"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn("failed acceptance", response.json()["evaluation_status"])
        self.assertEqual(response.json()["accounting"]["api_calls"], 0)

    def test_recorded_v18_and_v19_fail_with_later_candidates_unmeasured(self):
        data=self.client.get('/api/config').json()
        summary=data['recorded_v18']
        self.assertFalse(summary['target_met'])
        self.assertEqual(summary['risk_recall']['numerator'],8)
        self.assertEqual(summary['risk_recall']['denominator'],14)
        self.assertEqual(summary['false_positives'],2)
        self.assertEqual(summary['unsafe_non_abstention']['numerator'],2)
        self.assertEqual(summary['accounting']['cost_usd'],'0.6162670')
        latest=data['recorded_v19']
        self.assertEqual(latest['risk_recall']['numerator'],5)
        self.assertEqual(latest['risk_recall']['denominator'],14)
        self.assertEqual(latest['false_positives'],0)
        self.assertEqual(latest['unsafe_non_abstention']['numerator'],0)
        self.assertEqual(latest['substantive_citation_support']['numerator'],2)
        self.assertEqual(latest['substantive_citation_support']['denominator'],5)
        self.assertEqual(latest['accounting']['cost_usd'],'0.7858850')
        self.assertFalse(latest['target_met'])
        self.assertIn('No v20 model predictions',latest['v20_status'])
        self.assertIn('v22 paid regression failed acceptance',latest['v22_status'])
        current=data['recorded_v22']
        self.assertFalse(current['target_met'])
        self.assertEqual(current['risk_recall'],{'numerator':6,'denominator':14,'rate':6/14})
        self.assertEqual(current['false_positives'],0)
        self.assertEqual(current['unsafe_non_abstention']['numerator'],0)
        self.assertEqual(current['substantive_citation_support']['numerator'],6)
        self.assertEqual(current['substantive_citation_support']['denominator'],6)
        self.assertIn('Owner confirmation pending',current['citation_audit_status'])
        self.assertEqual(current['accounting']['api_calls'],57)
        self.assertEqual(current['accounting']['cost_usd'],'0.5746430')
        candidate=data['recorded_v25']
        self.assertTrue(candidate['target_met'])
        self.assertEqual(candidate['status'],'measured_gates_met_owner_confirmation_pending')
        self.assertEqual(candidate['risk_recall'],{'numerator':13,'denominator':14,'rate':13/14})
        self.assertEqual(candidate['false_positives'],0)
        self.assertEqual(candidate['unsafe_non_abstention']['numerator'],0)
        self.assertEqual(candidate['substantive_citation_support']['numerator'],13)
        self.assertEqual(candidate['accounting']['cost_usd'],'0.6028355')
        self.assertFalse(data['live_enabled'])
        self.assertEqual(data['recorded_v23']['risk_recall']['numerator'],9)
        self.assertEqual(data['recorded_v24']['risk_recall']['numerator'],4)
        home=self.client.get('/').text
        for text in ['Recorded v18','8/14 · 57.14%','0/12 · 0%','v18 failed acceptance',
                     'Recorded v19','2/5 · 40%','Recorded v22','6/14 · 42.86%','6/6 · 100%*',
                     'not an accepted final product','unmeasured candidates','Latest v25','13/14 · 92.86%',
                     'Owner citation confirmation is pending','do not execute v25']:
            self.assertIn(text,home)

    def test_live_parameters_rejected(self):
        for key, value in [("live", True), ("mode", "live"), ("spending_confirmed", True),
                           ("api_key", "not-a-real-key"), ("request", {})]:
            with self.subTest(key=key):
                self.assertEqual(self.post({**self.data, key: value}).status_code, 422)

    def test_false_or_string_confirmations_rejected(self):
        for key in ("synthetic_confirmed", "extraction_confirmed"):
            for value in (False, "true", 1, None):
                with self.subTest(key=key, value=value):
                    self.assertIn(self.post({**self.data, key: value}).status_code, (400, 422))

    def test_invalid_housing_and_versions(self):
        for data in ({**self.data, "housing_type": "Commercial"}, {**self.data, "review_version": "v99"}):
            self.assertEqual(self.post(data).status_code, 422)

    def test_personal_identifiers_blocked(self):
        self.data["clauses"][0]["text"] = "The Tenant is S1234567A and shall pay rent."
        response = self.post()
        self.assertEqual(response.status_code, 400)
        self.assertNotIn("S1234567A", response.text)

    def test_duplicate_and_invalid_clause_ids(self):
        data = {**self.data, "clauses": self.data["clauses"] * 2}
        self.assertEqual(self.post(data).status_code, 422)
        self.data["clauses"][0]["clause_id"] = "../.env"
        self.assertEqual(self.post().status_code, 422)

    def test_clause_and_document_limits(self):
        self.data["clauses"][0]["text"] = "a" * 6001
        self.assertEqual(self.post().status_code, 422)
        self.data["clauses"] = [{"clause_id": "C_" + str(i), "text": "a" * 6000, "pages": []} for i in range(20)]
        self.assertEqual(self.post().status_code, 413)
        self.data["clauses"] = [{"clause_id": "C_" + str(i), "text": "The Tenant pays rent.", "pages": []} for i in range(21)]
        self.assertEqual(self.post().status_code, 422)

    def test_body_limits_and_content_type(self):
        response = self.client.post("/api/review", content=b"x" * 500001,
                                    headers={"content-type": "application/json"})
        self.assertEqual(response.status_code, 413)
        self.assertEqual(self.client.post("/api/review", content=b"{}", headers={"content-type": "text/plain"}).status_code, 415)
        self.assertEqual(self.client.post("/api/review", content=b"{", headers={"content-type": "application/json"}).status_code, 422)

    def test_pdf_extract_and_review(self):
        payload = (ROOT / "data/demo_pdfs/demo_02.pdf").read_bytes()
        response = self.client.post("/api/extract?housing_type=HDB", content=payload,
                                    headers={"content-type": "application/pdf", "x-synthetic-confirmed": "true"})
        self.assertEqual(response.status_code, 200, response.text)
        self.data["clauses"] = response.json()["clauses"]
        report = self.post().json()
        self.assertEqual(report["clauses"][0]["result"]["label"], "no_material_difference_found")
        self.assertEqual(report["accounting"]["api_calls"], 0)

    def test_pdf_requires_synthetic_confirmation_and_limits(self):
        self.assertEqual(self.client.post("/api/extract?housing_type=HDB", content=b"%PDF").status_code, 400)
        headers = {"content-type": "application/pdf", "x-synthetic-confirmed": "true"}
        self.assertEqual(self.client.post("/api/extract?housing_type=HDB", content=b"bad", headers=headers).status_code, 400)
        self.assertEqual(self.client.post("/api/extract?housing_type=HDB", content=b"%PDF" + b"x" * 2_000_000, headers=headers).status_code, 413)

    def test_fixed_demo_downloads_only(self):
        self.assertEqual(self.client.get("/api/demo-pdf/2").status_code, 200)
        self.assertEqual(self.client.get("/api/demo-pdf/99").status_code, 422)

    def test_no_private_or_source_file_routes(self):
        for path in ("/.env", "/submission/Blind_Review_v18.zip", "/docs/demo_script_bilingual.md",
                     "/data/external_label_readjudication_v14.json", "/data/official_sources_v18/index_v18.jsonl"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)


if __name__ == "__main__":
    unittest.main()
