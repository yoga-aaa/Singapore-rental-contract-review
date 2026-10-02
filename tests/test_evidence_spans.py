import unittest

from src.evidence_spans import spans_for_chunks, split_exact_spans
from src.live_review import validate_output
from src.retrieval import RetrievedChunk


class EvidenceSpanTests(unittest.TestCase):
    def test_split_spans_are_contiguous_verbatim_and_bounded(self):
        source = "The deposit is due on signing. " + ("Written notice is needed for a deduction. " * 15)
        spans = split_exact_spans(source)
        self.assertGreater(len(spans), 1)
        self.assertTrue(all(span in source and len(span) <= 560 for span in spans))
        self.assertEqual(" ".join(spans), source.strip())

    def test_model_selects_id_but_program_supplies_exact_quote(self):
        chunk = RetrievedChunk(
            "CEA_HDB_TA", "HDB", "tenancy_agreement_template", "Template", 5,
            "Clause 2.2 / PDF page 5", "The Landlord shall first give written notice before deducting from the deposit.",
            1.0, clause_id="2.2", topics=("security_deposit",),
        )
        span = spans_for_chunks([chunk])[0]
        raw = {
            "label": "review_required", "clause_category": "security_deposit",
            "reason": "The clause allows an immediate deduction but the reference requires written notice first.",
            "follow_up_question": "Will deductions require written notice first?", "source_id": chunk.source_id,
            "source_section": chunk.section, "abstained": False,
            "evidence": [{"evidence_id": span.evidence_id, "topic": "security_deposit"}],
        }
        result = validate_output(raw, [chunk], clause_text="The landlord may immediately deduct the deposit.")
        self.assertFalse(result.abstained)
        self.assertEqual(result.evidence[0]["quote"], chunk.text)
        raw["evidence"][0]["evidence_id"] = "E999"
        self.assertTrue(validate_output(raw, [chunk]).abstained)


if __name__ == "__main__":
    unittest.main()
