"""Fresh synthetic and counterfactual regressions; every model call is mocked."""

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.comparison_checks import comparison_issue, omission_issue
from src.evidence_verifier import verification_request
from src.direct_common import direct_unrestricted_termination_review
from src.direct_matches import direct_minor_repair_match, direct_named_occupancy_match
from src.live_review import ModelReviewRequired, apply_verification, review_clause, validate_output
from src.rag_review import build_request, evidence_block
from src.retrieval import LocalBM25Retriever, RetrievedChunk, query_topics
from scripts import run_rag_evaluation


DEPOSIT = RetrievedChunk(
    "CEA_HDB_TA", "HDB", "tenancy_agreement_template", "Synthetic reference", 5,
    "Clause 2.2 / PDF page 5", "The Landlord shall give written notice and fourteen days to remedy a breach before deducting the deposit.",
    1.0, "2.2", ("security_deposit",),
)
SUBLET = RetrievedChunk(
    "CEA_HDB_TA", "HDB", "tenancy_agreement_template", "Synthetic reference", 9,
    "Clause 5.1 / PDF page 9", "The Tenant will not assign or sublet the flat or any part of it to another person.",
    1.0, "5.1", ("occupancy_subletting",),
)
REPAIR = RetrievedChunk(
    "CEA_HDB_TA", "HDB", "tenancy_agreement_template", "Synthetic reference", 7,
    "Clause 4.2 / PDF page 7", "The Tenant must obtain prior written consent for repairs above the cap; the Landlord pays the excess unless the Tenant is negligent.",
    1.0, "4.2", ("minor_repair",),
)
USAGE = {"prompt_tokens": 100, "completion_tokens": 100, "total_tokens": 200}


def candidate(clause, chunk=DEPOSIT, relation="tenant_adverse", label="review_required", reason=None):
    return {
        "label": label, "clause_category": chunk.topics[0],
        "reason": reason or "The contract expressly waives written notice before deductions; the cited template requires written notice first.",
        "follow_up_question": "Will the agreement preserve written notice before a deposit deduction?" if label == "review_required" else "",
        "source_id": chunk.source_id, "source_section": chunk.section,
        "evidence": [{"evidence_id": "E1", "topic": chunk.topics[0]}], "abstained": False,
        "comparisons": [{"topic": chunk.topics[0], "contract_quote": clause,
                         "evidence_indices": [0], "relation": relation,
                         "reference_claim": chunk.text,
                         "tenant_consequence": "The tenant loses the stated opportunity to receive notice before deduction." if relation == "tenant_adverse" else ""}],
    }


def approval(raw):
    return {"decision": "approve", "label": raw["label"], "reason": raw["reason"], "issue": "",
            "follow_up_question": raw["follow_up_question"],
            "comparison_verdicts": [{"comparison_index": index, "verdict": "supported",
                                     "relation": item["relation"], "note": "The explicit contract term differs from the cited notice requirement.",
                                     "tenant_consequence": item["tenant_consequence"], "reference_claim": item["reference_claim"]}
                                    for index, item in enumerate(raw["comparisons"])]}


