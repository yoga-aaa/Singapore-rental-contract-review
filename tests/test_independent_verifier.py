import unittest

from src.evidence_verifier import merged_usage
from src.live_review import apply_verification, direct_breach_termination_match
from src.retrieval import RetrievedChunk


CHUNK = RetrievedChunk(
    "CEA_PRIVATE_TA", "Private Residential", "tenancy_agreement_template", "Template", 12,
    "Clause 7.2 / PDF page 12",
    "if, upon the Landlord giving written notice to the Tenant of the Tenant's breach "
    "of any condition of this Agreement, and the Tenant fails to rectify such breach "
    "within fourteen (14) days from the service of such written notice.",
    1.0, clause_id="7.2", topics=("termination_notice",),
)


class IndependentVerifierTests(unittest.TestCase):
    def test_direct_match_uses_exact_reference_quote(self):
        clause = "The Landlord may terminate for a tenant breach after written notice and failure to rectify within fourteen days."
        result = direct_breach_termination_match(clause, [CHUNK])
        self.assertIsNotNone(result)
        self.assertEqual(result.label, "no_material_difference_found")
        self.assertIn(result.evidence[0]["quote"], CHUNK.text)
        self.assertFalse(result.api_called)

    def test_direct_match_rejects_unrestricted_termination(self):
        clause = "The Landlord may terminate at any time after written notice and failure to rectify within fourteen days."
        self.assertIsNone(direct_breach_termination_match(clause, [CHUNK]))

    def test_verifier_can_correct_a_vague_review_to_no_difference(self):
        quote = CHUNK.text.rstrip(".")
        raw = {
            "label": "review_required", "clause_category": "termination_notice",
            "reason": "The termination conditions might be different from the cited template.",
            "follow_up_question": "Why is this different?", "source_id": CHUNK.source_id,
            "source_section": CHUNK.section, "abstained": False,
            "evidence": [{"source_id": CHUNK.source_id, "source_section": CHUNK.section,
                          "topic": "termination_notice", "quote": quote}],
        }
        check = {"decision": "revise", "label": "no_material_difference_found",
                 "reason": "Both the contract and cited template require written notice and an unremedied breach after fourteen days.",
                 "issue": "The original label was unsupported."}
        result = apply_verification(raw, check, [CHUNK], {"total_tokens": 150, "api_calls": 2},
                                    "Termination after written notice and failure to rectify within fourteen days.")
        self.assertEqual(result.label, "no_material_difference_found")
        self.assertEqual(result.usage["api_calls"], 2)

    def test_usage_merges_both_model_calls(self):
        combined = merged_usage({"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
                                {"prompt_tokens": 80, "completion_tokens": 10, "total_tokens": 90})
        self.assertEqual(combined, {"prompt_tokens": 180, "completion_tokens": 30,
                                    "total_tokens": 210, "api_calls": 2})


if __name__ == "__main__":
    unittest.main()
