"""v25 scalar roles and complete sources, simulated traces only."""
import copy
import importlib
import json
import unittest
from unittest.mock import patch
from tests import test_review_v23 as baseline
from src.evidence_ids_v25 import catalogue,resolve_row,terms_schema
from src.review_v25 import request,review_clause
from src.condition_checks_v25 import assess

class V25Tests(unittest.TestCase):
    def setUp(self):
        baseline.V23Tests.setUp(self)
        self.row['contract_terms']['actor']=self.row['contract_terms']['actor'][0]
        self.row['reference_terms']=[{'reference_id':f['reference_id']} for f in self.row['reference_terms']]
    def raw(self,row=None):
        return {'comparisons':[row or self.row],'unassessed_task_ids':[]}
    def test_actor_is_scalar_party_enum(self):
        s=terms_schema(['C001','C001.A1','C001.A2'])
        self.assertEqual(s['properties']['actor'],{'type':'string','enum':['','C001.A1','C001.A2']})
    def test_actor_occurrence_list_is_rejected(self):
        r=copy.deepcopy(self.row); r['contract_terms']['actor']=[r['contract_terms']['actor']]*2
        self.assertFalse(assess(self.raw(r),[self.task],self.clause,self.p,'HDB')['accepted'])
    def test_unknown_actor_is_not_filled(self):
        r=copy.deepcopy(self.row); r['contract_terms']['actor']=''
        self.assertFalse(assess(self.raw(r),[self.task],self.clause,self.p,'HDB')['accepted'])
    def test_source_selects_complete_original_no_inferred_prerequisites(self):
        r=resolve_row(self.row,self.task,self.clause,self.p,catalogue(self.clause,self.p,[self.task]))
        self.assertEqual(r['reference_terms'][0]['terms']['action'],self.p['references'][0]['text'])
        self.assertEqual(r['reference_terms'][0]['terms']['prerequisite'],'')
    def test_no_abbreviated_source_fact_channel(self):
        payload=request('HDB',self.clause,self.p,'compare')
        p=payload['response_format']['json_schema']['schema']['properties']['comparisons']['items']['properties']
        self.assertEqual(set(p['reference_terms']['items']['properties']),{'reference_id'})
    def test_foreign_source_rejected(self):
        r=copy.deepcopy(self.row); r['reference_terms']=[{'reference_id':'R999'}]
        self.assertFalse(assess(self.raw(r),[self.task],self.clause,self.p,'HDB')['accepted'])
    def test_unknown_contract_id_rejected(self):
        r=copy.deepcopy(self.row); r['contract_terms']['action']=['fabricated']
        self.assertFalse(assess(self.raw(r),[self.task],self.clause,self.p,'HDB')['accepted'])
    def test_positive_contrast_retains_all_gates(self):
        self.assertEqual(len(assess(self.raw(),[self.task],self.clause,self.p,'HDB')['accepted']),1)
    def test_native_three_call_release(self):
        class Retriever:
            def packet(inner,*args): return self.p
        fact={k:v for k,v in self.row.items() if k not in {'relation','contrast_kind','scenario','decision'}}
        with patch('src.review_v25._request_openrouter',side_effect=[
            ({'facts':[fact],'unassessed_task_ids':[]},{}),(self.raw(),{}),(self.raw(),{})]) as transport:
            result=review_clause('HDB',self.clause,Retriever(),api_key='simulated')
        self.assertEqual(result.label,'review_required')
        self.assertEqual(transport.call_count,3)
    def test_audit_uncertainty_blocks_release(self):
        class Retriever:
            def packet(inner,*args): return self.p
        uncertain=copy.deepcopy(self.row); uncertain.update(relation='uncertain',decision='uncertain',contrast_kind='none',scenario='none')
        with patch('src.review_v25._request_openrouter',side_effect=[
            ({'facts':[]},{}),(self.raw(),{}),(self.raw(uncertain),{})]):
            self.assertEqual(review_clause('HDB',self.clause,Retriever(),api_key='simulated').label,'insufficient_evidence')
    def test_audit_blind_to_prior_conclusion(self):
        payload=request('HDB',self.clause,self.p,'audit',{'earlier':'VERDICT'},[self.task['task_id']])
        self.assertNotIn('VERDICT',json.dumps(payload))
    def test_offline_does_not_access_key(self):
        with patch('src.review_v25.local_api_key',side_effect=AssertionError('key')):
            self.assertEqual(review_clause('HDB',self.clause,None,allow_api=False).label,'insufficient_evidence')
    def test_diagnostic_closure_imports(self):
        importlib.import_module('src.condition_diagnostics_v25')
        importlib.import_module('scripts.diagnose_v25_run')