class GroundedReviewTests(unittest.TestCase):
    def validate(self, raw, clause, chunks=None):
        return validate_output(raw, chunks or [DEPOSIT], clause_text=clause, require_grounding=True)

    def test_contract_quote_must_be_verbatim(self):
        clause = "The Landlord may deduct from the deposit without written notice."
        raw = candidate(clause)
        self.assertFalse(self.validate(raw, clause).abstained)
        raw["comparisons"][0]["contract_quote"] = "The landlord need not notify the tenant."
        self.assertTrue(self.validate(raw, clause).abstained)

    def test_comparison_requires_a_valid_evidence_index(self):
        clause = "The Landlord may deduct from the deposit without written notice."
        for indices in ([9], [True], [0, 0], []):
            with self.subTest(indices=indices):
                raw = candidate(clause)
                raw["comparisons"][0]["evidence_indices"] = indices
                self.assertTrue(self.validate(raw, clause).abstained)

    def test_comparison_topic_must_match_its_evidence(self):
        clause = "The Landlord may deduct from the deposit without written notice."
        raw = candidate(clause)
        raw["comparisons"][0]["topic"] = "termination_notice"
        self.assertTrue(self.validate(raw, clause).abstained)

    def test_no_review_requires_comparisons_for_all_obligations(self):
        clause = "The Tenant shall not sublet the flat. The Tenant pays all utilities."
        raw = candidate("The Tenant shall not sublet the flat.", SUBLET, "equivalent", "no_material_difference_found",
                        "The clause and template both prohibit subletting the flat.")
        self.assertTrue(self.validate(raw, clause, [SUBLET]).abstained)

    def test_beneficial_variation_does_not_become_a_review_issue(self):
        clause = "The Tenant may sublet the flat with the Landlord's written consent."
        raw = candidate(clause, SUBLET, "tenant_beneficial", "no_material_difference_found",
                        "The contract permits subletting with consent while the template prohibits it; this option is more permissive for the tenant.")
        self.assertFalse(self.validate(raw, clause, [SUBLET]).abstained)
        raw["label"] = "review_required"
        raw["follow_up_question"] = "Can you clarify whether I may sublet with consent?"
        self.assertTrue(self.validate(raw, clause, [SUBLET]).abstained)

    def test_conditional_permission_cannot_be_equivalent_to_prohibition(self):
        clause = "The Tenant shall not sublet without the Landlord's written consent."
        raw = candidate(clause, SUBLET, "equivalent", "no_material_difference_found",
                        "The clause matches the reference prohibition of subletting.")
        self.assertTrue(self.validate(raw, clause, [SUBLET]).abstained)

    def test_emergency_exception_is_not_identical_prior_approval(self):
        clause = "The Tenant may arrange emergency repairs first and notify the Landlord afterwards."
        raw = candidate(clause, REPAIR, "equivalent", "no_material_difference_found",
                        "Both require written approval before repairs above the cap.")
        self.assertTrue(self.validate(raw, clause, [REPAIR]).abstained)

    def test_reporting_cost_condition_cannot_be_silently_passed(self):
        clause = "The Tenant pays major repair costs for any failure to report a defect promptly."
        raw = candidate(clause, REPAIR, "equivalent", "no_material_difference_found",
                        "The tenant and landlord repair allocation matches the template cap.")
        self.assertTrue(self.validate(raw, clause, [REPAIR]).abstained)

    def test_refund_withholding_is_not_automatically_a_deduction(self):
        clause = "The Landlord may hold the disputed deposit balance until settlement."
        raw = candidate(clause, reason="The contract allows holding the disputed balance, while the template requires notice before deductions.")
        self.assertTrue(self.validate(raw, clause).abstained)

    def test_exhaustive_source_claim_and_silence_are_rejected(self):
        evidence = [{"quote": "The template provides interest at ten percent per annum on overdue rent."}]
        for reason in ("The reference allows only this interest rate.", "This waterfall is not in the reference.",
                       "The reference has no such finality provision."):
            with self.subTest(reason=reason):
                self.assertIsNotNone(comparison_issue("review_required", reason, "An express daily fee applies.", evidence))

    def test_malformed_model_values_abstain_instead_of_crashing(self):
        clause = "The Landlord may deduct from the deposit without written notice."
        for field, value in (("label", []), ("comparisons", {}), ("evidence", [{"evidence_id": [], "topic": "security_deposit"}])):
            raw = candidate(clause)
            raw[field] = value
            self.assertTrue(self.validate(raw, clause).abstained)

    def test_exact_context_cannot_be_model_fabricated(self):
        clause = "The Landlord may deduct from the deposit without written notice."
        raw = candidate(clause)
        resolved = self.validate(raw, clause)
        raw["evidence"] = list(resolved.evidence)
        raw["evidence"][0]["context_quote"] = "The template permits deductions without notice."
        self.assertTrue(self.validate(raw, clause).abstained)

    def test_production_schema_and_verifier_require_per_comparison_review(self):
        clause = "The Landlord may deduct from the deposit without written notice."
        raw = candidate(clause)
        payload = build_request("HDB", clause, [DEPOSIT])
        self.assertIn("comparisons", payload["response_format"]["json_schema"]["schema"]["required"])
        resolved = self.validate(raw, clause)
        checked = verification_request("HDB", clause, {**raw, "evidence": list(resolved.evidence)})
        self.assertIn("comparison_verdicts", checked["response_format"]["json_schema"]["schema"]["required"])
        body = json.loads(checked["messages"][1]["content"])
        self.assertEqual(body["draft_follow_up_question"], raw["follow_up_question"])
        self.assertEqual(body["reference_contexts"][0]["context_quote"], DEPOSIT.text)

    def test_partial_verifier_approval_cannot_release_a_result(self):
        clause = "The Landlord may deduct from the deposit without written notice."
        raw = candidate(clause)
        checked = approval(raw)
        checked["comparison_verdicts"] = []
        result = apply_verification(raw, checked, [DEPOSIT], USAGE, clause, require_grounding=True)
        self.assertTrue(result.abstained)

    def test_verifier_relation_change_requires_consistent_revised_label(self):
        clause = "The Tenant may sublet the flat with the Landlord's written consent."
        raw = candidate(clause, SUBLET, "tenant_beneficial", "no_material_difference_found",
                        "The contract gives an optional subletting permission unlike the cited prohibition.")
        checked = approval(raw)
        checked["comparison_verdicts"][0]["relation"] = "tenant_adverse"
        self.assertTrue(apply_verification(raw, checked, [SUBLET], USAGE, clause, require_grounding=True).abstained)

    def test_verifier_can_correct_a_beneficial_variation_without_flagging_it(self):
        clause = "The Tenant may sublet the flat with the Landlord's written consent."
        raw = candidate(clause, SUBLET, "tenant_adverse", "review_required",
                        "The contract has a different conditional subletting term from the cited prohibition.")
        checked = approval(raw)
        checked.update(decision="revise", label="no_material_difference_found",
                       reason="The contract gives a more permissive subletting option than the cited prohibition.", follow_up_question="")
        checked["comparison_verdicts"][0].update(relation="tenant_beneficial", tenant_consequence="")
        result = apply_verification(raw, checked, [SUBLET], USAGE, clause, require_grounding=True)
        self.assertEqual(result.label, "no_material_difference_found")
        self.assertEqual(result.comparisons[0]["relation"], "tenant_beneficial")

    def test_verifier_malformed_label_does_not_crash(self):
        clause = "The Landlord may deduct from the deposit without written notice."
        raw = candidate(clause)
        checked = approval(raw)
        checked.update(decision="revise", label=[])
        self.assertTrue(apply_verification(raw, checked, [DEPOSIT], USAGE, clause, require_grounding=True).abstained)

    def test_mocked_end_to_end_two_calls_preserve_quotes_and_usage(self):
        clause = "The Landlord may deduct from the deposit without written notice."
        raw = candidate(clause)
        retriever = LocalBM25Retriever([DEPOSIT.__dict__])
        with patch("src.live_review._request_openrouter", return_value=(raw, USAGE)) as draft, \
             patch("src.live_review.verify_candidate", return_value=(approval(raw), USAGE)) as checker:
            result = review_clause("HDB", clause, retriever, api_key="synthetic-test-key")
        self.assertFalse(result.abstained)
        self.assertEqual(result.usage["api_calls"], 2)
        self.assertEqual(result.usage["total_tokens"], 400)
        self.assertEqual(result.comparisons[0]["contract_quote"], clause)
        self.assertEqual(result.evidence[0]["context_quote"], DEPOSIT.text)
        draft.assert_called_once()
        checker.assert_called_once()

    def test_verifier_can_repair_scope_but_not_release_an_unrepaired_claim(self):
        clause = "The Landlord may deduct from the deposit without written notice."
        raw = candidate(clause, reason="The reference only allows written notice before deduction, whereas the contract waives notice.")
        raw["comparisons"][0]["reference_claim"] = "The reference only allows written notice before deduction."
        # Structural checks let the second call correct reasoning; final checks
        # still reject an overclaim that was approved without correction.
        self.assertFalse(validate_output(raw, [DEPOSIT], clause_text=clause,
                                         require_grounding=True, structural_only=True).abstained)
        self.assertTrue(apply_verification(raw, approval(raw), [DEPOSIT], USAGE, clause, require_grounding=True).abstained)
        corrected = approval(raw)
        corrected.update(decision="revise", reason="The contract waives written notice; the cited template requires written notice before deducting.")
        corrected["comparison_verdicts"][0]["reference_claim"] = "The Landlord must give written notice before a deposit deduction."
        result = apply_verification(raw, corrected, [DEPOSIT], USAGE, clause, require_grounding=True)
        self.assertFalse(result.abstained)

    def test_offline_mode_stops_before_key_read_or_network(self):
        clause = "The Tenant may sublet with the Landlord's written consent."
        retriever = LocalBM25Retriever([SUBLET.__dict__])
        with patch("src.live_review.local_api_key") as key, patch("src.live_review._request_openrouter") as network:
            with self.assertRaises(ModelReviewRequired):
                review_clause("HDB", clause, retriever, allow_api=False)
        key.assert_not_called()
        network.assert_not_called()

    def test_context_is_sent_once_per_section(self):
        chunk = copy.copy(DEPOSIT)
        object.__setattr__(chunk, "text", "Opening condition. " + "A detailed safeguard applies. " * 30)
        block = evidence_block([chunk])
        self.assertEqual(block.count("REFERENCE_CONTEXT"), 1)
        self.assertGreater(block.count("EVIDENCE_ID"), 1)

    def test_unguarded_claim_of_waiver_is_rejected(self):
        clause = "The Landlord may deduct unpaid rent from the deposit."
        raw = candidate(clause, reason="The contract allows deduction without written notice, whereas the template requires written notice.")
        self.assertTrue(self.validate(raw, clause).abstained)

    def test_tenant_beneficial_exit_is_not_a_landlord_risk(self):
        clause = "The Tenant may end the tenancy at any time for any reason by text message the same day."
        source = RetrievedChunk("CEA_HDB_TA", "HDB", "tenancy_agreement_template", "Synthetic", 11,
                                "Clause 8.2 / PDF page 11",
                                "This may be terminated by the Landlord in writing for rent unpaid seven (7) days or breach unremedied fourteen (14) days.",
                                1.0, "8.2", ("termination_notice",))
        self.assertIsNotNone(direct_unrestricted_termination_review(clause.replace("Tenant", "Landlord"), [source]))
        self.assertIsNone(direct_unrestricted_termination_review(clause, [source]))

    def test_keywords_do_not_pass_reversed_repair_cost_allocation(self):
        clause = "The Tenant pays minor repairs up to S$200 per item per incident. The Tenant bears cost above S$200 unless due to Landlord negligence."
        schedule = RetrievedChunk("CEA_HDB_TA", "HDB", "tenancy_agreement_template", "Synthetic", 3,
                                  "ITEM 10", "The minor repair cap is S$_____ per item per incident.", 1.0, "ITEM10", ("minor_repair",))
        operative = RetrievedChunk("CEA_HDB_TA", "HDB", "tenancy_agreement_template", "Synthetic", 7,
                                   "Clause 4.2", "Minor repair cost per item per incident is capped by ITEM 10; excess is borne by the Landlord absent Tenant negligence.",
                                   1.0, "4.2", ("minor_repair",))
        sources = [schedule, operative]
        correct = clause.replace("The Tenant bears cost", "The Landlord bears cost").replace("Landlord negligence", "Tenant negligence")
        self.assertIsNotNone(direct_minor_repair_match(correct, sources))
        passive = "Minor repairs are capped at S$200 per item per incident. Costs above S$200 are borne by the Landlord unless due to Tenant negligence."
        self.assertIsNotNone(direct_minor_repair_match(passive, sources))
        self.assertIsNone(direct_minor_repair_match(clause, sources))

    def test_named_occupants_word_does_not_cover_anyone_permission(self):
        clause = "Anyone may occupy the flat, including named occupants."
        sources = [RetrievedChunk("CEA_HDB_TA", "HDB", "tenancy_agreement_template", "Synthetic", 2,
                                  "ITEM 6", "NAME(S) OF OCCUPIER(S)", 1.0, "ITEM6", ("occupancy_subletting",)),
                   RetrievedChunk("CEA_HDB_TA", "HDB", "tenancy_agreement_template", "Synthetic", 5,
                                  "Clause 1.1", "Residence occupancy is by persons in ITEM 5 and ITEM 6.", 1.0, "1.1", ("occupancy_subletting",))]
        self.assertIsNotNone(direct_named_occupancy_match("Only named occupants may occupy the flat.", sources))
        self.assertIsNone(direct_named_occupancy_match(clause, sources))

    def test_negated_notice_cannot_trigger_direct_no_review(self):
        clause = "Tenant pays deposit on signing. Deduction does not require written notice and fourteen days to remedy; balance refunded at expiry."
        source = RetrievedChunk("CEA_HDB_TA", "HDB", "tenancy_agreement_template", "Synthetic", 5,
                                "Clause 2.2", "Deposit is paid on signing. Deduction requires written notice and fourteen (14) days to remedy; balance refunded at expiry.",
                                1.0, "2.2", ("security_deposit",))
        retriever = LocalBM25Retriever([source.__dict__])
        self.assertFalse(review_clause("HDB", clause.replace("does not require", "requires"), retriever, allow_api=False).abstained)
        with patch("src.live_review.local_api_key") as key:
            with self.assertRaises(ModelReviewRequired):
                review_clause("HDB", clause, retriever, allow_api=False)
        key.assert_not_called()


