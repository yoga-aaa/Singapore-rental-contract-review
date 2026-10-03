"""Engineering counterexamples, not a substitute for held-out model scores."""
import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch
from src.condition_facts_v21 import FIELDS,KINDS,SCENARIOS,atoms_issue,rate
from src.mechanism_tasks_v21 import tasks_for
from src.review_v21 import build_request,finalize,validated_extraction,review_clause
from src.evidence_packet_v19 import CoverageRetriever
from src.condition_diagnostics_v21 import diagnose
from tests.test_review_v20 import packet,reference

ROOT=Path(__file__).resolve().parents[1]


def terms(text):
    # Literal fixtures only; no claimed automatic condition extractor here.
    chunks=[]
    while text:
        end=min(160,len(text))
        if end<len(text): end=text.rfind(' ',0,end)
        chunks.append(text[:end]); text=text[end:].lstrip()
    result={k:'' for k in FIELDS}
    for k,value in zip(('action','trigger','deadline_rate','prerequisite','exception'),chunks): result[k]=value
    return result


def comparison(task,clause,refs,relation='tenant_adverse'):
    from src.contract_spans import contract_spans
    spans=contract_spans(clause)
    text=' '.join(spans[c] for c in task['contract_span_ids'])
    kind=KINDS.get(task['mechanism'],'none') if relation=='tenant_adverse' else 'none'
    return {'task_id':task['task_id'],'contract_terms':terms(text),
            'reference_terms':[{'reference_id':r['evidence_id'],'terms':terms(r['text'])} for r in refs],
            'relation':relation,'contrast_kind':kind,'scenario':SCENARIOS.get(kind,'none'),'decision':'supported'}


def run(clause,refs,mechanism,relation='tenant_adverse',updates=None,housing='HDB'):
    p=packet(*refs); ts,_=tasks_for(clause,p,housing)
    task=next(t for t in ts if t['mechanism']==mechanism)
    row=comparison(task,clause,refs,relation)
    if updates: row.update(updates)
    raw={'comparisons':[row],'unassessed_task_ids':[t['task_id'] for t in ts if t!=task]}
    return finalize(raw,clause,p,housing),row,task


