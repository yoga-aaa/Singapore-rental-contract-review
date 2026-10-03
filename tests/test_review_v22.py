"""Structural counterexamples and simulated provider traces, not model scores."""
import copy
import json
import unittest
from unittest.mock import patch
from src.contract_spans import contract_spans
from src.condition_checks_v22 import assess,row_issue
from src.mechanism_tasks_v22 import plan_for,tasks_for,window_for,candidate_tasks
from src.review_v22 import request,stage_plan,audit_agreement,review_clause
from src.routing_text_v22 import match_text
from tests.test_review_v20 import packet,reference
from tests.test_review_v21 import terms
from src.condition_facts_v21 import KINDS,SCENARIOS


def make_row(task,clause,refs,relation='tenant_adverse',actor=None):
    text=' '.join(contract_spans(clause)[c] for c in task['contract_span_ids'])
    c=terms(text)
    if actor is None:
        for a in ['Either party','Landlord','Lessor','Tenant','Lessee']:
            if a in text: actor=a; break
    c['actor']=actor or ''
    kind=KINDS.get(task['mechanism'],'none') if relation=='tenant_adverse' else 'none'
    return {'task_id':task['task_id'],'contract_terms':c,
            'reference_terms':[{'reference_id':r['evidence_id'],'terms':terms(r['text'])} for r in refs],
            'relation':relation,'contrast_kind':kind,'scenario':SCENARIOS.get(kind,'none'),'decision':'supported',
            'checked_context_ids':list(task['contract_span_ids'])}


def response(row,unassessed=()):
    return {'comparisons':[row],'unassessed_task_ids':list(unassessed)}


class V22RouterTests(unittest.TestCase):
    def test_aliases_do_not_rewrite_original_quote(self):
        text='The Lessor pays back the deposit no later than twelve days following surrender of keys.'
        self.assertIn('Landlord refunds the deposit within twelve days after handover',match_text(text))
        p=packet(reference('2.2','The deposit is refunded when the Term expires.'))
        task=next(t for t in tasks_for(text,p,'HDB')[0] if t['mechanism']=='refund_trigger')
        self.assertEqual(contract_spans(text)[task['contract_span_ids'][0]],text)

    def test_date_fragment_and_deposit_share_bound_context(self):
        clause='The Landlord refunds the deposit. This is paid within nine days after handover.'
        tasks,_=tasks_for(clause,packet(),'HDB')
        refunds=[t for t in tasks if t['mechanism']=='refund_trigger']
        self.assertEqual(len(refunds),1)
        self.assertEqual(refunds[0]['contract_span_ids'],['C001','C002'])

    def test_pronoun_does_not_cross_blank_paragraph(self):
        clause='The Landlord refunds the deposit.\n\nThis is paid within nine days after handover.'
        self.assertEqual(window_for('C002',contract_spans(clause),clause),['C002'])

    def test_aggregate_under_this_clause_inherits_original_repair_context(self):
        clause='Tenant pays minor repair costs. The aggregate liability under this clause is capped at S$900 annually.'
        plan=plan_for(clause,packet(),'HDB')
        self.assertNotIn('other',{t['mechanism'] for t in plan['tasks']})
        repair=next(t for t in plan['tasks'] if t['mechanism']=='repair_allocation')
        self.assertEqual(repair['contract_span_ids'],['C001','C002'])

    def test_unrelated_guest_or_expert_topic_not_inherited(self):
        for second in ['Such expert report fees are paid by Tenant.','Such guests must supply passports.']:
            clause='The Landlord refunds the deposit. '+second
            self.assertEqual(window_for('C002',contract_spans(clause),clause),['C002'])

    def test_aircon_elsewhere_not_all_repairs_aircon(self):
        clause='Tenant services the air-conditioning quarterly. Landlord repairs structural pipes.'
        tasks,_=tasks_for(clause,packet(),'HDB')
        selected=[t for t in tasks if 'C002' in t['contract_span_ids']]
        self.assertIn('repair_allocation',{t['mechanism'] for t in selected})
        self.assertNotIn('repair_causation',{t['mechanism'] for t in selected})

    def test_causal_and_noncausal_conditions_remain_separate(self):
        clause='Tenant pays air-conditioning replacement due to failure to service. Landlord pays air-conditioning replacement not attributable to servicing failure provided that Tenant complied with servicing.'
        tasks,_=tasks_for(clause,packet(),'HDB')
        causal=[t for t in tasks if t['mechanism']=='repair_causation']
        self.assertEqual(len(causal),2)
        self.assertNotEqual(causal[0]['contract_span_ids'],causal[1]['contract_span_ids'])

    def test_duplicates_before_cap_do_not_cause_false_truncation(self):
        clause=' '.join(f'Landlord may review rent during the Term after the first {n} months.' for n in range(2,20))
        plan=plan_for(clause,packet(),'HDB')
        self.assertGreater(plan['candidate_count'],12)
        self.assertEqual(plan['deduplicated_count'],1)
        self.assertFalse(plan['truncated'])

    def test_important_later_mechanism_not_displaced_by_boilerplate(self):
        clause=' '.join(['Tenant pays an unspecified fee.']*13)+' Landlord refunds the deposit within nineteen days after handover.'
        plan=plan_for(clause,packet(),'HDB')
        self.assertTrue(plan['truncated'])
        self.assertIn('refund_trigger',{t['mechanism'] for t in plan['tasks']})
        self.assertEqual(len(plan['dropped_tasks']),2)

    def test_real_drops_are_explicit_and_unknown_cannot_be_approved(self):
        plan=plan_for(' '.join(['Tenant pays an unspecified fee.']*14),packet(),'HDB')
        self.assertEqual(len(plan['tasks']),12)
        self.assertEqual(len(plan['dropped_tasks']),2)
        self.assertTrue(plan['truncated'])

    def test_invalid_selection_capacity_rejected(self):
        for cap in [0,13,True,1.5]:
            with self.assertRaises(ValueError): plan_for('Tenant pays rent.',packet(),'HDB',cap)


