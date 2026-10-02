import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.evaluate import evaluate
from src.live_review import precheck_abstention_reason, review_clause, validate_output
from src.retrieval import RetrievedChunk


class DevelopmentGuardrailTests(unittest.TestCase):
    def test_generic_and_unallocated_repair_terms_abstain_without_api(self):
        self.assertIsNotNone(precheck_abstention_reason("The parties will cooperate respectfully throughout the tenancy."))
        self.assertIsNotNone(precheck_abstention_reason("Repairs shall be arranged by the responsible party."))
        self.assertIsNotNone(precheck_abstention_reason("Maintenance will be handled fairly by the parties."))
        self.assertIsNone(precheck_abstention_reason("The Tenant pays repairs up to S$200 per item."))
        self.assertIsNone(precheck_abstention_reason("Anyone connected with the Tenant may reside in the property."))
        self.assertIsNone(precheck_abstention_reason("The Landlord may end this tenancy today."))

        with patch("src.live_review._request_openrouter") as request:
            result = review_clause("HDB", "Repairs shall be arranged by the responsible party.", None)
        self.assertTrue(result.abstained)
        request.assert_not_called()

    def test_citation_must_match_source_and_page_as_a_pair(self):
        chunks = [
            RetrievedChunk("CEA_HDB_TA", "HDB", "tenancy_agreement_template", "HDB", 5, "Page 5", "Security deposit reference text.", 1.0, topics=("security_deposit",)),
            RetrievedChunk("CEA_HDB_CHECK", "HDB", "tenant_checklist", "HDB check", 9, "Page 9", "Unrelated checklist excerpt for a tenant.", 1.0, topics=("security_deposit",)),
        ]
        raw = {
            "label": "review_required",
            "clause_category": "security_deposit",
            "reason": "The deposit notice process materially differs from the cited template.",
            "follow_up_question": "Will deductions require written notice first?",
            "source_id": "CEA_HDB_TA",
            "source_section": "Page 9",
            "evidence": [{
                "source_id": "CEA_HDB_TA", "source_section": "Page 9",
                "topic": "security_deposit", "quote": "Security deposit reference text.",
            }],
            "abstained": False,
        }
        self.assertTrue(validate_output(raw, chunks).abstained)
        raw["source_section"] = "Page 5"
        raw["evidence"][0]["source_section"] = "Page 5"
        self.assertFalse(validate_output(raw, chunks).abstained)

    def test_unsafe_non_abstention_uses_abstain_cases_as_denominator(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            truth = base / "truth.csv"
            predictions = base / "predictions.csv"
            registry = base / "registry.csv"
            with truth.open("w", encoding="utf-8", newline="") as file:
                writer = csv.DictWriter(file, fieldnames=["case_id", "ground_truth_label"])
                writer.writeheader()
                writer.writerows([
                    {"case_id": "A", "ground_truth_label": "insufficient_evidence"},
                    {"case_id": "B", "ground_truth_label": "review_required"},
                ])
            with predictions.open("w", encoding="utf-8", newline="") as file:
                writer = csv.DictWriter(file, fieldnames=["case_id", "predicted_label", "source_id", "source_section"])
                writer.writeheader()
                writer.writerows([
                    {"case_id": "A", "predicted_label": "review_required", "source_id": "CEA", "source_section": "Page 1"},
                    {"case_id": "B", "predicted_label": "review_required", "source_id": "CEA", "source_section": "Page 1"},
                ])
            with registry.open("w", encoding="utf-8", newline="") as file:
                writer = csv.DictWriter(file, fieldnames=["source_id"])
                writer.writeheader()
                writer.writerow({"source_id": "CEA"})
            summary = evaluate(truth, predictions, registry)
        self.assertEqual(summary["unsafe_non_abstention_rate"], 1.0)
        self.assertIsNone(summary["citation_validity"])
        self.assertEqual(summary["citation_locator_validity"], 1.0)
        self.assertEqual(summary["unsafe_non_abstention_count"], 1)
        self.assertEqual(summary["insufficient_evidence_count"], 1)


if __name__ == "__main__":
    unittest.main()
