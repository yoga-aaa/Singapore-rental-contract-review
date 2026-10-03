import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from src.evidence_packet_v19 import CoverageRetriever
from src.mechanism_tasks_v20 import tasks_for,MAX_TASKS
from src.review_v20 import build_request,finalize,row_issue,shape_issue,review_clause

ROOT=Path(__file__).resolve().parents[1]


def reference(cid,text,rid='R001',housing='HDB'):
    return {'evidence_id':rid,'source_id':'SYNTHETIC_HDB' if housing=='HDB' else 'SYNTHETIC_PRIVATE',
            'housing_type':housing,'source_kind':'tenancy_agreement_template','clause_id':cid,
            'section':'Synthetic '+cid,'topics':[],'text':text}


def packet(*refs):
    return {'references':list(refs),'truncated':False,'topics':[]}


def row(task,facts,relation='tenant_adverse',**updates):
    result={'task_id':task['task_id'],'relation':relation,'reference_facts':facts,
            'difference':'The contract expressly changes the stated payment condition.',
            'tenant_consequence':'The tenant could incur the additional conditional cost.',
            'question':'Can the additional payment condition be clarified?',
            'verdict':'supported','check_note':'The quoted facts support this limited positive contrast.'}
    return {**result,**updates}


def fact(ref,quote=None):
    return {'reference_id':ref['evidence_id'],'quote':quote or ref['text']}


class V20TaskTests(unittest.TestCase):
    def test_landlord_may_deduct_request_report_or_review_is_not_exit(self):
        for clause in ['Landlord may deduct utility charges from the deposit.',
                       'Landlord may request a passport copy for any guest.',
                       'Landlord shall be entitled to review the rent during the Term.',
                       'Tenant may terminate on receiving Landlord notice of rent revision.']:
            tasks,_=tasks_for(clause,packet(),'HDB')
            self.assertNotIn('landlord_exit_trigger',{t['mechanism'] for t in tasks})

    def test_deposit_without_interest_is_not_overdue_payment_interest(self):
        tasks,_=tasks_for('Landlord refunds the deposit without interest within eighteen days after handover.',packet(),'HDB')
        self.assertNotIn('late_payment_charge',{t['mechanism'] for t in tasks})

    def test_rent_without_deduction_is_not_landlord_deposit_deduction(self):
        clause='Tenant pays rent without any deduction or set-off. Landlord may deduct unpaid rent from the deposit.'
        tasks,_=tasks_for(clause,packet(),'HDB')
        self.assertNotIn('deposit_deduction_process',{t['mechanism'] for t in tasks if t['contract_span_ids']==['C001']})

    def test_aircon_gas_and_management_service_charge_not_utilities_or_ac(self):
        tasks,_=tasks_for('Tenant pays air-conditioning repair including gas top-up due to failure to service.',packet(),'HDB')
        self.assertNotIn('utilities',{t['mechanism'] for t in tasks})
        tasks,_=tasks_for('Landlord pays the management monthly service charge.',packet(),'Private Residential')
        self.assertNotIn('ac_servicing',{t['mechanism'] for t in tasks})

    def test_repair_deadline_not_generic_allocation(self):
        clause='If Tenant fails to carry out repair within 11 days, Landlord repairs and recovers costs.'
        p=packet(reference('4.7','Proceed with works within 11 days; complete within a reasonable time.'))
        tasks,_=tasks_for(clause,p,'HDB')
        self.assertEqual(tasks[0]['mechanism'],'repair_completion_deadline')
        self.assertIn('reasonable time',tasks[0]['required_fact_terms'])

    def test_aircon_noncausal_compliance_has_distinct_task(self):
        clause='Air-conditioning replacement is not attributable to failure to service, and the Landlord pays provided that Tenant complied with servicing.'
        tasks,_=tasks_for(clause,packet(reference('4.5','Landlord pays unless breakdown is caused by non-maintenance.')),'HDB')
        self.assertEqual(tasks[0]['mechanism'],'repair_causation')

    def test_landlord_exit_preserves_lock_and_compensation_context(self):
        clause='Landlord may terminate for own occupation on two months notice. Landlord shall not exercise this right in the first thirteen months. Tenant receives relocation compensation.'
        tasks,_=tasks_for(clause,packet(reference('7.1','If Tenant pays and performs obligations, Tenant may HOLD AND ENJOY during the Term.')),'HDB')
        self.assertEqual(tasks[0]['mechanism'],'landlord_exit_trigger')
        self.assertEqual(tasks[0]['contract_span_ids'],['C001','C002','C003'])

    def test_holdover_requires_two_positive_reference_groups(self):
        clause='After expiry Tenant pays double rent while remaining in occupation.'
        tasks,_=tasks_for(clause,packet(reference('19.1','End obligations continue until keys are returned.'),reference('1.4','Rent means the rent agreed for the Term.','R002')),'HDB')
        self.assertEqual(tasks[0]['mechanism'],'holdover_charge')
        self.assertEqual(tasks[0]['required_reference_groups'],[['R001'],['R002']])
        self.assertEqual(tasks[0]['topic'],'rent')

    def test_guest_named_occupier_is_not_a_required_guest_source(self):
        clause='Tenant provides the passport of any guest staying nine consecutive days.'
        tasks,_=tasks_for(clause,packet(reference('1.1','Named occupiers may reside at the premises.')),'HDB')
        self.assertEqual(tasks[0]['required_reference_groups'],[[]])

    def test_cap_is_explicit_and_unknown_span_is_unsettled(self):
        tasks,truncated=tasks_for(' '.join(['Tenant must pay an unspecified charge.']*(MAX_TASKS+2)),packet(),'HDB')
        self.assertTrue(truncated)
        self.assertEqual(len(tasks),MAX_TASKS)
        self.assertTrue(all(t['mechanism']=='other' for t in tasks))

    def test_blank_optional_break_is_not_fixed_period_standard(self):
        clause='Tenant may terminate the tenancy once after eleven months with documentary evidence.'
        ref=reference('ITEM16','The Tenant may terminate after a period agreed in ITEM16 by providing documentary evidence.')
        tasks,_=tasks_for(clause,packet(ref),'HDB')
        self.assertEqual(tasks[0]['mechanism'],'tenant_break_clause')
        self.assertIn('Blank negotiated periods are not standards',tasks[0]['comparison_question'])


