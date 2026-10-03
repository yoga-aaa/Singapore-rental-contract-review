import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from src.contract_spans import contract_spans
from src.evidence_packet_v19 import CoverageRetriever
from src.review_v18 import obligation_inventory
from src.review_v19 import build_request, claim_issue, finalize, response_issue, review_clause

ROOT=Path(__file__).resolve().parents[1]


def reference(cid='2.2',topic='security_deposit',text='The landlord may deduct a reasonable sum to remedy breach after prior written notice.',rid='R001'):
    return {'evidence_id':rid,'source_id':'CEA_HDB_TA','housing_type':'HDB',
            'source_kind':'tenancy_agreement_template','clause_id':cid,'section':'Synthetic '+cid,
            'topics':[topic],'text':text}


def comparison(clause,mechanism='deposit_deduction_process',topic='security_deposit',cid='C001',rid='R001'):
    obligations=obligation_inventory(clause)
    return {'contract_span_ids':[cid],'obligation_ids':[next(k for k,v in obligations.items() if v['contract_span_id']==cid)],
            'reference_ids':[rid],'topic':topic,'mechanism':mechanism,'relation':'tenant_adverse',
            'reference_claim':'The landlord may deduct a reasonable sum to remedy breach after prior written notice.',
            'difference':'The contract expressly changes the specified payment mechanism.',
            'tenant_consequence':'The tenant could have to pay the stated additional amount.',
            'question':'Can the stated additional payment condition be clarified?',
            'verdict':'supported','check_note':'The reference has a positive contrasting condition.'}


