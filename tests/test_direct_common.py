import unittest

from src.direct_common import (
    direct_advance_rent_utilities_match, direct_deposit_process_match,
    direct_structural_repair_review, direct_unrestricted_termination_review,
)
from src.retrieval import RetrievedChunk


def chunk(clause_id: str, topic: str, text: str) -> RetrievedChunk:
    return RetrievedChunk("CEA_HDB_TA", "HDB", "tenancy_agreement_template", "Template", 5,
                          f"Section {clause_id}", text, 1.0, clause_id=clause_id, topics=(topic,))


class DirectCommonTests(unittest.TestCase):
    def test_structural_liability_contrasts_with_landlord_maintenance(self):
        source = chunk("7.1", "minor_repair", "The Landlord keeps the structural condition, including pipes and electric wiring, in repair. The Landlord shall bear the full cost of replacement unless Tenant fault.")
        clause = "The Tenant pays for every repair including structural pipes and concealed wiring whatever the cause or cost."
        self.assertEqual(direct_structural_repair_review(clause, [source]).label, "review_required")

    def test_unrestricted_termination_contrasts_with_listed_events(self):
        source = chunk("8.2", "termination_notice", "The agreement may be terminated by the Landlord in writing for rent unpaid seven (7) days or a breach unremedied within fourteen (14) days.")
        clause = "The Landlord may end the tenancy at any time for any reason by text message the same day."
        self.assertEqual(direct_unrestricted_termination_review(clause, [source]).label, "review_required")

    def test_deposit_process_matches_without_fixed_amount_claim(self):
        source = chunk("2.2", "security_deposit", "Tenant pays deposit on signing. Written notice and fourteen (14) days precede deduction; balance refunded at expiry.")
        clause = "Tenant pays a security deposit on signing. Deduction requires written notice and fourteen days to remedy; balance refunded at expiry."
        self.assertEqual(direct_deposit_process_match(clause, [source]).label, "no_material_difference_found")

    def test_advance_rent_and_utilities_need_both_reference_topics(self):
        sources = [chunk("1.4", "rent", "The rent under ITEM 8 is payable in advance."),
                   chunk("2.3", "utilities", "The Tenant pays charges for the supply of water, electricity, gas and sewerage.")]
        clause = "Rent is payable monthly in advance. The Tenant pays water, electricity, gas, and sewerage charges."
        result = direct_advance_rent_utilities_match(clause, sources)
        self.assertEqual(result.label, "no_material_difference_found")
        self.assertEqual({item["topic"] for item in result.evidence}, {"rent", "utilities"})


if __name__ == "__main__":
    unittest.main()
