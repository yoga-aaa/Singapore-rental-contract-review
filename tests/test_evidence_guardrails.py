import unittest

from src.live_review import validate_output
from src.retrieval import RetrievedChunk


RENT = RetrievedChunk(
    "CEA_PRIVATE_TA", "Private Residential", "tenancy_agreement_template", "Private template",
    6, "Clause 1.3 / PDF page 6",
    "The rent is the amount referred to in ITEM 8, payable in advance on the stated date.",
    10.0, clause_id="1.3", topics=("rent",),
)
UTILITIES = RetrievedChunk(
    "CEA_PRIVATE_TA", "Private Residential", "tenancy_agreement_template", "Private template",
    6, "Clause 2.3 / PDF page 6",
    "The Tenant agrees to pay all charges for the supply of water, electricity and gas.",
    9.0, clause_id="2.3", topics=("utilities",),
)


class EvidenceGuardrailTests(unittest.TestCase):
    def setUp(self):
        self.raw = {
            "label": "no_material_difference_found",
            "clause_category": "rent_utilities",
            "reason": "The two allocations track the template.",
            "follow_up_question": "",
            "source_id": RENT.source_id,
            "source_section": RENT.section,
            "evidence": [{
                "source_id": RENT.source_id, "source_section": RENT.section, "topic": "rent",
                "quote": "The rent is the amount referred to in ITEM 8, payable in advance",
            }],
            "abstained": False,
        }
        self.clause = "Rent is payable in advance, and the Tenant pays water and electricity utilities."

    def test_no_difference_requires_all_material_topics(self):
        self.assertTrue(validate_output(self.raw, [RENT, UTILITIES], clause_text=self.clause).abstained)
        self.raw["evidence"].append({
            "source_id": UTILITIES.source_id, "source_section": UTILITIES.section,
            "topic": "utilities", "quote": "The Tenant agrees to pay all charges for the supply of water, electricity and gas",
        })
        self.assertFalse(validate_output(self.raw, [RENT, UTILITIES], clause_text=self.clause).abstained)

    def test_nonexistent_quote_or_wrong_topic_is_rejected(self):
        self.raw["evidence"][0]["quote"] = "The Landlord may change the rent every week"
        self.assertTrue(validate_output(self.raw, [RENT], clause_text="Rent is payable in advance.").abstained)
        self.raw["evidence"][0]["quote"] = "The rent is the amount referred to in ITEM 8, payable in advance"
        self.raw["evidence"][0]["topic"] = "security_deposit"
        self.assertTrue(validate_output(self.raw, [RENT], clause_text="Rent is payable in advance.").abstained)


if __name__ == "__main__":
    unittest.main()