class ClaimGateTests(unittest.TestCase):
    def setUp(self):
        self.clause='The landlord may deduct unpaid utility charges from the deposit.'
        self.ref=reference()
        self.row=comparison(self.clause)

    def issue(self,row=None,clause=None,ref=None):
        return claim_issue(row or self.row,clause or self.clause,{'R001':ref or self.ref})

    def test_may_deduct_is_not_immediate_or_notice_waiver(self):
        for assertion in ['Tenant loses the deposit without prior written notice.',
                          'Tenant faces immediate deduction of the deposit.',
                          'Tenant has no cure opportunity before deduction.']:
            row={**self.row,'tenant_consequence':assertion}
            self.assertIsNotNone(self.issue(row))

    def test_actual_express_notice_waiver_is_not_blocked_by_omission_gate(self):
        clause='The landlord may deduct immediately without prior written notice.'
        row=comparison(clause)
        row['tenant_consequence']='Tenant faces immediate deduction without prior written notice.'
        self.assertIsNone(self.issue(row,clause))

    def test_material_breach_does_not_mean_immediate_termination(self):
        clause='Any breach of the guest clause is a material breach of this Agreement.'
        row=comparison(clause,'landlord_exit_trigger','termination_notice')
        row['tenant_consequence']='The tenant risks immediate termination for this breach.'
        self.assertIsNotNone(self.issue(row,clause))

    def test_guest_id_does_not_become_named_occupier_standard(self):
        clause='The tenant provides a copy of any guest passport to the landlord.'
        row=comparison(clause,'guest_documentation','occupancy_subletting')
        ref=reference('3.2','occupancy_subletting','The tenant supplies identity documents of named occupiers.')
        self.assertIsNotNone(self.issue(row,clause,ref))

    def test_holdover_cannot_use_late_interest_as_its_standard(self):
        clause='After expiry the tenant pays double monthly rent while remaining in occupation.'
        row=comparison(clause,'holdover_charge','rent')
        self.assertIsNotNone(self.issue(row,clause,reference('8.4','rent','Late interest is 10% per annum.')))
        self.assertIsNone(self.issue(row,clause,reference('19.1','rent','The rent continues until the keys are returned.')))

    def test_repair_start_and_completion_are_not_equivalent(self):
        clause='If the tenant fails to carry out repair within 14 days the landlord may recover repair costs.'
        row=comparison(clause,'repair_completion_deadline','minor_repair')
        row['relation']='equivalent'
        ref=reference('4.7','minor_repair','Proceed with works within 14 days; complete them within a reasonable time.')
        self.assertIsNotNone(self.issue(row,clause,ref))
        equivalent='The tenant must proceed with repair within 14 days and complete it within a reasonable time.'
        self.assertIsNone(self.issue(comparison(equivalent,'repair_completion_deadline','minor_repair'),equivalent,ref))

    def test_aircon_compliance_is_not_causation(self):
        clause='Replacement is not attributable to failure to service, and the landlord pays provided that the tenant has complied with servicing.'
        row=comparison(clause,'repair_causation','minor_repair'); row['relation']='equivalent'
        self.assertIsNotNone(self.issue(row,clause,reference('4.5','minor_repair','Landlord pays unless breakdown is due to tenant non-maintenance.')))

    def test_landlord_acceptance_is_not_assumed_objective(self):
        clause='The tenant supplies documentary evidence acceptable to the Landlord on relocation.'
        row=comparison(clause,'exit_evidence_acceptance','termination_notice'); row['relation']='equivalent'
        self.assertIsNotNone(self.issue(row,clause,reference('ITEM16','termination_notice','Notice accompanies documentary evidence of relocation.')))

    def test_fixed_refund_window_is_not_automatically_beneficial(self):
        clause='Refund is due within 18 days after vacant possession.'
        row=comparison(clause,'refund_trigger'); row['relation']='tenant_beneficial'
        ref=reference(text='The deposit is refunded when the Term expires or is terminated.')
        self.assertIsNotNone(self.issue(row,clause,ref))

    def test_agreed_remedy_period_exception_is_retained(self):
        self.ref['text']='Tenant may remedy within fourteen (14) days or within a period as may be agreed.'
        self.row['reference_claim']='Tenant may remedy within 14 days.'
        self.assertIsNotNone(self.issue())
        self.row['reference_claim']='Tenant may remedy within 14 days or an agreed period.'
        self.assertIsNone(self.issue())

    def test_one_valid_risk_survives_rejection_of_an_unrelated_claim(self):
        clause='If rent is late the tenant pays 1% per week, capped at 10%. The landlord may recover rent from the deposit.'
        rate=reference('8.4','rent','Interest is 10% per annum if rent remains unpaid seven days.',rid='R001')
        deposit=reference(rid='R002')
        first=comparison(clause,'late_payment_charge','rent')
        first.update(reference_claim='Interest is 10% per annum if rent remains unpaid seven days.',
                     difference='The contract charges 1% per week capped at 10%, rather than annual interest.',
                     tenant_consequence='A short overdue period can cost more with the stated weekly charge.')
        second=comparison(clause,cid='C002',rid='R002')
        second['tenant_consequence']='Tenant faces immediate deduction without prior notice.'
        packet={'references':[rate,deposit],'truncated':False,'topics':['rent','security_deposit']}
        result=finalize({'comparisons':[first,second],'unassessed_span_ids':[]},clause,packet,'HDB')
        self.assertEqual(result.label,'review_required')
        self.assertEqual(len(result.comparisons),1)
        self.assertNotIn('immediate',result.reason)

    def test_missing_mechanism_fails_closed_and_request_retains_two_models(self):
        packet={'references':[self.ref],'truncated':False,'topics':['security_deposit']}
        raw={'comparisons':[self.row],'unassessed_span_ids':[]}
        self.assertIsNone(response_issue(raw,self.clause,packet,True))
        del self.row['mechanism']
        self.assertIsNotNone(response_issue(raw,self.clause,packet,True))
        draft=build_request('HDB',self.clause,packet)
        verify=build_request('HDB',self.clause,packet,raw)
        self.assertEqual((draft['model'],verify['model']),('openai/gpt-4.1','openai/gpt-4o'))
        self.assertEqual(draft['max_tokens'],2400)
        self.assertIn('mechanism',draft['response_format']['json_schema']['schema']['properties']['comparisons']['items']['required'])

    def test_unknown_adverse_mechanism_cannot_bypass_safety(self):
        self.row['mechanism']='other'
        self.assertIsNotNone(self.issue())

    def test_guest_safety_cannot_be_bypassed_by_choosing_occupancy(self):
        clause='The tenant supplies guest passport copies.'
        row=comparison(clause,'occupancy','occupancy_subletting')
        self.assertIsNotNone(self.issue(row,clause,reference('3.2','occupancy_subletting','Named occupiers supply documents.')))

    def test_dispute_route_does_not_prove_expert_fee_allocation(self):
        clause='The tenant pays the surveyor fees.'
        row=comparison(clause,'expert_evidence_and_fees','dispute_resolution')
        self.assertIsNotNone(self.issue(row,clause,reference('12.2','dispute_resolution','Disputes may go to mediation.')))

    def test_malformed_array_fails_closed_without_exception(self):
        packet={'references':[self.ref],'truncated':False,'topics':['security_deposit']}
        for rows in [None,'text',{}]:
            result=finalize({'comparisons':rows,'unassessed_span_ids':[]},self.clause,packet,'HDB')
            self.assertEqual(result.label,'insufficient_evidence')

    def test_guest_threshold_without_word_guest_in_selected_span_is_unsettled(self):
        clause='Consent is required for persons other than named occupiers staying more than nine consecutive days.'
        row=comparison(clause,'occupancy','occupancy_subletting')
        row['difference']='The contract sets an additional overnight guest duration threshold.'
        self.assertIsNotNone(self.issue(row,clause,reference('1.1','occupancy_subletting','Named occupiers may reside at the premises.')))

    def test_question_cannot_reintroduce_rejected_notice_assertion(self):
        self.row['question']='Can the immediate deduction without prior written notice be changed?'
        self.assertIsNotNone(self.issue())

    def test_owner_permission_cannot_be_given_to_tenant(self):
        clause='The tenant may sublet a bedroom with landlord consent and registration.'
        row=comparison(clause,'subletting_permission','occupancy_subletting')
        row['reference_claim']='The tenant may rent out bedrooms after registration.'
        ref=reference('policy','occupancy_subletting','Flat owners may rent out bedrooms. Their tenants must not rent out the flat or bedrooms.')
        ref.update(source_id='HDB_SYNTHETIC',source_kind='housing_policy_background')
        self.assertIsNotNone(self.issue(row,clause,ref))
        row['reference_claim']='The tenants must not rent out bedrooms.'
        self.assertIsNone(self.issue(row,clause,ref))
        row['reference_claim']='The tenants are not permitted to sublet bedrooms.'
        self.assertIsNone(self.issue(row,clause,ref))

    def test_owner_only_registration_is_not_tenant_subletting_comparator(self):
        clause='The tenant must not sublet the flat or its bedrooms.'
        row=comparison(clause,'subletting_permission','occupancy_subletting')
        row['reference_claim']='Flat owners must register rental tenants.'
        ref=reference('policy','occupancy_subletting','Flat owners must register tenants. Their tenants must not further rent out the flat or bedrooms.')
        ref.update(source_id='HDB_SYNTHETIC',source_kind='housing_policy_background')
        self.assertIsNotNone(self.issue(row,clause,ref))

    def test_default_is_not_exhaustive_landlord_exit_evidence(self):
        clause='The landlord may end the tenancy early because the flat is required for own occupation.'
        row=comparison(clause,'landlord_exit_trigger','termination_notice')
        default=reference('8.1','termination_notice','The landlord may terminate for unremedied default.')
        self.assertIsNotNone(self.issue(row,clause,default))
        positive=reference('7.1','termination_notice','If the tenant pays rent and performs obligations, the tenant may HOLD AND ENJOY the flat during the term.')
        self.assertIsNone(self.issue(row,clause,positive))


