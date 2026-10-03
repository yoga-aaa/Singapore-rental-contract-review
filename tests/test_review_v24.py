"""Actor-schema constraints and imported trace tools; no performance claims."""
import importlib
import unittest
from unittest.mock import patch
from src.review_v24 import request
from src.review_v24 import review_clause
from tests import test_review_v23 as baseline
from src.evidence_ids_v24 import terms_schema

class V24StructureTests(unittest.TestCase):
    setUp=baseline.V23Tests.setUp
    def test_actor_schema_excludes_full_sentences(self):
        payload=request('HDB',self.clause,self.p,'compare')
        fields=payload['response_format']['json_schema']['schema']['properties']['comparisons']['items']['properties']
        ids=fields['contract_terms']['properties']['actor']['items']['enum']
        self.assertTrue(ids); self.assertTrue(all('.A' in i for i in ids))
        self.assertNotIn('C001',ids)
        self.assertIn('C001',fields['contract_terms']['properties']['action']['items']['enum'])
    def test_unknown_reference_actor_can_be_empty(self):
        schema=terms_schema(['R001','R001.S1'])
        self.assertEqual(schema['properties']['actor']['items']['enum'],['UNAVAILABLE'])
        self.assertNotIn('minItems',schema['properties']['actor'])
    def test_diagnostic_import_closure(self):
        importlib.import_module('src.condition_diagnostics_v24')
        importlib.import_module('scripts.diagnose_v24_run')
    def test_v24_native_three_call_release(self):
        class Retriever:
            def packet(inner,*args): return self.p
        fact={k:v for k,v in self.row.items() if k not in {'relation','contrast_kind','scenario','decision'}}
        raw={'comparisons':[self.row],'unassessed_task_ids':[]}
        with patch('src.review_v24._request_openrouter',side_effect=[
            ({'facts':[fact],'unassessed_task_ids':[]},{}),(raw,{}),(raw,{})]) as transport:
            result=review_clause('HDB',self.clause,Retriever(),api_key='simulated')
        self.assertEqual(result.label,'review_required')
        self.assertEqual(transport.call_count,3)
    def test_v24_offline_never_calls_key(self):
        with patch('src.review_v24.local_api_key',side_effect=AssertionError('key')):
            self.assertEqual(review_clause('HDB',self.clause,None,allow_api=False).label,'insufficient_evidence')
