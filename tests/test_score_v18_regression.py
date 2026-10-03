import json
import tempfile
import unittest
from pathlib import Path

from scripts.score_v18_regression import score
from src.frozen_external import byte_hash


class V18ScoringTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='v18-score-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bundle, self.run = self.root/'freeze', self.root/'run'
        self.cases = [{'case_id':f'NEW_{i:02d}','housing_type':'HDB','clause_text':'Synthetic rent term.'}
                      for i in range(1,21)]
        self.labels = [{'case_id':c['case_id'],'ground_truth_label':
                        'review_required' if i<14 else 'no_material_difference_found' if i<16 else 'insufficient_evidence'}
                       for i,c in enumerate(self.cases)]
        self.write_json(self.bundle/'inputs.json',self.cases)
        self.write_json(self.bundle/'labels.json',{'labels':self.labels})
        self.write(self.bundle/'index.jsonl',json.dumps({'source_id':'SYNTHETIC','section':'S1','text':'Synthetic reference.',
                  'housing_type':'HDB','source_kind':'tenancy_agreement_template'})+'\n')
        self.write(self.bundle/'official.jsonl','')
        manifest = {'freeze_version':'v18','evaluation_type':'synthetic tests only',
                    'input_path':'inputs.json','label_path':'labels.json',
                    'section_index_path':'index.jsonl','official_index_path':'official.jsonl',
                    'original_labels_sha256':byte_hash(self.bundle/'labels.json'),
                    'artifacts':[{'path':p.name,'sha256':byte_hash(p)} for p in sorted(self.bundle.iterdir())]}
        self.write_json(self.bundle/'manifest.json',manifest)
        self.write_json(self.run/'run_started.json',{'bundle_manifest_sha256':byte_hash(self.bundle/'manifest.json')})
        self.rows = [{'case_id':c['case_id'],'result':{'label':'review_required' if i<12 else 'insufficient_evidence',
                     'evidence':[{'source_id':'SYNTHETIC','source_section':'S1','quote':'Synthetic reference.',
                                  'source_kind':'tenancy_agreement_template'}] if i<12 else []},
                     'accounting':{'api_calls':0,'total_tokens':0,'cost_usd':'0'}} for i,c in enumerate(self.cases)]
        self.write(self.run/'calls.jsonl','')
        self.save_predictions()

    @staticmethod
    def write(path,text):
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(text,encoding='utf-8')

    def write_json(self,path,data):
        self.write(path,json.dumps(data))

    def save_predictions(self):
        self.write(self.run/'predictions.jsonl',''.join(json.dumps(r)+'\n' for r in self.rows))
        self.finish = {'status':'complete','accounting':{'api_calls':0,'total_tokens':0,'cost_usd':'0',
                        'unaccounted_attempt':False},'predictions_sha256':byte_hash(self.run/'predictions.jsonl'),
                       'calls_sha256':byte_hash(self.run/'calls.jsonl')}
        self.write_json(self.run/'run_finished.json',self.finish)

    def audit(self, verdict='supported'):
        path = self.root/'audit.json'
        self.write_json(path,{'predictions_sha256':byte_hash(self.run/'predictions.jsonl'),
                             'index_sha256':byte_hash(self.bundle/'index.jsonl'),
                             'official_index_sha256':byte_hash(self.bundle/'official.jsonl'),
                             'reviewer':'synthetic independent test audit','owner_confirmation':'pending',
                             'results':[{'case_id':r['case_id'],'verdict':verdict,'reason':'Synthetic audit reason.'}
                                        for r in self.rows if r['result']['label']!='insufficient_evidence']})
        return path

    def test_twelve_of_fourteen_reaches_85_without_implying_citation_support(self):
        result = score(self.bundle,self.run)
        self.assertAlmostEqual(result['rag']['recall'],12/14)
        self.assertTrue(result['recall_target_met'])
        self.assertTrue(result['safety_gate_met'])
        self.assertFalse(result['target_met'])
        self.assertEqual(result['rag']['precision'],1)
        self.assertEqual(result['rag']['unsafe_non_abstention'],0)
        self.assertEqual(result['false_negative_case_ids'],['NEW_13','NEW_14'])
        self.assertEqual(result['locator_valid_rate'],1)
        self.assertIsNone(result['citation_supported_rate'])

    def test_unsafe_and_precision_penalty_cannot_be_hidden(self):
        self.rows[19]['result']=self.rows[0]['result']
        self.save_predictions()
        result=score(self.bundle,self.run)
        self.assertEqual(result['rag']['precision'],12/13)
        self.assertEqual(result['rag']['unsafe_non_abstention'],1/4)
        self.assertEqual(result['unsafe_case_ids'],['NEW_20'])
        self.assertFalse(result['safety_gate_met'])
        self.assertFalse(result['target_met'])

    def test_partial_or_unknown_charge_has_no_headline_score(self):
        self.finish['status']='partial_stopped'
        self.write_json(self.run/'run_finished.json',self.finish)
        with self.assertRaisesRegex(ValueError,'Partial'):
            score(self.bundle,self.run)
        self.finish['status']='complete'
        self.finish['accounting']['unaccounted_attempt']=True
        self.write_json(self.run/'run_finished.json',self.finish)
        with self.assertRaisesRegex(ValueError,'unaccounted'):
            score(self.bundle,self.run)

    def test_changed_result_or_label_rejected(self):
        self.write(self.run/'predictions.jsonl','changed')
        with self.assertRaisesRegex(ValueError,'Run artifact'):
            score(self.bundle,self.run)
        self.save_predictions()
        self.write(self.bundle/'labels.json','changed')
        with self.assertRaisesRegex(ValueError,'Frozen artifact'):
            score(self.bundle,self.run)

    def test_uncertain_audit_counts_as_not_supported(self):
        result=score(self.bundle,self.run,self.audit('uncertain'))
        self.assertEqual(result['citation_supported_rate'],0)
        self.assertEqual(result['owner_audit_confirmation'],'pending')

    def test_audit_bound_to_sources_and_every_non_abstention(self):
        path=self.audit()
        result=score(self.bundle,self.run,path)
        self.assertEqual(result['citation_supported_rate'],1)
        audit=json.loads(path.read_text())
        audit['results'].pop()
        self.write_json(path,audit)
        with self.assertRaisesRegex(ValueError,'every non-abstention'):
            score(self.bundle,self.run,path)

    def test_high_recall_and_citation_audit_cannot_override_a_false_positive(self):
        self.rows[15]['result']=self.rows[0]['result']
        self.save_predictions()
        result=score(self.bundle,self.run,self.audit())
        self.assertTrue(result['recall_target_met'])
        self.assertEqual(result['citation_supported_rate'],1)
        self.assertEqual(result['rag']['fp'],1)
        self.assertFalse(result['target_met'])

    def test_a_single_uncertain_citation_fails_small_batch_95_percent_gate(self):
        path=self.audit()
        audit=json.loads(path.read_text())
        audit['results'][0]['verdict']='uncertain'
        self.write_json(path,audit)
        result=score(self.bundle,self.run,path)
        self.assertAlmostEqual(result['citation_supported_rate'],11/12)
        self.assertTrue(result['recall_target_met'])
        self.assertTrue(result['safety_gate_met'])
        self.assertFalse(result['target_met'])

    def test_all_metric_thresholds_must_be_met_together(self):
        result=score(self.bundle,self.run,self.audit())
        self.assertTrue(result['target_met'])
        # A metric threshold result is still an assistant audit pending owner
        # confirmation, not evidence of independent expert/generalization gold.
        self.assertEqual(result['owner_audit_confirmation'],'pending')


if __name__=='__main__':
    unittest.main()
