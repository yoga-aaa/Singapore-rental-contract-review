import copy
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from scripts import run_v18_regression
from src.frozen_external import byte_hash
from src.frozen_v18 import runtime_files, validate_cases, verify_freeze


class V18FreezeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='v18-regression-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root/'repo'
        self.bundle = self.root/'private/freeze_v18'
        self.write(self.repo/'src/synthetic.py', '# synthetic runtime\n')
        self.write(self.repo/'scripts/run_v18_regression.py', '# synthetic runner\n')
        self.write(self.repo/'requirements.txt', '# synthetic dependencies\n')
        self.cases = [{'case_id':f'NEW_{i:02d}', 'housing_type':'HDB' if i <= 10 else 'Private Residential',
                       'clause_text':'The tenant pays the agreed rent.'} for i in range(1,21)]
        self.config = {'review_version':'v18','retrieval_limit':12,
                       'models':{'draft':'openai/gpt-4.1','verifier':'openai/gpt-4o'},
                       'max_model_calls':40,'max_total_tokens':200000,'max_cost_usd':'1.00',
                       'prices':{model:{'input_usd_per_million':price[0],
                                        'output_usd_per_million':price[1],'max_completion_tokens':2400}
                                 for model,price in {'openai/gpt-4.1':('2.00','8.00'),
                                                    'openai/gpt-4o':('2.50','10.00')}.items()}}
        self.write_json(self.bundle/'inputs/cases.json', self.cases)
        self.write_json(self.bundle/'configuration.json', self.config)
        self.write(self.bundle/'scoring/labels.confirmed.json', 'GOLD_NOT_VALID_JSON_OR_MODEL_INPUT')
        self.write(self.bundle/'snapshot/data/derived/source_sections_v15.jsonl', '')
        self.write(self.bundle/'snapshot/data/official_sources_v18/index_v18.jsonl', '')
        runtime = []
        for source in runtime_files(self.repo):
            relative = source.relative_to(self.repo).as_posix()
            self.write(self.bundle/('snapshot/'+relative), source.read_text())
            runtime.append({'repo_path':relative,'snapshot_path':'snapshot/'+relative,'sha256':byte_hash(source)})
        self.manifest = {'freeze_version':'v18','status':'frozen_regression_authorization_pending',
                         'hash_method':'sha256_exact_bytes','case_count':20,
                         'input_path':'inputs/cases.json','label_path':'scoring/labels.confirmed.json',
                         'configuration_path':'configuration.json','snapshot_repo_path':'snapshot',
                         'section_index_path':'snapshot/data/derived/source_sections_v15.jsonl',
                         'official_index_path':'snapshot/data/official_sources_v18/index_v18.jsonl',
                         'original_labels_sha256':byte_hash(self.bundle/'scoring/labels.confirmed.json'),
                         'runtime_files':runtime,'evaluation_type':'synthetic fixture only'}
        self.refresh_manifest()

    @staticmethod
    def write(path, text):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')

    def write_json(self, path, value):
        self.write(path, json.dumps(value))

    def refresh_manifest(self):
        self.manifest['artifacts'] = [{'path':p.relative_to(self.bundle).as_posix(),'sha256':byte_hash(p)}
                                      for p in sorted(self.bundle.rglob('*'))
                                      if p.is_file() and p.name != 'manifest.json']
        self.write_json(self.bundle/'manifest.json', self.manifest)

    def test_preflight_never_reads_key_labels_or_predicts(self):
        output = io.StringIO()
        with patch.object(run_v18_regression,'REPO',self.repo), \
             patch.object(sys,'argv',['runner','--bundle',str(self.bundle)]), \
             patch.object(run_v18_regression,'local_api_key',side_effect=AssertionError('key read')), \
             patch.object(run_v18_regression,'review_clause',side_effect=AssertionError('prediction')), \
             redirect_stdout(output):
            run_v18_regression.main()
        summary = json.loads(output.getvalue())
        self.assertEqual(summary['api_calls'],0)
        self.assertEqual(summary['predictions'],0)
        self.assertFalse((self.bundle.parent/'run_v18').exists())

    def test_live_without_new_approval_stops_before_key(self):
        with patch.object(run_v18_regression,'REPO',self.repo), \
             patch.object(sys,'argv',['runner','--bundle',str(self.bundle),'--live']), \
             patch.object(run_v18_regression,'local_api_key',side_effect=AssertionError('key read')):
            with self.assertRaisesRegex(ValueError,'new human authorization'):
                run_v18_regression.main()

    def test_changed_labels_inputs_sources_or_code_stop(self):
        for relative in ['scoring/labels.confirmed.json','inputs/cases.json',
                         'snapshot/data/official_sources_v18/index_v18.jsonl','snapshot/src/synthetic.py']:
            path = self.bundle/relative
            original = path.read_bytes()
            self.write(path,'changed')
            with self.subTest(path=relative), self.assertRaisesRegex(ValueError,'Frozen artifact changed'):
                verify_freeze(self.bundle,self.repo)
            path.write_bytes(original)
        self.write(self.repo/'src/synthetic.py','# edited runtime')
        with self.assertRaisesRegex(ValueError,'Runtime changed'):
            verify_freeze(self.bundle,self.repo)

    def test_missing_or_duplicate_artifact_rejected(self):
        original = copy.deepcopy(self.manifest)
        self.manifest['artifacts'] = [r for r in self.manifest['artifacts'] if r['path'] != 'inputs/cases.json']
        self.write_json(self.bundle/'manifest.json',self.manifest)
        with self.assertRaisesRegex(ValueError,'Incomplete'):
            verify_freeze(self.bundle,self.repo)
        self.manifest = original
        self.manifest['artifacts'].append(self.manifest['artifacts'][0])
        self.write_json(self.bundle/'manifest.json',self.manifest)
        with self.assertRaisesRegex(ValueError,'duplicated'):
            verify_freeze(self.bundle,self.repo)

    def test_no_annotation_pii_oversized_or_unknown_housing_inputs(self):
        for update in [{'ground_truth_label':'review_required'}, {'clause_text':'Tenant name: Somebody'},
                       {'clause_text':'x'*6001}, {'housing_type':'Unknown'}]:
            cases = copy.deepcopy(self.cases)
            cases[0].update(update)
            with self.subTest(update=update), self.assertRaises(ValueError):
                validate_cases(cases)

    def test_wrong_price_model_and_budget_are_rejected(self):
        for update in [{'max_cost_usd':'1.01'},{'max_model_calls':41},
                       {'max_total_tokens':200001},{'retrieval_limit':4},
                       {'models':{'draft':'other','verifier':'openai/gpt-4o'}}]:
            self.write_json(self.bundle/'configuration.json',{**self.config,**update})
            self.refresh_manifest()
            with self.subTest(update=update), self.assertRaises(ValueError):
                verify_freeze(self.bundle,self.repo)
        config = copy.deepcopy(self.config)
        config['prices']['openai/gpt-4.1']['max_completion_tokens'] = 3000
        self.write_json(self.bundle/'configuration.json',config)
        self.refresh_manifest()
        with self.assertRaisesRegex(ValueError,'ceiling'):
            verify_freeze(self.bundle,self.repo)

    def test_v19_preflight_uses_its_own_version_and_never_reads_credentials(self):
        self.write(self.repo/'scripts/run_v19_regression.py','# synthetic v19 wrapper\n')
        relative='scripts/run_v19_regression.py'
        self.write(self.bundle/('snapshot/'+relative),'# synthetic v19 wrapper\n')
        self.manifest['runtime_files'].append({'repo_path':relative,'snapshot_path':'snapshot/'+relative,
                                               'sha256':byte_hash(self.repo/relative)})
        self.manifest['freeze_version']='v19'
        self.config.update(review_version='v19',retrieval_limit=15,max_total_tokens=300000)
        self.write_json(self.bundle/'configuration.json',self.config)
        self.refresh_manifest()
        output=io.StringIO()
        with patch.object(run_v18_regression,'REPO',self.repo), \
             patch.object(sys,'argv',['runner','--bundle',str(self.bundle)]), \
             patch.object(run_v18_regression,'local_api_key',side_effect=AssertionError('key read')), \
             redirect_stdout(output):
            run_v18_regression.main('v19')
        self.assertEqual(json.loads(output.getvalue())['api_calls'],0)
        with patch.object(run_v18_regression,'REPO',self.repo), \
             patch.object(sys,'argv',['runner','--bundle',str(self.bundle),'--live']), \
             patch.object(run_v18_regression,'local_api_key',side_effect=AssertionError('key read')):
            with self.assertRaisesRegex(ValueError,'new human authorization'):
                run_v18_regression.main('v19')
        self.assertFalse((self.bundle.parent/'run_v19').exists())

    def test_v20_preflight_no_budget_key_or_prediction_and_live_budget_before_key(self):
        relative='scripts/run_v20_regression.py'
        self.write(self.repo/relative,'# synthetic v20 wrapper\n')
        self.write(self.bundle/('snapshot/'+relative),'# synthetic v20 wrapper\n')
        self.manifest['runtime_files'].append({'repo_path':relative,'snapshot_path':'snapshot/'+relative,
                                               'sha256':byte_hash(self.repo/relative)})
        scorer='scripts/score_v18_regression.py'
        self.write(self.repo/scorer,'# synthetic fixed scoring rules\n')
        self.write(self.bundle/('snapshot/'+scorer),'# synthetic fixed scoring rules\n')
        self.manifest['runtime_files'].append({'repo_path':scorer,'snapshot_path':'snapshot/'+scorer,
                                               'sha256':byte_hash(self.repo/scorer)})
        self.manifest['freeze_version']='v20'
        self.config.update(review_version='v20',retrieval_limit=15,max_total_tokens=350000)
        self.write_json(self.bundle/'configuration.json',self.config); self.refresh_manifest()
        output=io.StringIO()
        with (patch.object(run_v18_regression,'REPO',self.repo),
              patch.object(sys,'argv',['runner','--bundle',str(self.bundle)]),
              patch.object(run_v18_regression,'local_api_key',side_effect=AssertionError('key')),
              patch.object(run_v18_regression,'verify_campaign',side_effect=AssertionError('campaign')),
              redirect_stdout(output)):
            run_v18_regression.main('v20')
        self.assertEqual(json.loads(output.getvalue())['api_calls'],0)
        authorization=self.bundle.parent/'approval.json'; self.write_json(authorization,{})
        with (patch.object(run_v18_regression,'REPO',self.repo),
              patch.object(sys,'argv',['runner','--bundle',str(self.bundle),'--live','--authorization',str(authorization)]),
              patch.object(run_v18_regression,'verify_authorization',return_value={}),
              patch.object(run_v18_regression,'local_api_key',side_effect=AssertionError('key'))):
            with self.assertRaisesRegex(ValueError,'cumulative'): run_v18_regression.main('v20')
        self.assertFalse((self.bundle.parent/'run_v20').exists())

    def test_v21_preflight_free_and_live_campaign_check_before_key(self):
        for relative in ['scripts/run_v21_regression.py','scripts/score_v18_regression.py','scripts/diagnose_v21_run.py']:
            self.write(self.repo/relative,'# synthetic v21 frozen entry\n')
            self.write(self.bundle/('snapshot/'+relative),'# synthetic v21 frozen entry\n')
            self.manifest['runtime_files'].append({'repo_path':relative,'snapshot_path':'snapshot/'+relative,
                'sha256':byte_hash(self.repo/relative)})
        self.manifest['freeze_version']='v21'
        self.config.update(review_version='v21',retrieval_limit=15,max_total_tokens=350000)
        self.write_json(self.bundle/'configuration.json',self.config); self.refresh_manifest()
        output=io.StringIO()
        with (patch.object(run_v18_regression,'REPO',self.repo),
              patch.object(sys,'argv',['runner','--bundle',str(self.bundle)]),
              patch.object(run_v18_regression,'local_api_key',side_effect=AssertionError('key')),
              patch.object(run_v18_regression,'verify_campaign',side_effect=AssertionError('campaign')),
              redirect_stdout(output)):
            run_v18_regression.main('v21')
        self.assertEqual(json.loads(output.getvalue())['predictions'],0)
        authorization=self.bundle.parent/'approval.json'; self.write_json(authorization,{})
        with (patch.object(run_v18_regression,'REPO',self.repo),
              patch.object(sys,'argv',['runner','--bundle',str(self.bundle),'--live','--authorization',str(authorization)]),
              patch.object(run_v18_regression,'verify_authorization',return_value={}),
              patch.object(run_v18_regression,'local_api_key',side_effect=AssertionError('key'))):
            with self.assertRaisesRegex(ValueError,'cumulative'): run_v18_regression.main('v21')
        self.assertFalse((self.bundle.parent/'run_v21').exists())


    def prepare_v22(self):
        for relative in ['scripts/run_v22_regression.py','scripts/score_v18_regression.py',
                         'scripts/diagnose_v22_run.py','scripts/score_frozen_results.py']:
            self.write(self.repo/relative,'# synthetic v22 frozen entry\n')
            self.write(self.bundle/('snapshot/'+relative),'# synthetic v22 frozen entry\n')
            self.manifest['runtime_files'].append({'repo_path':relative,'snapshot_path':'snapshot/'+relative,
                'sha256':byte_hash(self.repo/relative)})
        self.manifest['freeze_version']='v22'
        self.config.update(review_version='v22',retrieval_limit=15,max_total_tokens=450000,max_model_calls=80)
        self.write_json(self.bundle/'configuration.json',self.config); self.refresh_manifest()

    def test_v22_free_preflight_and_campaign_required_before_key(self):
        self.prepare_v22(); output=io.StringIO()
        with (patch.object(run_v18_regression,'REPO',self.repo),
              patch.object(sys,'argv',['runner','--bundle',str(self.bundle)]),
              patch.object(run_v18_regression,'local_api_key',side_effect=AssertionError('key')),
              patch.object(run_v18_regression,'verify_campaign',side_effect=AssertionError('campaign')),
              redirect_stdout(output)):
            run_v18_regression.main('v22')
        summary=json.loads(output.getvalue())
        self.assertEqual(summary['api_calls'],0)
        self.assertEqual(summary['budget']['max_model_calls'],80)
        self.assertEqual(summary['budget']['max_cost_usd'],'1.00')
        authorization=self.bundle.parent/'approval.json'; self.write_json(authorization,{})
        with (patch.object(run_v18_regression,'REPO',self.repo),
              patch.object(sys,'argv',['runner','--bundle',str(self.bundle),'--live','--authorization',str(authorization)]),
              patch.object(run_v18_regression,'verify_authorization',return_value={}),
              patch.object(run_v18_regression,'local_api_key',side_effect=AssertionError('key'))):
            with self.assertRaisesRegex(ValueError,'cumulative'): run_v18_regression.main('v22')
        self.assertFalse((self.bundle.parent/'run_v22').exists())

    def test_v22_new_capacity_cannot_raise_financial_or_model_ceilings(self):
        self.prepare_v22()
        for update in [{'max_model_calls':81},{'max_total_tokens':450001},{'max_cost_usd':'1.01'}]:
            self.write_json(self.bundle/'configuration.json',{**self.config,**update}); self.refresh_manifest()
            with self.subTest(update=update),self.assertRaises(ValueError):
                verify_freeze(self.bundle,self.repo)

    def test_v22_unbound_source_change_still_invalidates_freeze(self):
        self.prepare_v22()
        self.write(self.bundle/'snapshot/data/derived/source_sections_v15.jsonl','unbound changed source')
        with self.assertRaisesRegex(ValueError,'Frozen artifact changed'): verify_freeze(self.bundle,self.repo)

    def test_v22_metric_dependency_is_bound_to_runtime_snapshot(self):
        self.prepare_v22()
        self.assertIn('scripts/score_frozen_results.py',{r['repo_path'] for r in self.manifest['runtime_files']})
        self.write(self.repo/'scripts/score_frozen_results.py','# changed metrics')
        with self.assertRaisesRegex(ValueError,'Runtime changed'): verify_freeze(self.bundle,self.repo)

if __name__ == '__main__':
    unittest.main()
