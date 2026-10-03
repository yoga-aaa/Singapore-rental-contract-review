"""Freeze/preflight v18 without API calls; --live needs a new bound approval.

Predictions and raw provider replies are private, append-only and label-free.
An existing output directory or any failed request stops without auto-retry.
"""
import argparse
import json
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from src.evidence_packet_v18 import PacketRetriever
from src.frozen_external import MeteredTransport, byte_hash, require, safe_member, verify_authorization
from src.frozen_v18 import build_freeze, verify_freeze
from src.live_review import local_api_key
from src.review_v18 import review_clause


def main(version='v18'):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--freeze-from', type=Path)
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--authorization', type=Path)
    args = parser.parse_args()
    require(not (args.freeze_from and args.live), 'Freeze and paid execution must be separate commands')
    bundle = args.bundle.resolve()
    checked = (build_freeze(REPO, args.freeze_from, bundle,version) if args.freeze_from
               else verify_freeze(bundle, REPO))
    require(checked['manifest']['freeze_version']==version, 'Wrong runner for this frozen version')
    if not args.live:
        print(json.dumps({'status':'preflight_passed_authorization_pending', 'case_count':20,
                          'manifest_sha256':checked['manifest_sha256'], 'api_calls':0,
                          'predictions':0, 'budget':{k:checked['config'][k] for k in
                          ('max_model_calls','max_total_tokens','max_cost_usd')},
                          'evaluation_type':checked['manifest']['evaluation_type']}, indent=2))
        return
    verify_authorization(args.authorization, checked['manifest_sha256'], checked['config'])
    require(args.authorization.resolve().is_relative_to(bundle.parent), 'Approval must remain private')
    out = safe_member(bundle.parent, 'run_'+version)
    require(not out.exists(), 'Never overwrite, automatically resume or repeat this run')
    key = local_api_key()
    require(bool(key), 'Ignored local API credential required')
    retriever_class,reviewer=PacketRetriever,review_clause
    if version=='v19':
        from src.evidence_packet_v19 import CoverageRetriever
        from src.review_v19 import review_clause as v19_review
        retriever_class,reviewer=CoverageRetriever,v19_review
    retriever = retriever_class.from_repo(safe_member(bundle, checked['manifest']['snapshot_repo_path']))
    out.mkdir()
    started = {'started_at_utc':datetime.now(timezone.utc).isoformat(),
               'freeze_version':version, 'case_count':20,
               'bundle_manifest_sha256':checked['manifest_sha256'],
               'authorization_sha256':byte_hash(args.authorization),
               'evaluation_type':checked['manifest']['evaluation_type'],
               'budget':{k:checked['config'][k] for k in ('max_model_calls','max_total_tokens','max_cost_usd')}}
    with (out/'run_started.json').open('x', encoding='utf-8') as file:
        json.dump(started, file, indent=2)
    completed, status, failure = [], 'complete', None
    with (out/'calls.jsonl').open('x', encoding='utf-8', newline='\n') as log, \
         (out/'predictions.jsonl').open('x', encoding='utf-8', newline='\n') as predictions:
        meter = MeteredTransport(checked['config'], log)
        with patch('src.review_'+version+'._request_openrouter', meter):
            try:
                for case in checked['cases']:
                    require(byte_hash(bundle/'manifest.json') == checked['manifest_sha256'], 'Manifest changed')
                    verify_freeze(bundle, REPO)
                    meter.case_id = case['case_id']
                    before = meter.accounting()
                    result = reviewer(case['housing_type'], case['clause_text'], retriever,
                                           api_key=key, allow_api=True)
                    after = meter.accounting()
                    row = {'case_id':case['case_id'], 'result':asdict(result),
                           'accounting':{'api_calls':after['api_calls']-before['api_calls'],
                                         'total_tokens':after['total_tokens']-before['total_tokens'],
                                         'cost_usd':str(meter.cost-Decimal(before['cost_usd']))}}
                    predictions.write(json.dumps(row, ensure_ascii=False)+'\n')
                    predictions.flush()
                    completed.append(case['case_id'])
                    print(case['case_id']+' recorded', flush=True)
            except Exception as error:
                status, failure = 'partial_stopped', type(error).__name__
        finish = {'status':status, 'failure_type':failure, 'completed_case_ids':completed,
                  'accounting':meter.accounting(), 'metrics':None,
                  'citation_audit':'pending; model verifier verdict is not an independent citation audit',
                  'predictions_sha256':byte_hash(out/'predictions.jsonl'),
                  'calls_sha256':byte_hash(out/'calls.jsonl'),
                  'finished_at_utc':datetime.now(timezone.utc).isoformat()}
        with (out/'run_finished.json').open('x', encoding='utf-8') as file:
            json.dump(finish, file, indent=2)
    print(json.dumps(finish, indent=2))
    if status != 'complete':
        raise RuntimeError('Partial batch preserved; no automatic retries or headline metrics')


if __name__ == '__main__':
    main()
