import unittest
from pathlib import Path

from src.pdf_text import align_numbered_paragraphs, extract_layout_pages
from src.schedule_sections import split_schedule_items
from src.source_sections import split_operative_sections, short_heading


ROOT = Path(__file__).resolve().parents[1]
DOCUMENTS = ROOT / "data" / "source_documents"
BASE = {"source_kind": "tenancy_agreement_template", "title": "Fixed CEA template"}


class LayoutParagraphTests(unittest.TestCase):
    def test_centre_aligned_label_moves_to_paragraph_start_not_previous_block(self):
        raw = "5.3 Return the flat in similar condition.\n\n          For the avoidance of doubt, joint\n5.4       inspection decides the confirmed defects."
        fixed = align_numbered_paragraphs(raw)
        self.assertIn("5.4 For the avoidance of doubt, joint", fixed)
        chunks = split_operative_sections([(10, "OPERATIVE PART\n" + fixed)], {**BASE, "source_id": "CEA_HDB_TA", "housing_type": "HDB"})
        by_id = {item["clause_id"]: item["text"] for item in chunks}
        self.assertNotIn("joint", by_id["5.3"])
        self.assertIn("For the avoidance of doubt", by_id["5.4"])

    def test_dense_block_with_two_numbers_is_not_reassigned(self):
        raw = "Paragraph starts\n8.1 Breach process.\n8.2 Automatic events."
        self.assertEqual(align_numbered_paragraphs(raw), raw)

    def test_body_continuation_is_not_a_heading(self):
        self.assertFalse(short_heading("until the keys have been returned"))
        self.assertTrue(short_heading("Right to terminate"))

    def test_chapter_headers_footers_and_annexures_do_not_leak(self):
        raw = "OPERATIVE PART\n2.2 The deposit is refunded without interest at term end.\nH D B F L A T T E N A N C Y A G R E E M E N T P a g e 4 of 19\n3. IMMIGRATION STATUS\nCompliance with Immigration Authority\n3.1 The occupiers must be lawfully resident in Singapore.\nANNEXURE A\n1.1 An unrelated checklist item must not become an operative clause."
        chunks = split_operative_sections([(5, raw)], {**BASE, "source_id": "CEA_HDB_TA", "housing_type": "HDB"})
        self.assertEqual([item["clause_id"] for item in chunks], ["2.2", "3.1"])
        self.assertNotIn("IMMIGRATION", chunks[0]["text"])
        self.assertNotIn("ANNEXURE", str(chunks))
        self.assertNotIn("TENANCY A G R E E M E N T", str(chunks))

    def test_schedule_footnote_is_not_attached_to_break_clause(self):
        raw = "SCHEDULE\n14. DIPLOMATIC / BREAK CLAUSE:\nApplicable or Not Applicable. Documentary evidence is required.\n1 For the avoidance of doubt, this footnote is about stamp fees.\nThe Tenant pays those stamp fees.\nOPERATIVE PART"
        chunks = split_schedule_items([(3, raw)], {**BASE, "source_id": "CEA_PRIVATE_TA", "housing_type": "Private Residential"})
        self.assertEqual(chunks[0]["clause_id"], "ITEM14")
        self.assertNotIn("stamp fees", chunks[0]["text"])