class V21ConditionTests(unittest.TestCase):
    def setUp(self):
        self.ref=reference('2.2','The deposit balance is refunded when the Term expires or is terminated, after reasonable deductions to remedy breach.')
        self.clause='The Landlord refunds the deposit within seventeen days after handover.'

    def test_window_risk_different_numbers_not_memorised(self):
        for days in ['nine','seventeen','thirty','7','26']:
            clause=f'The Landlord refunds the deposit within {days} days after handover.'
            result,_,_=run(clause,[self.ref],'refund_trigger')
            self.assertEqual(result.label,'review_required',days)
            self.assertIn('not a statutory zero-day',result.reason)

    def test_different_words_same_refund_event_not_risk(self):
        clause='The deposit is returned when the tenancy period ends.'
        result,_,_=run(clause,[self.ref],'refund_trigger','equivalent')
        self.assertEqual(result.label,'no_material_difference_found')
        result,_,_=run(clause,[self.ref],'refund_trigger')
        self.assertEqual(result.label,'insufficient_evidence')

    def test_action_trigger_schema_order_does_not_change_quote_order(self):
        result,row,task=run(self.clause,[self.ref],'refund_trigger')
        row['contract_terms']={k:'' for k in FIELDS}
        row['contract_terms'].update(actor='Landlord',action='refunds the deposit',
                                     trigger='after handover',deadline_rate='within seventeen days')
        result=finalize({'comparisons':[row],'unassessed_task_ids':[]},self.clause,packet(self.ref),'HDB')
        self.assertEqual(result.label,'review_required')

    def test_positive_reference_needed_no_silence_inference(self):
        ref=reference('2.2','The Landlord holds the security deposit for performance of obligations.')
        result,_,_=run(self.clause,[ref],'refund_trigger')
        self.assertEqual(result.label,'insufficient_evidence')

    def test_later_window_not_automatically_beneficial_or_equivalent(self):
        for relation in ['tenant_beneficial','equivalent']:
            result,_,_=run(self.clause,[self.ref],'refund_trigger',relation)
            self.assertEqual(result.label,'insufficient_evidence')

    def test_deadline_ambiguity_not_certain_completion_claim(self):
        ref=reference('4.7','Tenant shall proceed with repairs within eleven days. Landlord recovers cost if repairs are not carried out within a reasonable time.')
        clause='If Tenant fails to carry out repair within eleven days of notice, Landlord may repair and recover reasonable cost.'
        result,_,_=run(clause,[ref],'repair_completion_deadline')
        self.assertEqual(result.label,'review_required')
        self.assertIn('may mean completion',result.reason)
        self.assertIn('starting or completing',result.follow_up_question)

    def test_explicit_start_and_reasonable_completion_not_risk(self):
        ref=reference('4.7','Tenant shall proceed with repairs within eleven days and finish within a reasonable time.')
        clause='Tenant shall start repair within eleven days and complete it within a reasonable time; Landlord may recover reasonable costs on failure.'
        result,_,_=run(clause,[ref],'repair_completion_deadline')
        self.assertEqual(result.label,'insufficient_evidence')

    def test_formal_compliance_not_causal_payment_and_not_automatic_tenant_cost(self):
        ref=reference('4.5','Landlord pays for breakdown, repair and replacement unless breakdown is due to Tenant negligence or non-maintenance.')
        clause='Replacement of the air-conditioning is not attributable to Tenant servicing failure; Landlord bears the cost provided that Tenant complied with servicing.'
        result,_,_=run(clause,[ref],'repair_causation')
        self.assertEqual(result.label,'review_required')
        self.assertIn('does not establish that the tenant automatically pays',result.reason)

    def test_causal_obligation_alone_not_noncausal_risk(self):
        ref=reference('4.5','Landlord pays for breakdown and replacement unless breakdown is due to Tenant negligence or non-maintenance.')
        clause='Tenant pays air-conditioning repair costs due to Tenant failure to service.'
        result,_,_=run(clause,[ref],'repair_causation')
        self.assertEqual(result.label,'insufficient_evidence')

    def test_ll_exit_with_reciprocity_notice_compensation_remains_narrow_contrast(self):
        ref=reference('7.1','If Tenant pays rent and performs obligations, Tenant shall HOLD AND ENJOY the flat during the Term without Landlord interruption.')
        for actor in ['Either party','Landlord']:
            clause=f'{actor} may terminate before expiry of the Term with three months notice. Landlord shall not exercise this right during the first fourteen months. Tenant receives relocation compensation.'
            result,_,_=run(clause,[ref],'landlord_exit_trigger')
            self.assertEqual(result.label,'review_required')
            self.assertIn('not an exhaustive prohibition',result.reason)
            self.assertIn('fourteen months',result.comparisons[0]['contract_context'])

    def test_default_only_exit_and_wrong_quiet_scope_not_risk(self):
        ref=reference('7.1','If Tenant pays and performs, Tenant shall HOLD AND ENJOY during the Term.')
        clause='Landlord may terminate before expiry only if Tenant commits a material breach.'
        result,_,_=run(clause,[ref],'landlord_exit_trigger')
        self.assertEqual(result.label,'insufficient_evidence')
        ref=reference('7.1','Landlord may recover rent upon default.')
        result,_,_=run('Landlord may terminate before expiry for own occupation.',[ref],'landlord_exit_trigger')
        self.assertEqual(result.label,'insufficient_evidence')

    def test_holdover_needs_both_source_groups(self):
        end=reference('19.1','After expiry obligations continue until keys are returned.')
        rent=reference('1.4','The agreed rent is the monthly rent in ITEM 8.','R002')
        clause='After expiry Tenant pays double rent while remaining in occupation.'
        result,_,_=run(clause,[end,rent],'holdover_charge')
        self.assertEqual(result.label,'review_required')
        result,_,_=run(clause,[end],'holdover_charge')
        self.assertEqual(result.label,'insufficient_evidence')

    def test_forfeit_vs_reasonable_amount_no_cure_waiver_claim(self):
        clause='If Tenant breaks the tenancy the deposit shall be forfeited. This does not apply to an agreed permitted early exit.'
        result,_,_=run(clause,[self.ref],'deposit_forfeiture_amount')
        self.assertEqual(result.label,'review_required')
        self.assertIn('No notice or cure waiver is inferred',result.reason)
        for clause in ['The deposit shall not be forfeited.',
                       'The amount forfeited from the deposit is limited to reasonable cost to remedy breach.']:
            result,_,_=run(clause,[self.ref],'deposit_forfeiture_amount')
            self.assertEqual(result.label,'insufficient_evidence')

    def test_rent_notice_exit_preserved_not_renewal_only_risk(self):
        ref=reference('1.4','The agreed monthly rent is indicated in ITEM 8.')
        clause='Landlord may revise rent during the Term after the first thirteen months. Tenant receives two months notice and may exit without penalty.'
        result,_,_=run(clause,[ref],'current_term_rent_review')
        self.assertEqual(result.label,'review_required')
        self.assertIn('exit option does not preserve staying',result.reason)
        result,_,_=run('Landlord may review rent only for extension on mutual agreement.',[ref],'current_term_rent_review')
        self.assertEqual(result.label,'insufficient_evidence')

    def test_guest_fees_and_distinct_utility_rules_cannot_be_passed(self):
        fixtures=[('Tenant provides a passport for any guest staying nine days.',reference('1.1','Named occupiers may reside in the premises.'),'guest_documentation'),
                  ('Tenant pays expert report fees.',reference('12.2','Disputes go to mediation.'),'expert_evidence_and_fees'),
                  ('Tenant transfers utility accounts within six days.',reference('2.3','Tenant pays charges for electricity and gas.'),'utilities'),
                  ('Landlord apportions shared utility charges.',reference('2.3','Tenant pays charges for electricity and gas.'),'utilities')]
        for clause,ref,mechanism in fixtures:
            for relation in ['tenant_adverse','equivalent','tenant_beneficial']:
                result,_,_=run(clause,[ref],mechanism,relation)
                self.assertEqual(result.label,'insufficient_evidence',(clause,relation))

    def test_rate_comparison_uses_actual_units_and_cap_scenario(self):
        self.assertEqual(rate('one (1%) per week',r'per week'),1)
        self.assertEqual(rate('one percent (1%) of the outstanding amount for each week or part thereof',r'(?:per|each) week'),1)
        self.assertIsNone(rate('a cap of 5%; the next provision concerns annual fees',r'per week'))
        self.assertEqual(rate('ten (10) percent per annum',r'per annum'),10)
        ref=reference('8.4','If rent is unpaid for seven days, Tenant pays interest of 10% per annum.')
        for percent,expected in [(1,'review_required'),(.01,'insufficient_evidence')]:
            clause=f'If rent is overdue seven days Tenant pays {percent}% per week, capped at 5% of overdue rent.'
            result,_,_=run(clause,[ref],'late_payment_charge')
            self.assertEqual(result.label,expected)
            if expected=='review_required': self.assertIn('not necessarily greater at every duration',result.reason)

    def test_extra_legal_prose_field_is_not_publishable(self):
        result,row,_=run(self.clause,[self.ref],'refund_trigger')
        row['difference']='This is illegal and unenforceable.'
        result=finalize({'comparisons':[row],'unassessed_task_ids':[]},self.clause,packet(self.ref),'HDB')
        self.assertEqual(result.label,'insufficient_evidence')

    def test_malformed_atoms_missing_binding_or_wrong_housing_rejected(self):
        for updates in [{'contract_terms':{k:'fabricated' for k in FIELDS}},
                        {'relation':[]},{'scenario':{}},{'decision':None},
                        {'reference_terms':[{'reference_id':'R999','terms':terms(self.ref['text'])}]}]:
            result,_,_=run(self.clause,[self.ref],'refund_trigger',updates=updates)
            self.assertEqual(result.label,'insufficient_evidence')
        for value in [None,[],{},2]:
            self.assertIsNotNone(atoms_issue({k:value for k in FIELDS},self.clause))
        ref=copy.deepcopy(self.ref); ref['housing_type']='Private Residential'
        result,_,_=run(self.clause,[ref],'refund_trigger')
        self.assertEqual(result.label,'insufficient_evidence')

    def test_unknown_neighbor_does_not_erase_one_valid_risk_but_blocks_pass(self):
        clause=self.clause+' Tenant pays expert report fees.'
        result,_,_=run(clause,[self.ref],'refund_trigger')
        self.assertEqual(result.label,'review_required')
        self.assertEqual(result.comparisons[0]['unassessed_span_ids'],['C002'])
        self.assertEqual(len(result.comparisons),1)
        clause='The deposit is refunded when the Term ends. Tenant pays expert report fees.'
        result,_,_=run(clause,[self.ref],'refund_trigger','equivalent')
        self.assertEqual(result.label,'insufficient_evidence')

    def test_first_stage_has_no_judgement_second_cannot_receive_opinions(self):
        p=packet(self.ref); tasks,_=tasks_for(self.clause,p,'HDB')
        first=build_request('HDB',self.clause,p)
        props=first['response_format']['json_schema']['schema']['properties']['facts']['items']['properties']
        self.assertEqual(set(props),{'task_id','contract_terms','reference_terms'})
        row=comparison(tasks[0],self.clause,[self.ref])
        first_fact={k:row[k] for k in ['task_id','contract_terms','reference_terms']}
        second=build_request('HDB',self.clause,p,{'facts':[first_fact],
                         'unassessed_task_ids':[],'conclusion':'MAGIC_DRAFT_RISK_TOKEN'})
        self.assertNotIn('MAGIC_DRAFT_RISK_TOKEN',json.dumps(second))
        self.assertNotIn('untrusted_draft',json.dumps(second))
        self.assertEqual((first['model'],second['model']),('openai/gpt-4.1','openai/gpt-4o'))
        self.assertEqual(first['max_tokens'],2400)
        data=json.loads(second['messages'][1]['content'])
        self.assertEqual(data['untrusted_literal_extraction']['facts'],[first_fact])

    def test_invalid_extraction_is_discarded_not_repaired_or_judged_as_opinion(self):
        p=packet(self.ref); tasks,_=tasks_for(self.clause,p,'HDB')
        row=comparison(tasks[0],self.clause,[self.ref])
        first_fact={k:row[k] for k in ['task_id','contract_terms','reference_terms']}
        first_fact['contract_terms']['action']='fabricated'
        safe=validated_extraction({'facts':[first_fact]},tasks,self.clause,p)
        self.assertEqual(safe['facts'],[])
        self.assertEqual(safe['rejected_fact_rows'],1)
        request=build_request('HDB',self.clause,p,{'facts':[first_fact]})
        self.assertIn(self.clause,request['messages'][1]['content'])

    def test_model_boundary_no_request_on_unsafe_input(self):
        with patch('src.review_v21._request_openrouter',side_effect=AssertionError('API')):
            result=review_clause('Unknown','Tenant pays rent.',None,api_key='synthetic')
        self.assertTrue(result.abstained)

    def test_only_two_calls_and_second_can_recover_bad_extraction(self):
        p=packet(self.ref); tasks,_=tasks_for(self.clause,p,'HDB')
        row=comparison(tasks[0],self.clause,[self.ref])
        class Retriever:
            def packet(self,*args): return p
        with patch('src.review_v21._request_openrouter',side_effect=[({'facts':'malformed'},{'total_tokens':10}),
                      ({'comparisons':[row],'unassessed_task_ids':[]},{'total_tokens':20})]) as call:
            result=review_clause('HDB',self.clause,Retriever(),api_key='synthetic')
        self.assertEqual(call.call_count,2)
        self.assertEqual(result.usage['total_tokens'],30)
        self.assertEqual(result.label,'review_required')

    def test_full_originals_published_not_compiler_invented_citations(self):
        result,_,_=run(self.clause,[self.ref],'refund_trigger')
        self.assertEqual(result.evidence[0]['quote'],self.ref['text'])
        self.assertEqual(result.comparisons[0]['contract_context'],self.clause)
        self.assertIn('not an independent expert audit',result.comparisons[0]['verification_note'])

    def test_contextual_duplicates_removed_but_distinct_causal_conditions_retained(self):
        ref=reference('1.4','The agreed monthly rent is indicated in ITEM 8.')
        clause='Landlord may review rent during the Term. Tenant may terminate if the revised rent is not accepted. No rent increase applies in the first thirteen months.'
        tasks,_=tasks_for(clause,packet(ref),'HDB')
        self.assertEqual(sum(t['mechanism']=='current_term_rent_review' for t in tasks),1)
        clause='Tenant pays air-conditioning repair cost due to failure to service. Replacement not attributable to servicing failure is paid by Landlord provided that Tenant complied with servicing.'
        tasks,_=tasks_for(clause,packet(reference('4.5','Landlord pays for breakdown unless due to Tenant negligence or non-maintenance.')),'HDB')
        self.assertEqual(sum(t['mechanism']=='repair_causation' for t in tasks),2)

    def test_personal_residence_exit_uses_quiet_not_occupier_proof(self):
        ref=reference('6.1','If Tenant pays rent and performs obligations, Tenant shall HOLD AND ENJOY during the Term.',housing='Private Residential')
        clause='Where Tenant ceases to reside, Landlord may terminate the tenancy with eighteen days notice.'
        result,_,_=run(clause,[ref],'landlord_exit_trigger',housing='Private Residential')
        self.assertEqual(result.label,'review_required')
        self.assertIn('compliant tenant',result.reason)

    def test_same_sublet_consent_condition_not_prohibition_contrast(self):
        ref=reference('5.1','Tenant shall not sublet without prior written consent.')
        result,_,_=run('Tenant shall not sublet without prior written consent.',[ref],'subletting_permission')
        self.assertEqual(result.label,'insufficient_evidence')

    def test_actual_rate_surface_with_qualifiers_not_adjacent_cap_rate(self):
        ref=reference('8.4','If rent remains unpaid seven days, interest is ten percent (10%) per annum.')
        clause='If rent is overdue seven days Tenant pays one percent (1%) of the outstanding amount for each week or part thereof, capped at ten percent (10%).'
        result,_,_=run(clause,[ref],'late_payment_charge')
        self.assertEqual(result.label,'review_required')

    def test_tiny_cap_and_long_grace_cannot_support_short_delay_risk(self):
        ref=reference('8.4','If rent remains unpaid seven days, interest is 10% per annum.')
        for clause in ['If rent is overdue seven days, Tenant pays 1% per week capped at 0.001%.',
                       'If rent is overdue 360 days, Tenant pays 1% per week capped at 5%.']:
            result,_,_=run(clause,[ref],'late_payment_charge')
            self.assertEqual(result.label,'insufficient_evidence')

    def test_default_exit_without_only_still_not_compliant_tenant_risk(self):
        ref=reference('7.1','If Tenant pays rent and performs, Tenant shall HOLD AND ENJOY during the Term.')
        for clause in ['Landlord may terminate before expiry if Tenant commits a material breach.',
                       'Landlord may terminate before expiry where Tenant fails to pay rent.']:
            result,_,_=run(clause,[ref],'landlord_exit_trigger')
            self.assertEqual(result.label,'insufficient_evidence')

    def test_diagnostics_separate_literal_failure_from_release_gate_failure(self):
        p=packet(self.ref); tasks,_=tasks_for(self.clause,p,'HDB')
        row=comparison(tasks[0],self.clause,[self.ref])
        first={k:row[k] for k in ['task_id','contract_terms','reference_terms']}
        first['contract_terms']['action']='invented'
        row['relation']='tenant_beneficial'; row['contrast_kind']='none'; row['scenario']='none'
        result=diagnose({'facts':[first]},{'comparisons':[row]},self.clause,p,'HDB')
        self.assertEqual(result['literal_fact_rows_rejected'],1)
        self.assertIsNotNone(result['checks'][0]['release_gate_issue'])
        self.assertIsNone(result['quality_metrics'])


@unittest.skipUnless((ROOT/'data/official_sources_v18/index_v18.jsonl').exists(),'Bootstrap references first')
class V21OfflineTests(unittest.TestCase):
    def test_offline_never_reads_key_or_spends(self):
        retriever=CoverageRetriever.from_repo(ROOT)
        with (patch('src.review_v21.local_api_key',side_effect=AssertionError('key')),
              patch('src.review_v21._request_openrouter',side_effect=AssertionError('API'))):
            result=review_clause('HDB','Tenant pays the agreed rent.',retriever,allow_api=False)
        self.assertFalse(result.api_called)


if __name__=='__main__': unittest.main()
