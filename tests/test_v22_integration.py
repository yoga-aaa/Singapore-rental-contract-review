"""Synthetic trace/registry engineering tests, never measured risk metrics."""
import copy
import hashlib
import io
import json
import unittest
from pathlib import Path
from unittest.mock import patch
from src.condition_diagnostics_v22 import input_record,reproduce_trace
from src.evidence_packet_v22 import ConditionRetriever
from src.frozen_external import MeteredTransport
from src.mechanism_tasks_v22 import plan_for
from src.review_v22 import request,review_clause
from tests.test_review_v20 import reference,packet
from tests.test_review_v22 import make_row,response

ROOT=Path(__file__).resolve().parents[1]


class V22TraceTests(unittest.TestCase):
    def setUp(self):
        self.case={'case_id':'SYNTHETIC_TRACE','housing_type':'HDB',
                   'clause_text':'The Landlord refunds the deposit within seventeen days after handover.'}
        self.ref=reference('2.2','The deposit is refunded when the Term expires or is terminated.')
        self.p=packet(self.ref)
        self.tasks=plan_for(self.case['clause_text'],self.p,'HDB')['tasks']
        self.row=make_row(self.tasks[0],self.case['clause_text'],[self.ref])
        self.config=json.loads((ROOT/'data/live_budget_policy_v22.json').read_text())

    def record(self,replies):
        events=[]; attempts={}; meter=MeteredTransport(self.config,io.StringIO())
        class Retriever:
            def packet(inner,*args): return self.p
        def simulated(payload,unused_key):
            number=len(events)+1; raw=replies[number-1]
            bounded,_,_=meter.reservation(payload)
            attempts[number]={'case_id':self.case['case_id'],'request_sha256':hashlib.sha256(
                json.dumps(bounded,ensure_ascii=False,sort_keys=True).encode('utf-8')).hexdigest()}
            usage={'prompt_tokens':1,'completion_tokens':1,'total_tokens':2}
            events.append({'case_id':self.case['case_id'],'call_number':number,
                'body':{'choices':[{'message':{'content':json.dumps(raw)}}],'usage':usage}})
            return raw,usage
        with patch('src.review_v22._request_openrouter',side_effect=simulated):
            review_clause('HDB',self.case['clause_text'],Retriever(),api_key='synthetic-recording-only')
        return events,attempts

    def test_reproduces_three_stage_trace_with_exact_request_hashes(self):
        raw=response(self.row); events,attempts=self.record([{'facts':[]},raw,raw])
        diagnostic=reproduce_trace(self.case,self.p,events,attempts,self.config)
        self.assertEqual(diagnostic['matched_requests'],3)
        self.assertEqual([r['stage'] for r in diagnostic['stages']],['extract','compare','audit'])
        self.assertIsNone(diagnostic['quality_metrics'])

    def test_reproduces_four_stage_correction_trace(self):
        raw=response(self.row)
        wrong=response({**self.row,'relation':'equivalent','contrast_kind':'none','scenario':'none'})
        events,attempts=self.record([{'facts':[]},wrong,raw,raw])
        diagnostic=reproduce_trace(self.case,self.p,events,attempts,self.config)
        self.assertEqual(diagnostic['matched_requests'],4)
        self.assertIn('misclassified_condition',diagnostic['stages'][1]['issue_codes'])

    def test_reproduces_two_stage_malformed_stop(self):
        events,attempts=self.record([{'facts':[]},{'unexpected':'malformed'}])
        diagnostic=reproduce_trace(self.case,self.p,events,attempts,self.config)
        self.assertEqual(diagnostic['matched_requests'],2)
        self.assertEqual(diagnostic['replayed_recorded_decision'],'insufficient_evidence')

    def test_changed_or_missing_requests_cannot_fall_back_to_api(self):
        raw=response(self.row); events,attempts=self.record([{'facts':[]},raw,raw])
        attempts[1]['request_sha256']='wrong'
        with self.assertRaisesRegex(ValueError,'actual v22 model input'):
            reproduce_trace(self.case,self.p,events,attempts,self.config)
        events,attempts=self.record([{'facts':[]},raw,raw])
        with self.assertRaisesRegex(ValueError,'Missing recorded stage'):
            reproduce_trace(self.case,self.p,events[:-1],attempts,self.config)

    def test_focused_rubric_drops_only_irrelevant_examples(self):
        req=request('HDB',self.case['clause_text'],self.p,'audit',task_ids=[self.row['task_id']])
        system=req['messages'][0]['content']
        self.assertIn('* refund_window:',system)
        self.assertNotIn('* late_rate_difference:',system)
        self.assertIn('untrusted DATA',system)
        self.assertIn('CEA wording is a comparison template',system)
        enums=req['response_format']['json_schema']['schema']['properties']['comparisons']['items']['properties']
        self.assertEqual(enums['contrast_kind']['enum'],['none','refund_window'])

    def test_input_diagnostics_do_not_claim_support_or_predictions(self):
        diagnostic=input_record(self.case['clause_text'],self.p,'HDB')
        self.assertTrue(diagnostic['coverage_is_not_semantic_support'])
        self.assertNotIn('recall',diagnostic)
        self.assertNotIn('predicted_label',diagnostic)