@unittest.skipUnless(all((DOCUMENTS / name).exists() for name in (
    "cea_hdb_tenancy_agreement_template_v1_4.pdf", "cea_private_tenancy_agreement_template_v1_4.pdf"
)), "Registered PDF fixtures are not downloaded")
class FixedTemplateLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sections = {}
        cls.pages = {}
        for housing, identifier, filename in (
            ("HDB", "CEA_HDB_TA", "cea_hdb_tenancy_agreement_template_v1_4.pdf"),
            ("Private Residential", "CEA_PRIVATE_TA", "cea_private_tenancy_agreement_template_v1_4.pdf"),
        ):
            source = {**BASE, "source_id": identifier, "housing_type": housing}
            pages = extract_layout_pages(DOCUMENTS / filename)
            cls.pages[identifier] = pages
            cls.sections[identifier] = split_schedule_items(pages, source) + split_operative_sections(pages, source)

    def clause(self, source, identifier):
        return [item for item in self.sections[source] if item["clause_id"] == identifier]

    def text(self, source, identifier):
        return " ".join(item["text"] for item in self.clause(source, identifier))

    def test_breach_and_automatic_termination_are_separate_in_both_templates(self):
        for source, breach, automatic in (("CEA_HDB_TA", "8.1", "8.2"), ("CEA_PRIVATE_TA", "7.1", "7.2")):
            with self.subTest(source=source):
                self.assertIn("fails to rectify", self.text(source, breach))
                self.assertIn("or within a period as may be agreed", self.text(source, breach))
                self.assertNotIn("prohibited immigrant", self.text(source, breach))
                self.assertIn("automatically terminated", self.text(source, automatic))
                self.assertNotIn("fails to rectify", self.text(source, automatic))
                self.assertIn("termination_notice", self.clause(source, breach)[0]["topics"])

    def test_air_conditioning_service_and_causal_fault_exception_are_separate(self):
        for source in self.sections:
            with self.subTest(source=source):
                self.assertIn("once every three (3) months", self.text(source, "4.4"))
                self.assertNotIn("breakdown is due", self.text(source, "4.4"))
                self.assertIn("breakdown is due", self.text(source, "4.5"))
                self.assertNotIn("once every three (3) months", self.text(source, "4.5"))

    def test_joint_inspection_clause_includes_its_real_paragraph_start(self):
        self.assertIn("For the avoidance of doubt", self.text("CEA_HDB_TA", "5.4"))
        self.assertIn("after a joint inspection", self.text("CEA_HDB_TA", "5.4"))
        self.assertNotIn("after a joint inspection", self.text("CEA_HDB_TA", "5.3"))
        self.assertIn("fair wear and tear", self.text("CEA_HDB_TA", "5.3"))
        self.assertIn("security_deposit", self.clause("CEA_HDB_TA", "5.4")[0]["topics"])

    def test_personal_service_and_deemed_posting_are_not_merged(self):
        for source, personal, deemed in (("CEA_HDB_TA", "11.1", "11.2"), ("CEA_PRIVATE_TA", "12.1", "12.2")):
            with self.subTest(source=source):
                self.assertIn("delivered to the Tenant personally", self.text(source, personal))
                self.assertNotIn("deemed to be served", self.text(source, personal))
                self.assertIn("deemed to be served", self.text(source, deemed))

    def test_identity_production_and_change_notifications_are_not_merged(self):
        for source in self.sections:
            with self.subTest(source=source):
                self.assertIn("Where required by the Landlord", self.text(source, "3.2"))
                self.assertNotIn("not less than fourteen", self.text(source, "3.2"))
                self.assertIn("not less than fourteen", self.text(source, "3.3"))

    def test_break_items_preserve_blanks_applicability_and_evidence_conditions(self):
        for source, item in (("CEA_HDB_TA", "ITEM16"), ("CEA_PRIVATE_TA", "ITEM14")):
            with self.subTest(source=source):
                text = self.text(source, item)
                self.assertIn("Not Applicable", text)
                self.assertIn("____________", text)
                self.assertIn("documentary evidence", text)
                self.assertNotIn("stamp duty", text)

    def test_private_subletting_child_keeps_consent_and_company_exception(self):
        child = [item for item in self.sections["CEA_PRIVATE_TA"] if "Clause 5.1(d) /" in item["section"]]
        self.assertEqual(len(child), 1)
        self.assertIn("consent shall not be unreasonably withheld", child[0]["text"])
        self.assertIn("Where the Tenant is a company", child[0]["text"])

    def test_boundaries_lengths_and_locators_are_consistent(self):
        for sections in self.sections.values():
            locators = [item["section"] for item in sections]
            self.assertEqual(len(locators), len(set(locators)))
            for item in sections:
                if item["section"].startswith("Clause "):
                    self.assertLessEqual(len(item["text"]), 1700)
                self.assertNotIn("ANNEXURE A", item["text"])
                self.assertNotIn("TENANCY AGREEMENT Page", item["text"])


if __name__ == "__main__":
    unittest.main()
