import unittest

from src.direct_remaining import (
    direct_complete_deposit_match, direct_deferred_deposit_review,
    direct_discretionary_utilities_review, direct_occupant_documents_match,
    direct_unlimited_repair_review, direct_variable_notice_review,
)
from src.retrieval import RetrievedChunk


def chunk(clause_id: str, topic: str, text: str) -> RetrievedChunk:
    return RetrievedChunk("CEA_HDB_TA", "HDB", "tenancy_agreement_template", "Template", 5,
                          f"Section {clause_id}", text, 1.0, clause_id=clause_id, topics=(topic,))


class RemainingDirectMatchTests(unittest.TestCase):
    def test_deposit_amount_remains_a_variable(self):
        sources = [
            chunk("ITEM9", "security_deposit", "9. SECURITY DEPOSIT equivalent to _______ month(s) rent."),
            chunk("2.2", "security_deposit", "The Tenant pays on signing per ITEM 9. Deduction requires written notice and fourteen (14) days to remedy. Balance refunded at expiry. The deposit shall not be utilised as rent."),
        ]
        clause = "The Tenant pays a security deposit of one month's rent on signing. It shall not be used as rent. Deductions require written notice and fourteen days to remedy. Balance refunded at expiry."
        result = direct_complete_deposit_match(clause, sources)
        self.assertEqual(result.label, "no_material_difference_found")
        self.assertIn("blank Schedule ITEM 9", result.reason)

    def test_verbal_deferred_deposit_needs_review(self):
        source = chunk("2.2", "security_deposit", "The deposit is due on signing. Written notice precedes deductions.")
        clause = "The deposit terms will be agreed verbally after the Tenant moves in."
        self.assertEqual(direct_deferred_deposit_review(clause, [source]).label, "review_required")

    def test_unlimited_repairs_need_review(self):
        sources = [chunk("ITEM10", "minor_repair", "The minor repair cap is S$_____ per item."),
                   chunk("4.2", "minor_repair", "Excess over ITEM 10 is borne by the Landlord absent Tenant negligence.")]
        clause = "The Tenant pays all plumbing and electrical repairs regardless of cause or cost."
        self.assertEqual(direct_unlimited_repair_review(clause, sources).label, "review_required")

    def test_later_landlord_notice_period_needs_review(self):
        source = chunk("7.2", "termination_notice", "Landlord may terminate for unpaid rent after seven (7) days or an unremedied breach after written notice and fourteen (14) days.")
        clause = "Either party may end the tenancy after sufficient notice, with the length decided later by the Landlord."
        self.assertEqual(direct_variable_notice_review(clause, [source]).label, "review_required")

    def test_occupier_documents_match_explicit_reference_duty(self):
        source = chunk("3.3", "occupancy_subletting", "Where required by the Landlord, the Tenant shall produce documents of all occupiers evidencing lawful residence.")
        clause = "Foreign occupants must provide documents showing lawful residence when required by the Landlord."
        self.assertEqual(direct_occupant_documents_match(clause, [source]).label,
                         "no_material_difference_found")

    def test_arbitrary_utilities_excess_is_reviewed_without_inventing_bill_rule(self):
        source = chunk("2.3", "utilities", "The Tenant agrees to pay all charges for the supply of water and electricity.")
        clause = "The Landlord may decide the normal level of utilities and charge the Tenant any excess."
        result = direct_discretionary_utilities_review(clause, [source])
        self.assertEqual(result.label, "review_required")
        self.assertNotIn("bill", result.reason)


if __name__ == "__main__":
    unittest.main()