class V20ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.clause='The Landlord returns the deposit within nineteen days after handover.'
        self.ref=reference('2.2','The deposit is refunded when the Term expires or is terminated.')
        self.p=packet(self.ref)
        self.tasks,_=tasks_for(self.clause,self.p,'HDB')
        self.row=row(self.tasks[0],[fact(self.ref)],difference='The contract allows a nineteen-day post-handover window rather than refund when the term ends.',
                     tenant_consequence='Receipt could occur later under the stated handover-linked window.')

    def run_result(self,rows=None,unassessed=None,clause=None,p=None):
        return finalize({'comparisons':rows if rows is not None else [self.row],
                         'unassessed_task_ids':unassessed or []},clause or self.clause,p or self.p,'HDB')

    def test_exact_facts_and_full_source_released_without_label_claim(self):
        result=self.run_result()
        self.assertEqual(result.label,'review_required')
        self.assertEqual(result.evidence[0]['quote'],self.ref['text'])
        self.assertEqual(result.comparisons[0]['reference_facts'],[fact(self.ref)])
        self.assertIn('all other terms remain unapproved',result.reason)

    def test_supported_same_meaning_wording_passes_without_exact_contract_match(self):
        clause='The Landlord refunds the deposit when the tenancy period ends.'
        result=self.run_result([self.row | {'relation':'equivalent','tenant_consequence':'',
                                               'difference':'Both refund the deposit when the agreed tenancy period ends.'}],clause=clause)
        self.assertEqual(result.label,'no_material_difference_found')
        self.assertNotEqual(clause,self.ref['text'])

    def test_paraphrased_or_invented_reference_fact_is_rejected(self):
        self.row['reference_facts'][0]['quote']='The landlord must refund immediately without exceptions.'
        self.assertEqual(self.run_result().label,'insufficient_evidence')

    def test_malformed_memberships_fail_closed_without_exception(self):
        for key in ['task_id','relation','verdict']:
            for value in [[],{},None,4]:
                bad={**self.row,key:value}
                with self.subTest(key=key,value=value):
                    self.assertEqual(self.run_result([bad]).label,'insufficient_evidence')

    def test_duplicate_tasks_unknown_tasks_and_fact_objects_rejected(self):
        for bad in [self.row | {'task_id':'T999'},self.row | {'reference_facts':None},self.row | {'reference_facts':[{'quote':self.ref['text']}]}]:
            self.assertEqual(self.run_result([bad]).label,'insufficient_evidence')
        self.assertEqual(self.run_result([self.row,self.row]).label,'insufficient_evidence')

    def test_silence_and_legal_claims_in_any_free_field_are_rejected(self):
        for key in ['difference','tenant_consequence','question','check_note']:
            for claim in ['This is illegal and unenforceable?', 'Further damages are not mentioned in this reference?']:
                with self.subTest(key=key,claim=claim):
                    self.assertEqual(self.run_result([self.row | {key:claim}]).label,'insufficient_evidence')

    def test_material_literal_qualifier_not_retained_is_rejected(self):
        self.row['reference_facts'][0]['quote']='The deposit is refunded'
        self.assertEqual(self.run_result().label,'insufficient_evidence')

    def test_refund_window_is_not_beneficial_from_clarity(self):
        self.assertEqual(self.run_result([self.row | {'relation':'tenant_beneficial'}]).label,'insufficient_evidence')

    def test_wrong_housing_fails_even_with_exact_source_quote(self):
        self.ref['housing_type']='Private Residential'
        self.assertEqual(self.run_result().label,'insufficient_evidence')

    def test_unrequested_neighbor_source_cannot_be_added(self):
        unrelated=reference('19.1','End obligations continue until keys are returned.','R002')
        self.p['references'].append(unrelated)
        self.row['reference_facts'].append(fact(unrelated))
        self.assertEqual(self.run_result().label,'insufficient_evidence')

    def test_unsettled_neighbor_does_not_erase_limited_valid_risk(self):
        clause=self.clause+' Tenant pays an unspecified expert fee.'
        result=self.run_result(clause=clause)
        self.assertEqual(result.label,'review_required')
        self.assertEqual(result.comparisons[0]['unassessed_span_ids'],['C002'])
        self.assertEqual(len(result.comparisons),1)

    def test_unknown_neighbor_prevents_whole_clause_pass(self):
        clause='The deposit is refunded when the Term ends. Tenant pays an unspecified expert fee.'
        self.assertEqual(self.run_result([self.row | {'relation':'equivalent'}],clause=clause).label,'insufficient_evidence')

    def test_uncertain_and_unsupported_are_not_published(self):
        for updates in [{'verdict':'unsupported'},{'verdict':'uncertain'},{'relation':'uncertain','reference_facts':[]}]:
            self.assertEqual(self.run_result([self.row | updates]).label,'insufficient_evidence')

    def test_known_limited_risk_does_not_hide_task_cap(self):
        clause=self.clause+' '+' '.join(['Tenant pays an unspecified expert fee.']*13)
        result=self.run_result(clause=clause)
        self.assertEqual(result.label,'review_required')
        self.assertIn('C014',result.comparisons[0]['unassessed_span_ids'])

    def test_causal_obligation_not_invented_as_noncausal_risk(self):
        clause='Tenant pays air-conditioning replacement costs due to failure to service.'
        ref=reference('4.5','Landlord pays unless breakdown is due to Tenant non-maintenance.')
        tasks,_=tasks_for(clause,packet(ref),'HDB')
        bad=row(tasks[0],[fact(ref)],tenant_consequence='Tenant pays even if they did not cause the breakdown.')
        self.assertEqual(self.run_result([bad],clause=clause,p=packet(ref)).label,'insufficient_evidence')

    def test_additional_formal_compliance_can_be_supported_without_omission_gate(self):
        clause='Air-conditioning replacement is not attributable to failure to service, and Landlord pays provided that Tenant complied with servicing.'
        ref=reference('4.5','Landlord pays unless breakdown is due to Tenant non-maintenance.')
        tasks,_=tasks_for(clause,packet(ref),'HDB')
        good=row(tasks[0],[fact(ref)],difference='The contract adds formal servicing compliance to payment where the breakdown is not attributable to Tenant.',
                 tenant_consequence='Tenant could bear costs despite not causing the fault.')
        self.assertEqual(self.run_result([good],clause=clause,p=packet(ref)).label,'review_required')
        self.assertEqual(self.run_result([good | {'relation':'equivalent'}],clause=clause,p=packet(ref)).label,'insufficient_evidence')

    def test_holdover_end_source_alone_is_not_enough(self):
        clause='After expiry Tenant pays double rent while remaining in occupation.'
        end=reference('19.1','End obligations continue until keys are returned.')
        rent=reference('1.4','Rent means the rent agreed for the Term.','R002')
        p=packet(end,rent); tasks,_=tasks_for(clause,p,'HDB')
        good=row(tasks[0],[fact(end),fact(rent)])
        self.assertEqual(self.run_result([good],clause=clause,p=p).label,'review_required')
        self.assertEqual(self.run_result([good | {'reference_facts':[fact(end)]}],clause=clause,p=p).label,'insufficient_evidence')

    def test_deadline_not_equivalent_but_ambiguity_can_be_clarified(self):
        clause='If Tenant fails to carry out repair within eleven days, Landlord repairs and recovers cost.'
        ref=reference('4.7','Proceed with repairs within eleven days and complete within a reasonable time.')
        tasks,_=tasks_for(clause,packet(ref),'HDB'); good=row(tasks[0],[fact(ref)])
        self.assertEqual(self.run_result([good | {'relation':'equivalent'}],clause=clause,p=packet(ref)).label,'insufficient_evidence')
        good.update(difference='The carry-out trigger may require completion, unlike separate starting and reasonable-time completion.',question='Does carry out mean start or finish the repairs in this period?')
        self.assertEqual(self.run_result([good],clause=clause,p=packet(ref)).label,'review_required')

    def test_blank_and_once_break_are_not_material_disadvantages(self):
        clause='Tenant may terminate once after eleven months with documentary evidence.'
        ref=reference('ITEM16','Tenant may terminate after the period agreed in ITEM16 with documentary evidence.')
        tasks,_=tasks_for(clause,packet(ref),'HDB')
        for diff in ['The once-only exit limits multiple times of termination.','A blank optional period should instead be fixed 12 months.']:
            bad=row(tasks[0],[fact(ref)],difference=diff)
            self.assertEqual(self.run_result([bad],clause=clause,p=packet(ref)).label,'insufficient_evidence')

    def test_guest_documents_and_expert_fees_remain_unsettled(self):
        for clause,ref in [('Tenant provides a passport copy for any guest.',reference('1.1','Named occupiers may reside at the premises.')),
                           ('Tenant pays the expert report fees.',reference('12.2','Disputes may proceed to mediation.'))]:
            tasks,_=tasks_for(clause,packet(ref),'HDB'); bad=row(tasks[0],[fact(ref)])
            self.assertEqual(self.run_result([bad],clause=clause,p=packet(ref)).label,'insufficient_evidence')

    def test_generic_utility_payer_cannot_settle_transfer_supply_or_apportionment(self):
        for clause in ['Tenant transfers utility accounts within six days.',
                       'Landlord is not responsible for utility supply interruption except its own acts.',
                       'Landlord apportions shared utility charges and supplies calculations.',
                       'Landlord imposes no surcharge on utility charges.']:
            ref=reference('2.3','Tenant pays charges for water, electricity and gas during the Term.')
            tasks,_=tasks_for(clause,packet(ref),'HDB'); bad=row(tasks[0],[fact(ref)])
            for relation in ['tenant_adverse','equivalent','tenant_beneficial']:
                with self.subTest(clause=clause,relation=relation):
                    self.assertEqual(self.run_result([bad | {'relation':relation}],clause=clause,p=packet(ref)).label,'insufficient_evidence')

    def test_request_has_fixed_tasks_literal_facts_and_same_two_models(self):
        draft=build_request('HDB',self.clause,self.p)
        verify=build_request('HDB',self.clause,self.p,{'comparisons':[],'unassessed_task_ids':[]})
        self.assertEqual((draft['model'],verify['model']),('openai/gpt-4.1','openai/gpt-4o'))
        data=json.loads(draft['messages'][1]['content'])
        self.assertEqual(data['untrusted_contract'],self.clause)
        self.assertEqual(data['tasks'],self.tasks)
        self.assertNotIn('ground_truth_label',json.dumps(data))
        props=draft['response_format']['json_schema']['schema']['properties']['comparisons']['items']['properties']
        self.assertNotIn('topic',props)
        self.assertNotIn('mechanism',props)
        self.assertEqual(props['task_id']['enum'],['T001'])


@unittest.skipUnless((ROOT/'data/official_sources_v18/index_v18.jsonl').exists(),'Bootstrap references first')
class V20OfflineTests(unittest.TestCase):
    def test_offline_never_reads_key_or_calls_model(self):
        retriever=CoverageRetriever.from_repo(ROOT)
        with (patch('src.review_v20.local_api_key',side_effect=AssertionError('key')),
              patch('src.review_v20._request_openrouter',side_effect=AssertionError('API'))):
            result=review_clause('HDB','Tenant pays stamp duty.',retriever,allow_api=False)
        self.assertFalse(result.api_called)


if __name__=='__main__': unittest.main()
