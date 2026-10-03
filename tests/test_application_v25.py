"""Final-engine intake, metering and UI adapter checks; simulated calls only."""
import json
import unittest
from unittest.mock import patch
from src.application import Clause, run_document
from tests import test_review_v25 as fixture


class FinalApplicationTests(unittest.TestCase):
    def setUp(self):
        fixture.V25Tests.setUp(self)

    def run_review(self, clauses=None, **options):
        settings={'synthetic_confirmed':True,'extraction_confirmed':True,'review_version':'v25'}
        settings.update(options)
        return run_document(clauses or [Clause('CL_01',(1,),self.clause)],'HDB',**settings)

    def simulated(self, responses):
        self.sent=[]
        replies=iter(responses)
        def request(payload, key):
            self.assertEqual(key,'simulated-not-a-credential')
            self.assertEqual(payload['provider']['only'],['openai'])
            self.assertFalse(payload['provider']['allow_fallbacks'])
            self.sent.append(payload)
            return {'choices':[{'message':{'content':json.dumps(next(replies))}}],
                    'usage':{'prompt_tokens':100,'completion_tokens':20,'total_tokens':120,'cost':'0.00001'}}
        return request

    def live_report(self, request, **options):
        class Retriever:
            def packet(inner, *args): return self.p
        with patch.dict('os.environ',{'RENTAL_ENABLE_LIVE':'1'}), \
             patch('src.application.local_api_key',return_value='simulated-not-a-credential'), \
             patch('src.evidence_packet_v22.ConditionRetriever.from_repo',return_value=Retriever()):
            return self.run_review(live=True,spending_confirmed=True,budget='1',request=request,**options)

    def test_offline_preview_never_accesses_key_or_reviewer(self):
        with patch('src.application.local_api_key',side_effect=AssertionError('key')), \
             patch('src.review_v25.review_clause',side_effect=AssertionError('pipeline')), \
             patch('src.review_v25._request_openrouter',side_effect=AssertionError('network')):
            report=self.run_review()
        self.assertEqual(report['version'],'v25')
        self.assertEqual(report['clauses'][0]['status'],'model_needed')
        self.assertIsNone(report['clauses'][0]['result'])
        self.assertTrue(report['clauses'][0]['retrieved_sources'])
        self.assertEqual(report['accounting']['cost_usd'],'0')
        self.assertEqual(report['accounting']['api_calls'],0)

    def test_live_confirmation_guard_before_key(self):
        for enabled, spending in [('0',True),('1',False)]:
            with patch.dict('os.environ',{'RENTAL_ENABLE_LIVE':enabled}), \
                 patch('src.application.local_api_key',side_effect=AssertionError('key')):
                with self.assertRaisesRegex(ValueError,'disabled'):
                    self.run_review(live=True,spending_confirmed=spending)

    def test_personal_data_guard_before_credentials(self):
        with patch('src.application.local_api_key',side_effect=AssertionError('key')):
            with self.assertRaisesRegex(ValueError,'personal'):
                self.run_review([Clause('CL_01',(),'The Tenant NRIC: S1234567A pays rent.')],
                                live=True,spending_confirmed=True)

    def test_metered_three_stage_v25_not_legacy_pipeline(self):
        raw={'comparisons':[self.row],'unassessed_task_ids':[]}
        fact={k:v for k,v in self.row.items() if k not in {'relation','contrast_kind','scenario','decision'}}
        request=self.simulated([{'facts':[fact],'unassessed_task_ids':[]},raw,raw])
        with patch('src.live_review._request_openrouter',side_effect=AssertionError('legacy')), \
             patch('src.review_v18._request_openrouter',side_effect=AssertionError('v18')):
            report=self.live_report(request)
        self.assertEqual(report['clauses'][0]['result']['label'],'review_required')
        self.assertEqual(report['clauses'][0]['result']['evidence'][0]['quote'],self.p['references'][0]['text'])
        self.assertEqual(report['clauses'][0]['result']['comparisons'][0]['contract_context'],self.clause)
        self.assertEqual(report['accounting']['api_calls'],3)
        self.assertEqual(report['accounting']['cost_usd'],'0.00003')
        schemas=[p['response_format']['json_schema']['name'] for p in self.sent]
        self.assertEqual(schemas,['conditions_extract_v25','conditions_compare_v25','conditions_audit_v25'])
        self.assertNotIn('CL_01',json.dumps(self.sent))
        self.assertEqual(report['not_processed_count'],0)

    def test_unknown_charge_stops_without_retry_or_exposing_error(self):
        calls=[]
        def broken(payload,key):
            calls.append(payload)
            raise RuntimeError('simulated sensitive provider body')
        report=self.live_report(broken,clauses=[Clause('C1',(),self.clause),Clause('C2',(),self.clause)])
        self.assertEqual(len(calls),1)
        self.assertTrue(report['stopped'])
        self.assertTrue(report['accounting']['unaccounted_attempt'])
        self.assertEqual(report['not_processed_count'],1)
        self.assertEqual(report['clauses'][0]['status'],'stopped')
        self.assertNotIn('sensitive',json.dumps(report))

    def test_missing_usage_stops_and_retains_unknown_charge_flag(self):
        report=self.live_report(lambda payload,key:{'choices':[]})
        self.assertTrue(report['stopped'])
        self.assertTrue(report['accounting']['unaccounted_attempt'])
        self.assertEqual(report['accounting']['api_calls'],1)

    def test_budget_guard_stops_before_transport(self):
        class Retriever:
            def packet(inner,*args): return self.p
        with patch.dict('os.environ',{'RENTAL_ENABLE_LIVE':'1'}), \
             patch('src.application.local_api_key',return_value='simulated-not-a-credential'), \
             patch('src.evidence_packet_v22.ConditionRetriever.from_repo',return_value=Retriever()):
            report=self.run_review(live=True,spending_confirmed=True,budget='.000001',
                                   request=lambda *args: self.fail('Must stop before transport'))
        self.assertTrue(report['stopped'])
        self.assertEqual(report['accounting']['api_calls'],0)
        self.assertEqual(report['accounting']['cost_usd'],'0')

    def test_source_failure_before_key_does_not_fall_back_to_legacy(self):
        with patch.dict('os.environ',{'RENTAL_ENABLE_LIVE':'1'}), \
             patch('src.application.local_api_key',side_effect=AssertionError('key')), \
             patch('src.evidence_packet_v22.ConditionRetriever.from_repo',side_effect=ValueError('source missing')):
            with self.assertRaisesRegex(ValueError,'source missing'):
                self.run_review(live=True,spending_confirmed=True)