class V22RegistryTests(unittest.TestCase):
    def fixture(self,cid,text,housing='HDB'):
        return {**reference(cid,text,housing=housing),'page_number':1,'title':'Synthetic fixture'}

    def test_complete_shorter_mechanism_reference_reserved_first(self):
        short=self.fixture('2.2','Deposit refunded when Term expires.')
        long={**self.fixture('2.2','Deposit refunded when Term expires; '+('Synthetic context. '*50)),
              'section':'Synthetic longer'}
        private=self.fixture('2.2','Private housing deposit text.','Private Residential')
        r=ConditionRetriever([long,short,private],[])
        p=r.packet('The Lessor pays back the deposit within nine days after handover.','HDB')
        self.assertEqual(p['references'][0]['text'],short['text'])
        self.assertTrue(all(x['housing_type']=='HDB' for x in p['references']))
        self.assertIn(long['text'],[x['text'] for x in p['references']])
        self.assertFalse(p['truncated'])

    def test_oversized_required_source_is_explicitly_omitted_not_clipped(self):
        r=ConditionRetriever([self.fixture('2.2','Deposit refund when Term expires. '+'x'*7600)],[])
        p=r.packet('Landlord refunds deposit within nine days after handover.','HDB')
        self.assertTrue(p['truncated'])
        self.assertTrue(p['omitted_required_locations'])
        self.assertFalse(p['references'])

    def test_unrelated_authority_cannot_become_guest_rule(self):
        official={**self.fixture('','Guests appear in an unrelated stamp duty example.'),
                  'source_kind':'stamp_duty_guidance','housing_type':'Both'}
        r=ConditionRetriever([self.fixture('1.1','Named occupiers live in the flat.')],[official])
        p=r.packet('Tenant provides ID copies for ordinary guests.','HDB')
        t=next(t for t in plan_for('Tenant provides ID copies for ordinary guests.',p,'HDB')['tasks']
               if t['mechanism']=='guest_documentation')
        self.assertFalse(t['required_reference_groups'][0])
        self.assertNotIn(official['text'],[x['text'] for x in p['references']])

    def test_unknown_housing_never_retrieves(self):
        self.assertEqual(ConditionRetriever([],[]).packet('Tenant pays rent.','Unknown')['references'],[])

    @unittest.skipUnless((ROOT/'data/official_sources_v18/index_v18.jsonl').exists(),
                         'Bootstrap the pinned official sources for integration checks')
    def test_real_registry_keeps_original_text_hashes_and_housing_scope(self):
        r=ConditionRetriever.from_repo(ROOT)
        originals={(x['source_id'],x['section']):x for x in r.templates+r.official}
        for housing in ['HDB','Private Residential']:
            for clause in ['Landlord refunds deposit within nine days after handover.',
                           'Tenant pays stamp duty.','Tenant shares the Premises with consent.',
                           'Landlord may terminate for own occupation before expiry of the Term.']:
                for selected in r.packet(clause,housing)['references']:
                    source=originals[(selected['source_id'],selected['section'])]
                    self.assertEqual(selected['text'],source['text'])
                    self.assertEqual(selected.get('source_sha256'),source.get('source_sha256'))
                    self.assertIn(selected['housing_type'],{housing,'Both'})


if __name__=='__main__': unittest.main()
