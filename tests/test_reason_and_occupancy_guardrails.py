import unittest

from src.live_review import precheck_abstention_reason, validate_output
from src.retrieval import RetrievedChunk


class ReasonAndOccupancyGuardrailTests(unittest.TestCase):
    def test_property_use_does_not_imply_occupancy(self):
        ambiguous = "The property may be used by anyone connected with the Tenant from time to time."
        self.assertIsNotNone(precheck_abstention_reason(ambiguous))
        explicit = "The premises may be occupied only by the named Tenant and occupants."
        self.assertIsNone(precheck_abstention_reason(explicit))

    def test_review_needs_a_concrete_difference_after_saying_terms_align(self):
        chunk = RetrievedChunk(
            "CEA_HDB_TA", "HDB", "tenancy_agreement_template", "Template", 11,
            "Clause 8.2 / PDF page 11",
            "The Landlord may terminate after written notice and fourteen days to rectify a breach.",
            1.0, clause_id="8.2", topics=("termination_notice",),
        )
        raw = {
            "label": "review_required", "clause_category": "termination_notice",
            "reason": "The clause aligns with the template's written notice and fourteen-day remedy period. However, more conditions may be unclear.",
            "follow_up_question": "", "source_id": chunk.source_id,
            "source_section": chunk.section, "abstained": False,
            "evidence": [{"source_id": chunk.source_id, "source_section": chunk.section,
                          "topic": "termination_notice",
                          "quote": "The Landlord may terminate after written notice and fourteen days to rectify a breach."}],
        }
        self.assertTrue(validate_output(raw, [chunk], clause_text="Termination after notice and fourteen days.").abstained)


if __name__ == "__main__":
    unittest.main()
