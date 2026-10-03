"""Handcrafted gate fixtures, NOT model predictions or a performance benchmark.

These exercise both sides of each changed mechanism. The response is supplied
by the test; success only means the release gate can retain that valid contrast
and does not force every example to abstain. No external labels are imported.
"""
import copy
import unittest

from src.review_v18 import obligation_inventory
from src.review_v19 import finalize


# Fictional reference wording isolates mechanisms. Official retriever integrity
# and unchanged source bytes are tested separately in test_review_v19.py.
CONTROLS = [
    ('refund_trigger','security_deposit','2.2',
     'The deposit is refunded when the Term expires or is terminated.',
     'The deposit is refunded within eighteen days after handover.',
     'The contract uses a later handover-based refund window rather than term expiry or termination.',
     'Refund can be delayed after expiry pending handover and the stated window.',
     'The deposit is returned when the Term ends or is terminated.'),
    ('repair_completion_deadline','minor_repair','4.7',
     'Start repair within fourteen days and complete the works within a reasonable time.',
     'If the tenant fails to complete repairs within fourteen days, the landlord may recover repair costs.',
     'The contract makes completion within fourteen days the cost-recovery trigger, not starting then completing in a reasonable time.',
     'The tenant can face cost recovery for work not completed by the fixed deadline.',
     'The tenant must start repairs within fourteen days and complete them within a reasonable time.'),
    ('repair_causation','minor_repair','4.5',
     'The landlord pays repair or replacement unless the fault was caused by the tenant failure to maintain the air-conditioning.',
     'The landlord pays replacement not caused by failure to maintain air-conditioning provided that the tenant has complied with all servicing duties.',
     'Payment for a fault not caused by non-maintenance is additionally conditional on full servicing compliance.',
     'A non-causal servicing breach could still transfer replacement costs to the tenant.',
     'The landlord pays air-conditioning replacement unless tenant non-maintenance caused the fault.'),
    ('landlord_exit_trigger','termination_notice','7.1',
     'If the tenant pays rent and performs obligations, the tenant may HOLD AND ENJOY the flat during the Term.',
     'The landlord may terminate the tenancy early for own occupation despite the tenant performing all obligations.',
     'The contract permits landlord-triggered early exit for own occupation despite tenant performance, against conditional enjoyment during the Term.',
     'A compliant tenant can lose the remaining rental period through that positive exit trigger.',
     'If the tenant pays rent and performs obligations, the tenant may hold and enjoy the flat during the Term.'),
    ('exit_evidence_acceptance','termination_notice','ITEM16',
     'A relocation termination notice must be accompanied by documentary evidence of relocation.',
     'The tenant must supply documentary evidence of relocation acceptable to the Landlord to terminate.',
     'The contract adds landlord acceptance of evidence to the documentary relocation requirement.',
     'The additional acceptance standard can affect exercise of the relocation exit right.',
     'The tenant must accompany relocation termination notice with documentary evidence of relocation.'),
    ('current_term_rent_review','rent','1.4',
     'Rent means the monthly rent agreed for the Term.',
     'The landlord may revise monthly rent during the Term on twenty days notice; the tenant may terminate instead.',
     'The contract adds a mid-term rent-revision trigger to the agreed monthly rent for the Term.',
     'The tenant can face paying revised rent or leaving instead of staying at the agreed rent.',
     'The tenant pays the monthly rent agreed for the Term.'),
]


def packet_and_response(control, clause, relation):
    mechanism,topic,cid,quote,_,difference,consequence,_=control
    ref={'evidence_id':'R001','source_id':'SYNTHETIC_GATE_FIXTURE','housing_type':'HDB',
         'source_kind':'tenancy_agreement_template','clause_id':cid,'section':'Synthetic '+cid,
         'topics':[topic],'text':quote}
    row={'contract_span_ids':['C001'],'obligation_ids':list(obligation_inventory(clause)),
         'reference_ids':['R001'],'topic':topic,'mechanism':mechanism,'relation':relation,
         'reference_claim':quote,'difference':difference if relation=='tenant_adverse' else 'The same positive condition is stated in different words.',
         'tenant_consequence':consequence if relation=='tenant_adverse' else 'The compared condition has the same effect.',
         'question':'Can the stated condition and its consequences be clarified?',
         'verdict':'supported','check_note':'The selected positive mechanism supports this limited comparison.'}
    return {'references':[ref],'topics':[topic],'truncated':False}, {'comparisons':[row],'unassessed_span_ids':[]}


class PositiveControlTests(unittest.TestCase):
    def test_valid_limited_risk_can_be_released_for_each_improved_mechanism(self):
        for control in CONTROLS:
            with self.subTest(mechanism=control[0]):
                clause=control[4]
                packet,raw=packet_and_response(control,clause,'tenant_adverse')
                result=finalize(raw,clause,packet,'HDB')
                self.assertEqual(result.label,'review_required')
                self.assertEqual(len(result.comparisons),1)

    def test_equivalent_paraphrases_can_pass_without_being_flagged(self):
        for control in CONTROLS:
            with self.subTest(mechanism=control[0]):
                clause=control[7]
                packet,raw=packet_and_response(control,clause,'equivalent')
                self.assertEqual(finalize(raw,clause,packet,'HDB').label,'no_material_difference_found')

    def test_wrong_process_citation_fails_closed(self):
        for control in CONTROLS:
            with self.subTest(mechanism=control[0]):
                clause=control[4]
                packet,raw=packet_and_response(control,clause,'tenant_adverse')
                packet['references'][0].update(clause_id='UNRELATED',text='The tenant pays utility charges.')
                result=finalize(raw,clause,packet,'HDB')
                self.assertEqual(result.label,'insufficient_evidence')

    def test_reasonable_document_check_does_not_become_unrestricted_veto(self):
        control=CONTROLS[4]
        clause='Documentary relocation evidence is acceptable to the landlord acting reasonably to verify authenticity.'
        packet,raw=packet_and_response(control,clause,'tenant_adverse')
        raw['comparisons'][0]['tenant_consequence']='The tenant faces an unrestricted landlord veto of the exit right.'
        self.assertEqual(finalize(raw,clause,packet,'HDB').label,'insufficient_evidence')

    def test_unsupported_neighbor_is_not_released_with_supported_risk(self):
        control=CONTROLS[0]
        clause=control[4]
        packet,raw=packet_and_response(control,clause,'tenant_adverse')
        bad=copy.deepcopy(raw['comparisons'][0])
        bad['tenant_consequence']='The tenant loses the refund without prior written notice.'
        raw['comparisons'].append(bad)
        result=finalize(raw,clause,packet,'HDB')
        self.assertEqual(result.label,'review_required')
        self.assertEqual(len(result.comparisons),1)
        self.assertNotIn('without prior written notice',result.reason)


if __name__=='__main__':
    unittest.main()
