import unittest

from src.live_review import normalized_quote, unsupported_fixed_amount_claim


class FixedAmountGuardrailTests(unittest.TestCase):
    def test_word_order_survives_punctuation_and_spacing(self):
        self.assertEqual(normalized_quote("notice, or written notice."), "notice or written notice")

    def test_unsupported_template_amount_is_rejected(self):
        evidence = [{"quote": "The Security Deposit is the amount set out in ITEM 9."}]
        reason = "Both the clause and the CEA template stipulate a deposit of one month's rent."
        self.assertTrue(unsupported_fixed_amount_claim(reason, evidence))

    def test_clause_amount_not_attributed_to_reference_is_allowed(self):
        evidence = [{"quote": "The Security Deposit is the amount set out in ITEM 9."}]
        reason = "The clause sets the deposit at one month's rent; the template leaves the amount to ITEM 9."
        self.assertFalse(unsupported_fixed_amount_claim(reason, evidence))

    def test_amount_present_in_cited_quote_is_allowed(self):
        evidence = [{"quote": "The tenant shall pay S$200 for each minor repair."}]
        reason = "The reference specifies S$200 for each minor repair."
        self.assertFalse(unsupported_fixed_amount_claim(reason, evidence))


if __name__ == "__main__":
    unittest.main()
