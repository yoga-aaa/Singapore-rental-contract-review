import unittest

from src.schedule_sections import split_schedule_items


SOURCE = {
    "source_id": "CEA_HDB_TA", "housing_type": "HDB",
    "source_kind": "tenancy_agreement_template", "title": "Template",
}


class ScheduleSectionTests(unittest.TestCase):
    def test_only_selected_fields_are_indexed_and_blanks_remain_variable(self):
        pages = [(2, "SCHEDULE\n4. LANDLORD NAME:\n______\n"
                     "5. NAME OF TENANT:\n______\n6. NAME(S) OF OCCUPIER(S) ALLOWED:\n______\n"
                     "8. RENT:\nRent of ______ per month.\n9. SECURITY DEPOSIT:\n"
                     "Deposit of ______ equivalent to _____ months rent.\n"
                     "10. MINOR REPAIR:\nCost must not exceed S$_____.\n11. OTHER:\ntext\n"
                     "OPERATIVE PART\n1.1 Start of clause")]
        chunks = split_schedule_items(pages, SOURCE)
        self.assertEqual([x["clause_id"] for x in chunks],
                         ["ITEM5", "ITEM6", "ITEM8", "ITEM9", "ITEM10"])
        self.assertIn("NAME(S) OF OCCUPIER(S)", chunks[1]["text"])
        self.assertIn("_____", chunks[3]["text"])
        self.assertEqual(chunks[4]["topics"], ["minor_repair"])
        self.assertTrue(all("OPERATIVE PART" not in x["text"] for x in chunks))


if __name__ == "__main__":
    unittest.main()
