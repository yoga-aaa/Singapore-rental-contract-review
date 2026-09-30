import unittest

from src.live_review import validate_output
from src.retrieval import RetrievedChunk


CHUNK = RetrievedChunk(
    source_id="CEA_HDB_TA",
    housing_type="HDB",
    source_kind="tenancy_agreement_template",
    title="HDB template",
    page_number=5,
    section="Page 5",
    text="Security deposit reference text.",
    score=1.0,
)


class LiveReviewTests(unittest.TestCase):
    def test_printed_pdf_page_number_is_valid_when_the_retrieved_pdf_page_has_a_cover_offset(self):
        raw = {
            "label": "review_required",
            "clause_category": "security_deposit",
            "reason": "The notice process differs.",
            "follow_up_question": "Can you clarify the notice process?",
            "source_id": "CEA_HDB_TA",
            "source_section": "Page 4",
            "abstained": False,
        }
        result = validate_output(raw, [CHUNK])
        self.assertEqual(result.label, "review_required")
        self.assertFalse(result.abstained)

    def test_unknown_source_is_rejected(self):
        raw = {
            "label": "review_required",
            "clause_category": "security_deposit",
            "reason": "The notice process differs.",
            "follow_up_question": "Can you clarify the notice process?",
            "source_id": "UNKNOWN",
            "source_section": "Page 4",
            "abstained": False,
        }
        result = validate_output(raw, [CHUNK])
        self.assertTrue(result.abstained)


if __name__ == "__main__":
    unittest.main()