@unittest.skipUnless((ROOT/'data/official_sources_v18/index_v18.jsonl').exists(),'Bootstrap references first')
class CoverageTests(unittest.TestCase):
    def setUp(self):
        self.retriever=CoverageRetriever.from_repo(ROOT)

    def test_deadline_query_includes_4_7_without_relying_on_bm25(self):
        packet=self.retriever.packet('If the tenant fails to carry out repair within 14 days after notice, the landlord repairs and recovers the cost.','HDB')
        self.assertIn('4.7',{r.get('clause_id') for r in packet['references']})
        self.assertIn('repair_deadline',packet['coverage'])

    def test_landlord_exit_reserves_positive_quiet_enjoyment(self):
        packet=self.retriever.packet('Either party may terminate the tenancy early on one month notice.','HDB')
        self.assertTrue(any('HOLD AND ENJOY' in r['text'] and 'termination_notice' in r['topics'] for r in packet['references']))

    def test_rent_review_reserves_exact_extension_subclause(self):
        packet=self.retriever.packet('The landlord may review rent for the remaining term after the first year.','HDB')
        self.assertTrue(any('7.1(c)' in r['section'] for r in packet['references']))

    def test_holdover_reserves_end_clause_and_agreed_rent(self):
        packet=self.retriever.packet('After expiry the tenant pays double monthly rent while remaining in occupation.','HDB')
        self.assertTrue({'19.1','1.4','ITEM8'} <= {r.get('clause_id') for r in packet['references']})

    def test_capacity_loss_is_not_silent(self):
        with patch('src.evidence_packet_v19.MAX_TEMPLATES',1):
            packet=self.retriever.packet('Either party may terminate early, the tenant pays monthly rent and utility charges.','HDB')
        self.assertTrue(packet['truncated'])
        self.assertTrue(packet['omitted_required_locations'])

    def test_quotes_are_unchanged_and_housing_not_mixed(self):
        packet=self.retriever.packet('The landlord pays structural repairs and the tenant services air-conditioning every quarter.','HDB')
        for ref in packet['references']:
            self.assertIn(ref['housing_type'],{'HDB','Both'})
            self.assertTrue(any(ref['source_id']==r['source_id'] and ref['section']==r['section'] and ref['text']==r['text']
                                for r in self.retriever.templates+self.retriever.official))
        self.assertLessEqual(sum(len(r['text']) for r in packet['references']),26000)

    def test_offline_never_reads_key_or_calls_model(self):
        with (patch('src.review_v19.local_api_key',side_effect=AssertionError('key')),
              patch('src.review_v19._request_openrouter',side_effect=AssertionError('API'))):
            result=review_clause('HDB','The tenant pays stamp duty.',self.retriever,allow_api=False)
        self.assertEqual(result.label,'insufficient_evidence')
