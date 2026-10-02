import unittest

from src.direct_differences import direct_discretionary_rent_review, direct_late_rent_review
from src.retrieval import RetrievedChunk


def chunk(clause_id: str, text: str) -> RetrievedChunk:
    return RetrievedChunk("CEA_PRIVATE_TA", "Private Residential", "tenancy_agreement_template",
                          "Template", 6, f"Section {clause_id}", text, 1.0,
                          clause_id=clause_id, topics=("rent",))


class DirectDifferenceTests(unittest.TestCase):
    def test_daily_charge_compares_with_explicit_default_interest(self):
        source = chunk("7.4", "Default in Rent: unpaid seven days after due date; interest at ten percent (10%) per annum.")
        clause = "If rent is late, the Tenant pays S$100 per day."
        result = direct_late_rent_review(clause, [source])
        self.assertEqual(result.label, "review_required")
        self.assertIn("ten percent", result.evidence[0]["quote"])

    def test_discretionary_rent_change_is_reviewed_against_item8(self):
        sources = [chunk("ITEM8", "8. RENT: The rent amount is ______ per month."),
                   chunk("1.3", "The rent is the amount referred to in ITEM 8.")]
        clause = "The agent may change the rent at their absolute discretion."
        result = direct_discretionary_rent_review(clause, sources)
        self.assertEqual(result.label, "review_required")
        self.assertEqual(len(result.evidence), 2)
        self.assertNotIn("prohibited", result.reason)


if __name__ == "__main__":
    unittest.main()
