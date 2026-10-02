"""Local regressions for approval paraphrases and explicit safeguard waivers."""

import unittest

from src.comparison_checks import omission_issue
from src.live_review import apply_verification
from test_grounded_review_v13 import DEPOSIT, USAGE, approval, candidate


class ApprovalParaphraseTests(unittest.TestCase):
    def test_supported_approval_paraphrase_is_revalidated_and_released(self):
        clause = "The Landlord may deduct from the deposit without written notice."
        raw = candidate(clause)
        check = approval(raw)
        check["reason"] = "The contract waives notice before deposit deductions, whereas the cited template requires written notice."
        check["follow_up_question"] = "Can written notice before a deposit deduction be retained?"
        result = apply_verification(raw, check, [DEPOSIT], USAGE, clause, require_grounding=True)
        self.assertFalse(result.abstained)
        self.assertEqual(result.reason, check["reason"])
        self.assertEqual(result.follow_up_question, check["follow_up_question"])
        self.assertEqual(result.comparisons, tuple(raw["comparisons"]))

    def test_reworded_approval_cannot_add_unsupported_source_exclusivity(self):
        clause = "The Landlord may deduct from the deposit without written notice."
        raw = candidate(clause)
        check = approval(raw)
        check["reason"] = "The reference only allows written notice before deductions, whereas the contract waives notice."
        self.assertTrue(apply_verification(raw, check, [DEPOSIT], USAGE, clause, require_grounding=True).abstained)

    def test_reworded_question_cannot_invent_a_remedy_waiver(self):
        clause = "The Landlord may deduct from the deposit without written notice."
        raw = candidate(clause)
        check = approval(raw)
        check["follow_up_question"] = "Why does this agreement provide no remedy period before a deduction?"
        self.assertTrue(apply_verification(raw, check, [DEPOSIT], USAGE, clause, require_grounding=True).abstained)

    def test_changed_claim_still_requires_explicit_revision(self):
        clause = "The Landlord may deduct from the deposit without written notice."
        raw = candidate(clause)
        check = approval(raw)
        check["comparison_verdicts"][0]["reference_claim"] = "The template permits deduction without notice."
        self.assertTrue(apply_verification(raw, check, [DEPOSIT], USAGE, clause, require_grounding=True).abstained)

    def test_malformed_question_is_rejected(self):
        clause = "The Landlord may deduct from the deposit without written notice."
        raw = candidate(clause)
        check = approval(raw)
        check["follow_up_question"] = []
        self.assertTrue(apply_verification(raw, check, [DEPOSIT], USAGE, clause, require_grounding=True).abstained)


class WaiverParaphraseTests(unittest.TestCase):
    def test_notice_recipient_and_verb_variants(self):
        for clause in (
            "The Landlord may deduct the deposit without giving the Tenant written notice.",
            "The Landlord may deduct the deposit without first notifying the Tenant.",
            "The Landlord is not required to give the Tenant prior written notice before deduction.",
        ):
            with self.subTest(clause=clause):
                self.assertFalse(omission_issue("The clause lacks written notice before deposit deduction.", clause))

    def test_explicit_negative_process_list_covers_both_protections(self):
        clause = "The deposit is returned with no process for written notice or remedy of a breach."
        self.assertFalse(omission_issue("The clause lacks a written notice and remedy process.", clause))

    def test_affirmative_following_process_is_not_waived(self):
        for connector in (", but", " but", ", however"):
            clause = "There is no process for rent increases" + connector + " written notice is required before deposit deductions."
            self.assertTrue(omission_issue("The clause lacks written notice.", clause))

    def test_without_delay_and_different_safeguard_cannot_waive_notice(self):
        for clause in ("The Tenant pays without delay; deductions follow written notice.",
                       "The Landlord may deduct without the Tenant's consent after written notice."):
            self.assertTrue(omission_issue("The clause lacks written notice before deduction.", clause))


if __name__ == "__main__":
    unittest.main()