class V22PipelineTests(unittest.TestCase):
    def setUp(self):
        self.clause='The Landlord refunds the deposit within seventeen days after handover.'
        self.ref=reference('2.2','The deposit balance is refunded when the Term expires or is terminated.')
        self.p=packet(self.ref)
        self.tasks,_=tasks_for(self.clause,self.p,'HDB')
        self.task=next(t for t in self.tasks if t['mechanism']=='refund_trigger')
        self.row=make_row(self.task,self.clause,[self.ref])
        self.raw=response(self.row)
        class Retriever:
            def packet(inner,*args): return self.p
        self.retriever=Retriever()

    def call(self,replies,clause=None,retriever=None):
        with patch('src.review_v22._request_openrouter',side_effect=[(r,{'total_tokens':10}) for r in replies]) as model:
            result=review_clause('HDB',clause or self.clause,retriever or self.retriever,api_key='synthetic-test-only')
        return result,model

    def test_valid_risk_requires_third_independent_audit(self):
        result,model=self.call([{'facts':[]},self.raw,self.raw])
        self.assertEqual(model.call_count,3)
        self.assertEqual(result.label,'review_required')
        self.assertEqual(result.comparisons[0]['pipeline_stages'],['extract','compare','audit'])

    def test_audit_rejects_risk_no_fourth_retry(self):
        audited=response({**self.row,'relation':'uncertain','decision':'uncertain','contrast_kind':'none','scenario':'none'})
        result,model=self.call([{'facts':[]},self.raw,audited])
        self.assertEqual(result.label,'insufficient_evidence')
        self.assertEqual(model.call_count,3)

    def test_misclassified_condition_recovers_then_audits_with_fourth_call(self):
        wrong=response({**self.row,'relation':'tenant_beneficial','contrast_kind':'none','scenario':'none'})
        result,model=self.call([{'facts':[]},wrong,self.raw,self.raw])
        self.assertEqual(result.label,'review_required')
        self.assertEqual(model.call_count,4)
        self.assertEqual(result.comparisons[0]['pipeline_stages'],['extract','compare','correct','audit'])
        self.assertEqual(model.call_args_list[-1].args[0]['model'],'openai/gpt-4o')

    def test_corrective_uncertainty_is_not_retried(self):
        uncertain=response({**self.row,'relation':'uncertain','decision':'uncertain','contrast_kind':'none','scenario':'none'})
        result,model=self.call([{'facts':[]},uncertain,uncertain])
        self.assertEqual(result.label,'insufficient_evidence')
        self.assertEqual(model.call_count,3)

    def test_malformed_focused_correction_stops_without_exception_or_audit(self):
        uncertain=response({**self.row,'relation':'uncertain','decision':'uncertain','contrast_kind':'none','scenario':'none'})
        for bad in [None,{'comparisons':[self.row],'unassessed_task_ids':[{}]},
                    {'comparisons':[self.row],'unassessed_task_ids':['UNKNOWN']},
                    {'comparisons':[self.row,self.row],'unassessed_task_ids':[]}]:
            with self.subTest(bad=bad):
                result,model=self.call([{'facts':[]},uncertain,bad])
                self.assertEqual(result.label,'insufficient_evidence')
                self.assertEqual(model.call_count,3)

    def test_unrequested_correction_is_not_imported(self):
        uncertain=response({**self.row,'relation':'uncertain','decision':'uncertain','contrast_kind':'none','scenario':'none'})
        bad=response({**self.row,'task_id':'UNKNOWN'})
        result,model=self.call([{'facts':[]},uncertain,bad])
        self.assertEqual(result.label,'insufficient_evidence')
        self.assertEqual(model.call_count,3)

    def test_wrong_housing_audit_cannot_release_conclusion(self):
        bad=copy.deepcopy(self.p); bad['references'][0]['housing_type']='Private Residential'
        checked=assess(self.raw,self.tasks,self.clause,bad,'HDB')
        self.assertFalse(checked['accepted'])
        self.assertEqual(checked['issues'][0]['code'],'wrong_housing')

    def test_provider_failure_is_not_automatically_retried(self):
        with patch('src.review_v22._request_openrouter',side_effect=RuntimeError('synthetic provider failure')) as model:
            with self.assertRaises(RuntimeError):
                review_clause('HDB',self.clause,self.retriever,api_key='synthetic-test-only')
        self.assertEqual(model.call_count,1)

    def test_missing_literal_can_be_reselected_from_original(self):
        bad=copy.deepcopy(self.row); bad['contract_terms']['action']='not in the contract'
        result,model=self.call([{'facts':[]},response(bad),self.raw,self.raw])
        self.assertEqual(result.label,'review_required')
        self.assertEqual(model.call_count,4)

    def test_wrong_actor_not_accepted_even_with_literal_quote(self):
        clause='The Landlord refunds the deposit within seventeen days after handover. Tenant pays rent.'
        tasks,_=tasks_for(clause,self.p,'HDB')
        task=next(t for t in tasks if t['mechanism']=='refund_trigger')
        row=make_row(task,clause,[self.ref],actor='Tenant')
        issue=row_issue(row,task,clause,{'R001':self.ref},'HDB')
        self.assertIsNotNone(issue)

    def test_missing_context_blocks_release_and_can_trigger_recheck(self):
        row={**self.row,'checked_context_ids':[]}
        plan=stage_plan(response(row),self.clause,self.p,'HDB')
        self.assertEqual(plan['stage'],'correct')
        self.assertEqual(plan['assessment']['issues'][0]['code'],'missing_context')

    def test_term_end_upper_bound_overrides_later_window_fragment(self):
        for safeguard in ['but no later than expiry','but by termination']:
            clause=self.clause[:-1]+', '+safeguard+'.'
            tasks,_=tasks_for(clause,self.p,'HDB')
            row=make_row(next(t for t in tasks if t['mechanism']=='refund_trigger'),clause,[self.ref])
            checked=assess(response(row),tasks,clause,self.p,'HDB')
            self.assertFalse(checked['accepted'])

    def test_low_cap_and_long_grace_remain_blocked(self):
        ref=reference('8.4','Tenant pays interest at 10% per annum on unpaid rent.')
        p=packet(ref)
        for clause in ['If rent is overdue seven days, Tenant pays 1% per week capped at 0.001%.',
                       'If rent is overdue 360 days, Tenant pays 1% per week capped at 5%.']:
            tasks,_=tasks_for(clause,p,'HDB')
            task=next(t for t in tasks if t['mechanism']=='late_payment_charge')
            row=make_row(task,clause,[ref],actor='Tenant')
            self.assertFalse(assess(response(row),tasks,clause,p,'HDB')['accepted'])

    def test_causal_only_replacement_does_not_become_noncausal_risk(self):
        clause='The Landlord pays replacement unless breakdown of the air-conditioning is due to Tenant negligence or failure to service.'
        ref=reference('4.5','Landlord pays replacement unless breakdown is due to Tenant negligence or non-maintenance.')
        p=packet(ref); tasks,_=tasks_for(clause,p,'HDB')
        row=make_row(next(t for t in tasks if t['mechanism']=='repair_causation'),clause,[ref])
        self.assertFalse(assess(response(row),tasks,clause,p,'HDB')['accepted'])

    def test_audit_does_not_receive_candidate_extraction_or_relation(self):
        for stage in ['correct','audit']:
            req=request('HDB',self.clause,self.p,stage,{'facts':'SECRET_PRIOR_OPINION'},[self.task['task_id']])
            user=json.loads(req['messages'][1]['content'])
            self.assertNotIn('SECRET_PRIOR_OPINION',req['messages'][1]['content'])
            self.assertNotIn('candidate_rows',user)
            self.assertNotIn('untrusted_literal_extraction',user)
            self.assertEqual(user['untrusted_contract'],self.clause)

    def test_source_gap_does_not_start_recovery(self):
        clause='Tenant provides passport copies for guests.'
        ref=reference('1.1','Named occupiers may reside in the flat.')
        p=packet(ref); tasks,_=tasks_for(clause,p,'HDB')
        task=next(t for t in tasks if t['mechanism']=='guest_documentation')
        row=make_row(task,clause,[ref],'equivalent')
        plan=stage_plan(response(row),clause,p,'HDB')
        self.assertEqual(plan['stage'],'stop')

    def test_utility_transfer_not_settled_by_generic_payer(self):
        clause='Tenant transfers utility accounts within six days.'
        ref=reference('2.3','Tenant pays electricity and water charges.')
        p=packet(ref); ts,_=tasks_for(clause,p,'HDB')
        row=make_row(ts[0],clause,[ref],'equivalent')
        plan=stage_plan(response(row),clause,p,'HDB')
        self.assertEqual(plan['stage'],'stop')

    def test_duplicate_or_contradictory_unassessed_response_not_released(self):
        raw={'comparisons':[self.row,self.row],'unassessed_task_ids':[]}
        self.assertEqual(stage_plan(raw,self.clause,self.p,'HDB')['stage'],'stop')
        raw=response(self.row,[self.task['task_id']])
        self.assertNotEqual(stage_plan(raw,self.clause,self.p,'HDB')['stage'],'audit')

    def test_audit_agreement_requires_matching_risk_scenario(self):
        bad={**self.row,'scenario':'short_overdue_period_before_cap'}
        self.assertIsNone(audit_agreement([self.row],response(bad),self.tasks,self.clause,self.p,'HDB'))

    def test_support_is_not_inferred_from_binding_or_claimed_coverage(self):
        bad=copy.deepcopy(self.row)
        bad['reference_terms'][0]['terms']=terms('The deposit balance is refunded')
        checked=assess(response(bad),self.tasks,self.clause,self.p,'HDB')
        self.assertFalse(checked['accepted'])

    def test_unknown_neighbor_kept_unapproved_after_valid_audit(self):
        clause=self.clause+' Tenant pays an unspecified expert fee.'
        tasks,_=tasks_for(clause,self.p,'HDB')
        task=next(t for t in tasks if t['mechanism']=='refund_trigger')
        row=make_row(task,clause,[self.ref])
        raw=response(row,[t['task_id'] for t in tasks if t!=task])
        result,model=self.call([{'facts':[]},raw,response(row)],clause=clause)
        self.assertEqual(result.label,'review_required')
        self.assertEqual(result.comparisons[0]['unassessed_span_ids'],['C002'])

    def test_bound_aliases_work_without_fake_quotation(self):
        clause='The Lessor pays back the deposit no later than twelve days following handover.'
        tasks,_=tasks_for(clause,self.p,'HDB')
        row=make_row(next(t for t in tasks if t['mechanism']=='refund_trigger'),clause,[self.ref])
        result,model=self.call([{'facts':[]},response(row),response(row)],clause=clause)
        self.assertEqual(result.label,'review_required')
        self.assertEqual(result.evidence[0]['quote'],self.ref['text'])
        self.assertEqual(result.comparisons[0]['contract_quote'],clause)

    def test_same_meaning_pass_requires_full_independent_audit(self):
        clause='The Landlord refunds the deposit when the Term ends.'
        tasks,_=tasks_for(clause,self.p,'HDB')
        rows=[make_row(t,clause,[self.ref],'equivalent') for t in tasks]
        raw={'comparisons':rows,'unassessed_task_ids':[]}
        result,model=self.call([{'facts':[]},raw,raw],clause=clause)
        self.assertEqual(result.label,'no_material_difference_found')
        self.assertEqual(model.call_count,3)

    def test_no_key_or_model_in_offline_mode_and_unsafe_input(self):
        with (patch('src.review_v22.local_api_key',side_effect=AssertionError('key')),
              patch('src.review_v22._request_openrouter',side_effect=AssertionError('API'))):
            for housing,text in [('HDB',self.clause),('Unknown','Tenant pays rent.')]:
                result=review_clause(housing,text,None,allow_api=False)
                self.assertFalse(result.api_called)

    def test_no_legal_free_text_schema_channel(self):
        req=request('HDB',self.clause,self.p,'compare',{})
        props=req['response_format']['json_schema']['schema']['properties']['comparisons']['items']['properties']
        self.assertNotIn('reason',props)
        self.assertNotIn('difference',props)
        self.assertNotIn('final_label',props)


if __name__=='__main__': unittest.main()
