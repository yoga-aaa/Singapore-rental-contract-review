import sys
import unittest
from unittest.mock import patch

from src.direct_common import direct_notice_delivery_match, direct_unrestricted_termination_review
from src.direct_remaining import direct_occupant_documents_match
from src.index_paths import CURRENT_SECTION_INDEX, LEGACY_SECTION_INDEX
from src.retrieval import LocalBM25Retriever


@unittest.skipUnless(CURRENT_SECTION_INDEX.exists(), "Build the current layout index first")
class CurrentIndexIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.retriever = LocalBM25Retriever.from_jsonl(CURRENT_SECTION_INDEX)

    def test_notice_delivery_uses_actual_personal_service_clause(self):
        text = "A notice can be delivered personally or sent by Certificate of Posting to the stated address."
        for housing, expected in (("HDB", "11.1"), ("Private Residential", "12.1")):
            with self.subTest(housing=housing):
                chunks = self.retriever.search(text, housing, limit=6)
                result = direct_notice_delivery_match(text, chunks)
                self.assertIsNotNone(result)
                self.assertIn("Clause " + expected + " /", result.source_section)

    def test_unrestricted_termination_uses_actual_breach_clause(self):
        text = "The Landlord may end the tenancy at any time for any reason by a text message on the same day."
        for housing, expected in (("HDB", "8.1"), ("Private Residential", "7.1")):
            with self.subTest(housing=housing):
                chunks = self.retriever.search(text, housing, limit=6)
                result = direct_unrestricted_termination_review(text, chunks)
                self.assertIsNotNone(result)
                self.assertIn("Clause " + expected + " /", result.source_section)

    def test_occupier_documents_uses_actual_production_clause(self):
        text = "The Tenant shall produce foreign occupier documents showing lawful residence when required by the Landlord."
        for housing in ("HDB", "Private Residential"):
            with self.subTest(housing=housing):
                chunks = self.retriever.search(text, housing, limit=6)
                result = direct_occupant_documents_match(text, chunks)
                self.assertIsNotNone(result)
                self.assertIn("Clause 3.2 /", result.source_section)

    def test_air_conditioning_retrieval_never_mixes_housing_types(self):
        for housing in ("HDB", "Private Residential"):
            chunks = self.retriever.search(
                "maintenance of air-conditioning units and servicing every three months",
                housing, limit=6,
            )
            self.assertTrue(chunks)
            self.assertTrue(all(chunk.housing_type == housing for chunk in chunks))
            self.assertTrue(any(chunk.clause_id == "4.4" for chunk in chunks))


class VersionedEntryPointTests(unittest.TestCase):
    def test_historical_evaluation_keeps_legacy_index(self):
        from scripts.score_external_evaluation import INDEX as external_index
        from scripts.run_v13_development_check import INDEX as development_index
        self.assertEqual(external_index, LEGACY_SECTION_INDEX)
        self.assertEqual(development_index, LEGACY_SECTION_INDEX)

    def test_current_live_cli_defaults_to_current_index_before_any_model_call(self):
        from scripts import review_clause_live
        with patch.object(sys, "argv", ["review_clause_live.py", "HDB", "Synthetic input", "--offline"]):
            with patch.object(review_clause_live.LocalBM25Retriever, "from_jsonl",
                              side_effect=RuntimeError("stop before review")) as loader:
                with self.assertRaisesRegex(RuntimeError, "stop before review"):
                    review_clause_live.main()
        loader.assert_called_once_with(CURRENT_SECTION_INDEX)


if __name__ == "__main__":
    unittest.main()
