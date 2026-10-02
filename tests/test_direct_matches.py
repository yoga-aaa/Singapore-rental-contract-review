import unittest

from src.direct_matches import direct_minor_repair_match, direct_named_occupancy_match
from src.retrieval import RetrievedChunk


def chunk(clause_id: str, topic: str, text: str) -> RetrievedChunk:
    return RetrievedChunk("CEA_HDB_TA", "HDB", "tenancy_agreement_template", "Template", 3,
                          f"Section {clause_id}", text, 1.0, clause_id=clause_id, topics=(topic,))


class DirectMatchTests(unittest.TestCase):
    def test_filled_minor_repair_cap_is_not_a_material_difference(self):
        sources = [
            chunk("ITEM10", "minor_repair", "The minor repair cap is S$_____ per item per incident."),
            chunk("4.2", "minor_repair", "The Tenant pays minor repairs so long as the cost per item per incident does not exceed ITEM 10. Such expenditure in excess of the indicated amount shall be borne by the Landlord unless due to Tenant negligence."),
        ]
        clause = "The Tenant pays minor repairs up to S$200 per item per incident. The Landlord bears cost above S$200 unless due to Tenant negligence."
        result = direct_minor_repair_match(clause, sources)
        self.assertEqual(result.label, "no_material_difference_found")
        self.assertEqual(len(result.evidence), 2)

    def test_unlimited_repair_liability_does_not_trigger_direct_match(self):
        self.assertIsNone(direct_minor_repair_match("The Tenant pays all repairs regardless of cost.", []))

    def test_schedule_names_make_named_occupants_non_material(self):
        sources = [
            chunk("ITEM6", "occupancy_subletting", "6. NAME(S) OF OCCUPIER(S) ALLOWED TO OCCUPY THE FLAT"),
            chunk("1.1", "occupancy_subletting", "The flat is a private residence occupied by persons in ITEMS 5 and 6."),
            chunk("1.2", "occupancy_subletting", "HDB tenants must comply with HDB rental conditions."),
        ]
        clause = "The flat may be occupied only by the Tenant and occupants named in the agreement. The Tenant must comply with HDB rental conditions."
        result = direct_named_occupancy_match(clause, sources)
        self.assertEqual(result.label, "no_material_difference_found")
        self.assertEqual(len(result.evidence), 3)


if __name__ == "__main__":
    unittest.main()
