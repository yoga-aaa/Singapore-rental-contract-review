"""Regression tests for actionable-risk decisions rather than wording diffs."""

import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from scripts import run_external_evaluation
from src.direct_common import direct_notice_delivery_match
from src.evidence_verifier import verification_request
from src.live_review import validate_output
from src.rag_review import build_request
from src.retrieval import RetrievedChunk


DEPOSIT = RetrievedChunk(
    "CEA_HDB_TA", "HDB", "tenancy_agreement_template", "HDB template", 5,
    "Clause 2.2 / PDF page 5",
    "The Landlord shall first give written notice to the Tenant and allow fourteen days "
    "to remedy a breach before deducting from the security deposit.",
    1.0, clause_id="2.2", topics=("security_deposit",),
)


def candidate(reason: str, label: str = "review_required", question: str = "Will you give written notice before a deduction?") -> dict:
    return {
        "label": label,
        "clause_category": "security_deposit",
        "reason": reason,
        "follow_up_question": question,
        "source_id": DEPOSIT.source_id,
        "source_section": DEPOSIT.section,
        "evidence": [{
            "source_id": DEPOSIT.source_id,
            "source_section": DEPOSIT.section,
            "topic": "security_deposit",
            "quote": DEPOSIT.text,
        }],
        "abstained": False,
    }


class RiskFocusedReviewTests(unittest.TestCase):
    def test_isolated_omission_does_not_establish_contract_wide_risk(self):
        raw = candidate("The clause omits written notice before a deduction, while the template requires it.")
        clause = "The Landlord may deduct unpaid rent from the deposit."
        self.assertTrue(validate_output(raw, [DEPOSIT], clause_text=clause).abstained)

    def test_explicit_exclusion_supports_actionable_review(self):
        raw = candidate("The clause omits written notice and expressly allows deductions without it; the template requires notice first.")
        clause = "The Landlord may deduct from the deposit without written notice."
        self.assertEqual(validate_output(raw, [DEPOSIT], clause_text=clause).label, "review_required")

    def test_flag_requires_a_specific_question(self):
        raw = candidate("The clause permits deduction without notice, whereas the template requires written notice.", question="")
        self.assertTrue(validate_output(raw, [DEPOSIT], clause_text="Deposit deductions need no notice.").abstained)

    def test_same_obligations_do_not_become_review_due_to_wording(self):
        raw = candidate("The clause matches the template's written notice and fourteen-day cure period exactly.")
        clause = "The landlord must notify the tenant in writing and allow fourteen days to cure before deducting the deposit."
        self.assertTrue(validate_output(raw, [DEPOSIT], clause_text=clause).abstained)
        raw["label"] = "no_material_difference_found"
        raw["follow_up_question"] = ""
        self.assertEqual(validate_output(raw, [DEPOSIT], clause_text=clause).label, "no_material_difference_found")

    def test_both_models_receive_the_risk_not_wording_criterion(self):
        draft = build_request("HDB", "Example deposit clause", [DEPOSIT])["messages"][0]["content"]
        checked = verification_request("HDB", "Example deposit clause", candidate("Some draft reason"))[
            "messages"
        ][0]["content"]
        self.assertIn("Paraphrases", draft)
        self.assertIn("tenant-adverse", draft)
        self.assertIn("tenant consequence", checked)
        self.assertIn("tenant-beneficial", checked)

    def test_unsupported_legal_inference_is_removed_from_reason(self):
        raw = candidate(
            "The clause permits a deduction without notice, whereas the template requires written notice. "
            "This may affect legal validity and enforceability."
        )
        result = validate_output(raw, [DEPOSIT], clause_text="The landlord may deduct without written notice.")
        self.assertEqual(result.label, "review_required")
        self.assertNotIn("validity", result.reason)
        self.assertIn("template requires written notice", result.reason)

    def test_equivalent_notice_methods_pass_and_extra_channel_does_not(self):
        notice = RetrievedChunk(
            "CEA_HDB_TA", "HDB", "tenancy_agreement_template", "HDB template", 12,
            "Clause 11.2 / PDF page 12-13",
            "Notice may be delivered to the Tenant personally or sent by Certificate of Posting "
            "to the address stated in this Agreement.",
            1.0, clause_id="11.2", topics=("termination_notice",),
        )
        same = "A notice is served when delivered by hand or sent by Certificate of Posting to the address in the Agreement."
        result = direct_notice_delivery_match(same, [notice])
        self.assertIsNotNone(result)
        self.assertEqual(result.label, "no_material_difference_found")
        self.assertIsNone(direct_notice_delivery_match(same + " An emoji in a group chat also counts.", [notice]))

    def test_external_runner_stops_before_api_until_independent_labels_exist(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            with patch.object(run_external_evaluation, "read_holdout", return_value=[{"case_id": "EXT_01"}]), \
                 patch.object(run_external_evaluation, "REVIEWED_TRUTH", base / "missing_reviewed.csv"), \
                 patch.object(run_external_evaluation, "OUTPUT", base / "predictions.csv"), \
                 patch.object(run_external_evaluation, "local_api_key") as key:
                with self.assertRaisesRegex(RuntimeError, "Independent-reviewed external labels"):
                    run_external_evaluation.main()
                key.assert_not_called()
                self.assertFalse((base / "predictions.csv").exists())


if __name__ == "__main__":
    unittest.main()
