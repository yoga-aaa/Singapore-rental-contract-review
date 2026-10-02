import unittest

from src.retrieval import LocalBM25Retriever, query_topics
from src.source_sections import split_operative_sections


SOURCE = {
    "source_id": "CEA_HDB_TA",
    "housing_type": "HDB",
    "source_kind": "tenancy_agreement_template",
    "title": "Synthetic CEA-style test template",
}


class SectionRetrievalTests(unittest.TestCase):
    def test_clause_split_preserves_locator_and_cross_page_text(self):
        pages = [
            (5, "Schedule item 9 is blank\nOPERATIVE PART\nPremises\n1.1 The flat is for use as a private residence by named occupants.\nSecurity Deposit\n2.2 The deposit is in accordance with ITEM 9."),
            (6, "A deduction requires written notice and an opportunity to remedy.\nUtilities\n2.3 The Tenant pays the charges for water and electricity used at the flat."),
        ]
        chunks = split_operative_sections(pages, SOURCE)
        by_clause = {chunk["clause_id"]: chunk for chunk in chunks}
        self.assertEqual(set(by_clause), {"1.1", "2.2", "2.3"})
        self.assertIn("PDF page 5-6", by_clause["2.2"]["section"])
        self.assertIn("written notice", by_clause["2.2"]["text"])
        self.assertNotIn("Schedule item 9 is blank", by_clause["1.1"]["text"])
        self.assertEqual(by_clause["2.3"]["topics"], ["utilities"])

    def test_topic_aware_retrieval_covers_both_rent_and_utilities(self):
        chunks = [
            {**SOURCE, "page_number": 5, "section": "Clause 1.3 / PDF page 5", "clause_id": "1.3", "topics": ["rent"], "text": "The monthly rent is payable in advance under ITEM 8."},
            {**SOURCE, "page_number": 6, "section": "Clause 2.3 / PDF page 6", "clause_id": "2.3", "topics": ["utilities"], "text": "The Tenant pays charges for water and electricity supply."},
            {**SOURCE, "page_number": 11, "section": "Clause 7.4 / PDF page 11", "clause_id": "7.4", "topics": ["rent"], "text": "Default in Rent occurs when rent remains unpaid seven days."},
            {**SOURCE, "source_id": "CEA_PRIVATE_TA", "housing_type": "Private Residential", "page_number": 5, "section": "Clause 1.3 / PDF page 5", "clause_id": "1.3", "topics": ["rent"], "text": "The monthly rent is payable in advance under ITEM 8."},
        ]
        retriever = LocalBM25Retriever(chunks)
        query = "Rent is payable monthly in advance and the Tenant pays water and electricity utilities."
        self.assertEqual(query_topics(query), {"rent", "utilities"})
        results = retriever.search(query, "HDB", limit=2)
        self.assertEqual({topic for result in results for topic in result.topics}, {"rent", "utilities"})
        self.assertEqual({result.source_id for result in results}, {"CEA_HDB_TA"})


if __name__ == "__main__":
    unittest.main()