class OmissionCounterfactualTests(unittest.TestCase):
    def test_omission_paraphrases_are_rejected(self):
        clause = "The Landlord may deduct unpaid rent from the deposit."
        for reason in ("The clause allows deduction without requiring written notice.",
                       "The clause allows deduction without specifying written notice.",
                       "The clause has no explicit provision for written notice.",
                       "The clause does not require written notice."):
            with self.subTest(reason=reason):
                self.assertTrue(omission_issue(reason, clause))

    def test_unrelated_without_phrase_is_not_a_waiver(self):
        self.assertTrue(omission_issue("The clause omits written notice before deduction.",
                                      "The Tenant must report defects without delay. The Landlord may deduct the deposit."))

    def test_notice_waiver_does_not_waive_remedy_period(self):
        self.assertTrue(omission_issue("The clause omits a remedy period.", "The Landlord may deduct without written notice."))

    def test_explicit_same_protection_waiver_is_detected(self):
        self.assertFalse(omission_issue("The clause omits written notice and expressly waives it.",
                                       "The Landlord may deduct without written notice."))


class MultiTopicTests(unittest.TestCase):
    def test_deposit_does_not_hide_termination_right(self):
        self.assertEqual(query_topics("Either party may terminate by written notice. Unpaid notice rent may be deducted from the deposit."),
                         {"termination_notice", "security_deposit"})

    def test_deposit_sizing_and_deduction_lists_are_not_separate_obligations(self):
        self.assertEqual(query_topics("The deposit equals two months rent. The landlord may deduct utility bills and repair costs from the deposit."),
                         {"security_deposit"})

    def test_deposit_notice_is_not_termination(self):
        self.assertEqual(query_topics("Deposit deductions require written notice and fourteen days to remedy."), {"security_deposit"})

    def test_following_notice_sentence_inherits_deposit_context(self):
        self.assertEqual(query_topics("A security deposit is paid on signing. Written notice and fourteen days to remedy precede any deduction."),
                         {"security_deposit"})

    def test_extra_rent_is_not_hidden_by_a_deposit_increase(self):
        self.assertEqual(query_topics("Consent may be conditional on an increased deposit and additional rent."),
                         {"security_deposit", "rent"})

    def test_independent_rent_utilities_and_repair_topics_are_collected(self):
        self.assertEqual(query_topics("Rent is paid monthly in advance. The Tenant pays utilities. The Landlord maintains the plumbing."),
                         {"rent", "utilities", "minor_repair"})

    def test_housing_filter_and_multi_topic_coverage(self):
        exit_clause = RetrievedChunk("CEA_HDB_TA", "HDB", "tenancy_agreement_template", "Synthetic", 11,
                                     "Clause 8.2 / PDF page 11", "Right to terminate: terminated by the Landlord in writing for a breach.",
                                     1.0, "8.2", ("termination_notice",))
        private = copy.copy(DEPOSIT)
        object.__setattr__(private, "housing_type", "Private Residential")
        retriever = LocalBM25Retriever([DEPOSIT.__dict__, exit_clause.__dict__, private.__dict__])
        found = retriever.search("Either party may terminate by notice. The deposit may be deducted.", "HDB", limit=2)
        self.assertEqual({topic for chunk in found for topic in chunk.topics}, {"security_deposit", "termination_notice"})
        self.assertTrue(all(chunk.housing_type == "HDB" for chunk in found))


class EvaluationBudgetTests(unittest.TestCase):
    def test_runner_does_not_start_a_two_call_review_with_only_one_call_left(self):
        with tempfile.TemporaryDirectory() as directory:
            cases = Path(directory) / "development_cases.csv"
            output = Path(directory) / "new_predictions.csv"
            cases.write_text("case_id,housing_type,clause_text\nDEV_NEW,HDB,A synthetic deposit clause.\n", encoding="utf-8")
            args = ["run_rag_evaluation.py", "--cases", str(cases), "--output", str(output), "--max-model-calls", "1"]
            with patch("sys.argv", args), \
                 patch.object(run_rag_evaluation.LocalBM25Retriever, "from_jsonl", return_value=object()), \
                 patch.object(run_rag_evaluation, "review_clause", side_effect=ModelReviewRequired) as review:
                with self.assertRaisesRegex(RuntimeError, "fewer than two"):
                    run_rag_evaluation.main()
            self.assertEqual(review.call_count, 1)
            self.assertFalse(review.call_args.kwargs["allow_api"])
            self.assertEqual(len(output.read_text(encoding="utf-8").splitlines()), 1)


if __name__ == "__main__":
    unittest.main()
