"""A separate immutable v18 regression; old v16/v17 bundles are never edited.

The predictor hashes scoring bytes but never parses labels. Expanded sources
are an experiment against unchanged, exposed CEA-comparison labels, not a new
independently adjudicated gold set. Only the explicit live command spends.
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from src.application import EXPECTED_INDEX_SHA, safety_issue
from src.frozen_external import INPUT_FIELDS, byte_hash, read_json, require, safe_member
from src.official_sources import load_official_index

RUNNER = 'scripts/run_v18_regression.py'


def runtime_files(repo: Path, version='v18') -> list[Path]:
    extra=[repo/f'scripts/run_{version}_regression.py'] if version!='v18' else []
    if version=='v20': extra.append(repo/'scripts/score_v18_regression.py')
    return sorted([*(repo/'src').glob('*.py'), repo/RUNNER, repo/'requirements.txt', *extra])


def validate_cases(cases: list) -> None:
    require(isinstance(cases, list) and len(cases) == 20, 'Expected the original 20 cases')
    require([c.get('case_id') for c in cases] == [f'NEW_{i:02d}' for i in range(1, 21)],
            'Original ordered case IDs required')
    for case in cases:
        require(set(case) == INPUT_FIELDS, 'Labels or unexpected fields in predictor input')
        require(case['housing_type'] in {'HDB', 'Private Residential'}, 'Unsupported housing')
        require(isinstance(case['clause_text'], str) and 0 < len(case['clause_text']) <= 6000,
                'Invalid or oversized clause')
        require(safety_issue(case['clause_text'], case['housing_type']) is None,
                'Synthetic input safety check failed')


def build_freeze(repo: Path, original: Path, destination: Path, version='v18') -> dict:
    repo, original, destination = repo.resolve(), original.resolve(), destination.resolve()
    require(not destination.is_relative_to(repo), 'Keep the regression outside the public repository')
    require(not destination.exists(), 'Never overwrite a frozen batch')
    require(version in {'v18','v19','v20'}, 'Unsupported expanded-source version')
    old = read_json(original/'manifest.json')
    require(old['freeze_version'] == 'v17' and old['case_count'] == 20, 'Expected original v17 freeze')
    for entry in old['artifacts']:
        require(byte_hash(safe_member(original, entry['path'])) == entry['sha256'],
                'Original frozen artifact changed')
    cases_path = safe_member(original, old['input_path'])
    validate_cases(read_json(cases_path))
    require(byte_hash(repo/'data/derived/source_sections_v15.jsonl') == EXPECTED_INDEX_SHA,
            'CEA source snapshot changed')
    load_official_index(repo)  # Verify all publisher articles before copying.
    policy = read_json(repo/f'data/live_budget_policy_{version}.json')
    config = {**policy, 'models':{'draft':'openai/gpt-4.1', 'verifier':'openai/gpt-4o'},
              'review_version':version, 'retrieval_limit':12 if version=='v18' else 15, 'max_cost_usd':'1.00'}
    destination.mkdir(parents=True)
    def copy(source: Path, relative: str):
        target = safe_member(destination, relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    copy(cases_path, 'inputs/cases.json')
    copy(safe_member(original, old['label_path']), 'scoring/labels.confirmed.json')
    with (destination/'configuration.json').open('x', encoding='utf-8') as file:
        json.dump(config, file, ensure_ascii=False, indent=2)
    runtime = []
    for source in runtime_files(repo,version):
        relative = source.relative_to(repo).as_posix()
        copy(source, 'snapshot/'+relative)
        runtime.append({'repo_path':relative, 'snapshot_path':'snapshot/'+relative,
                        'sha256':byte_hash(source)})
    sources = [repo/'data/derived/source_sections_v15.jsonl',
               repo/'data/official_reference_registry_v18.json',
               repo/f'data/live_budget_policy_{version}.json',
               *(repo/'data/official_sources_v18').glob('*.html'),
               repo/'data/official_sources_v18/index_v18.jsonl',
               repo/'data/official_sources_v18/snapshot_manifest_v18.json',
               *(repo/'data/source_documents').glob('*.pdf')]
    for source in sources:
        copy(source, 'snapshot/'+source.relative_to(repo).as_posix())
    artifacts = [{'path':p.relative_to(destination).as_posix(), 'sha256':byte_hash(p)}
                 for p in sorted(destination.rglob('*')) if p.is_file()]
    manifest = {'freeze_version':version, 'status':'frozen_regression_authorization_pending',
                'hash_method':'sha256_exact_bytes', 'case_count':20,
                'evaluation_type':'Expanded-source regression on 20 exposed AI-authored cases; unchanged v17 comparison labels; not independent generalization or expert gold',
                'input_path':'inputs/cases.json', 'label_path':'scoring/labels.confirmed.json',
                'configuration_path':'configuration.json',
                'section_index_path':'snapshot/data/derived/source_sections_v15.jsonl',
                'official_index_path':'snapshot/data/official_sources_v18/index_v18.jsonl',
                'snapshot_repo_path':'snapshot', 'runtime_files':runtime, 'artifacts':artifacts,
                'original_manifest_sha256':byte_hash(original/'manifest.json'),
                'original_labels_sha256':byte_hash(safe_member(original, old['label_path'])),
                'created_at_utc':datetime.now(timezone.utc).isoformat()}
    with (destination/'manifest.json').open('x', encoding='utf-8') as file:
        json.dump(manifest, file, ensure_ascii=False, indent=2)
    return verify_freeze(destination, repo)


def verify_freeze(bundle: Path, repo: Path) -> dict:
    manifest = read_json(bundle/'manifest.json')
    version=manifest.get('freeze_version')
    require(version in {'v18','v19','v20'}
            and manifest.get('status') == 'frozen_regression_authorization_pending'
            and manifest.get('hash_method') == 'sha256_exact_bytes'
            and manifest.get('case_count') == 20, 'Unexpected v18 freeze')
    entries = manifest['artifacts']
    required = {manifest[k] for k in ('input_path','label_path','configuration_path',
                                      'section_index_path','official_index_path')}
    paths = {e['path'] for e in entries}
    require(len(paths) == len(entries) and required <= paths, 'Incomplete or duplicated artifacts')
    for entry in entries:
        require(byte_hash(safe_member(bundle, entry['path'])) == entry['sha256'],
                'Frozen artifact changed: '+entry['path'])
    require(byte_hash(safe_member(bundle, manifest['label_path'])) == manifest['original_labels_sha256'],
            'Original labels must stay unchanged')
    expected = {p.relative_to(repo).as_posix() for p in runtime_files(repo,version)}
    require({e['repo_path'] for e in manifest['runtime_files']} == expected,
            'Runtime file set changed')
    for entry in manifest['runtime_files']:
        require(entry['snapshot_path'] in paths, 'Runtime snapshot not integrity-bound')
        require(byte_hash(safe_member(repo, entry['repo_path'])) == entry['sha256']
                == byte_hash(safe_member(bundle, entry['snapshot_path'])), 'Runtime changed')
    cases = read_json(safe_member(bundle, manifest['input_path']))
    validate_cases(cases)
    config = read_json(safe_member(bundle, manifest['configuration_path']))
    require(config.get('review_version') == version and config.get('retrieval_limit') == (12 if version=='v18' else 15),
            'Not the original v18 configuration')
    require(config['models'] == {'draft':'openai/gpt-4.1','verifier':'openai/gpt-4o'}, 'Model roles changed')
    require(type(config['max_model_calls']) is int and 1 <= config['max_model_calls'] <= 40,
            'Invalid call budget')
    require(type(config['max_total_tokens']) is int and 1000 <= config['max_total_tokens'] <= {'v18':200000,'v19':300000,'v20':350000}[version],
            'Invalid token budget')
    require(Decimal('0') < Decimal(config['max_cost_usd']) <= Decimal('1'), 'Invalid cost budget')
    approved_prices = {'openai/gpt-4.1':('2.00','8.00'), 'openai/gpt-4o':('2.50','10.00')}
    require(set(config['prices']) == set(approved_prices), 'Unexpected price/model set')
    for model, (prompt, completion) in approved_prices.items():
        price = config['prices'][model]
        require(price['input_usd_per_million'] == prompt and price['output_usd_per_million'] == completion
                and price['max_completion_tokens'] == 2400, 'Price/output ceiling changed')
    return {'manifest':manifest, 'config':config, 'cases':cases,
            'manifest_sha256':byte_hash(bundle/'manifest.json')}
