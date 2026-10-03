"""Complete one known, fully accounted token-limit stop without re-buying draft.

Explicit recovery, not an automatic retry: original artifacts remain intact.
The original US$1/40-call total includes ALL previous charges. Only the local
token safety ceiling increases; model, sources, prompts and labels stay fixed.
Never recover an unknown charge, provider failure or unaccounted attempt.
"""
import argparse
import hashlib
import json
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO))
from src.evidence_packet_v18 import PacketRetriever
from src.frozen_external import MeteredTransport, byte_hash, read_json, require, safe_member, verify_authorization
from src.frozen_v18 import verify_freeze
from src.live_review import local_api_key
from src.review_v18 import review_clause


def restore_accounting(events: list, finish: dict) -> dict:
    require(finish['status']=='partial_stopped' and finish['failure_type']=='BudgetStop'
            and finish['accounting']['unaccounted_attempt'] is False,
            'Only a fully accounted before-call budget stop can be completed')
    attempts=[e for e in events if e['event']=='attempt']
    responses=[e for e in events if e['event']=='response']
    require(len(events)==74 and len(attempts)==len(responses)==37
            and [a['call_number'] for a in attempts]==list(range(1,38))
            and [r['call_number'] for r in responses]==list(range(1,38)),
            'Expected exactly 37 accounted calls, not a failed/duplicated request')
    for i,(a,r) in enumerate(zip(attempts,responses)):
        expected=f'NEW_{i//2+1:02d}'
        require(a['case_id']==r['case_id']==expected
                and a['model']==('openai/gpt-4.1' if i%2==0 else 'openai/gpt-4o'),
                'Call sequence or model roles changed')
        usage=r['body']['usage']
        require(all(type(usage[k]) is int and usage[k]>=0 for k in
                    ('prompt_tokens','completion_tokens','total_tokens'))
                and usage['total_tokens']==usage['prompt_tokens']+usage['completion_tokens']
                and usage['total_tokens']>0 and not usage.get('is_byok'), 'Invalid prior usage')
        cost=Decimal(str(usage['cost']))
        require(cost.is_finite() and cost>=0, 'Unknown prior charge')
    totals={k:sum(r['body']['usage'][k] for r in responses) for k in
            ('prompt_tokens','completion_tokens','total_tokens')}
    totals.update(api_calls=37,cost_usd=str(sum((Decimal(str(r['body']['usage']['cost']))
                                             for r in responses),Decimal('0'))),unaccounted_attempt=False)
    require(totals==finish['accounting'], 'Previous provider totals do not reconcile')
    return {'totals':totals,'cached_attempt':attempts[-1],'cached_response':responses[-1]}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--authorization',type=Path,required=True)
    parser.add_argument('--live',action='store_true')
    args=parser.parse_args()
    bundle=args.bundle.resolve()
    checked=verify_freeze(bundle,REPO)
    verify_authorization(args.authorization,checked['manifest_sha256'],checked['config'])
    old=safe_member(bundle.parent,'run_v18')
    started,finish=read_json(old/'run_started.json'),read_json(old/'run_finished.json')
    require(started['bundle_manifest_sha256']==checked['manifest_sha256']
            and started['authorization_sha256']==byte_hash(args.authorization), 'Different original authorization')
    for name in ('predictions','calls'):
        require(byte_hash(old/(name+'.jsonl'))==finish[name+'_sha256'], 'Original run changed')
    rows=[json.loads(l) for l in (old/'predictions.jsonl').read_text(encoding='utf-8').splitlines()]
    require([r['case_id'] for r in rows]==finish['completed_case_ids']==[f'NEW_{i:02d}' for i in range(1,19)],
            'Unexpected completed cases')
    events=[json.loads(l) for l in (old/'calls.jsonl').read_text(encoding='utf-8').splitlines()]
    restored=restore_accounting(events,finish)
    config={**checked['config'],'max_total_tokens':300000}
    if not args.live:
        print(json.dumps({'status':'recovery_preflight_passed','new_api_calls':0,
                          'previous':restored['totals'],'remaining_calls':3,'max_total_cost_usd':config['max_cost_usd'],
                          'token_ceiling_amendment':{'from':200000,'to':300000}},indent=2))
        return
    out=safe_member(bundle.parent,'run_v18_completed')
    require(not out.exists(),'Recovery output exists: do not retry or overwrite')
    retriever=PacketRetriever.from_repo(safe_member(bundle,checked['manifest']['snapshot_repo_path']))
    key=local_api_key()
    require(bool(key),'Ignored local API credential required')
    out.mkdir()
    recovery={**started,'budget':{k:config[k] for k in ('max_model_calls','max_total_tokens','max_cost_usd')},
              'recovery_started_at_utc':datetime.now(timezone.utc).isoformat(),
              'recovery':'Complete remaining three calls; reuse already-paid NEW_19 draft; no financial/call cap increase',
              'predecessor_calls_sha256':finish['calls_sha256'],
              'predecessor_predictions_sha256':finish['predictions_sha256'],
              'token_ceiling_amendment':{'from':200000,'to':300000}}
    with (out/'run_started.json').open('x',encoding='utf-8') as file:
        json.dump(recovery,file,indent=2)
    status,failure='complete',None
    with (out/'calls.jsonl').open('x',encoding='utf-8',newline='\n') as log, \
         (out/'predictions.jsonl').open('x',encoding='utf-8',newline='\n') as predictions:
        log.write((old/'calls.jsonl').read_text(encoding='utf-8')); log.flush()
        predictions.write((old/'predictions.jsonl').read_text(encoding='utf-8')); predictions.flush()
        meter=MeteredTransport(config,log)
        meter.calls=37; meter.cost=Decimal(restored['totals']['cost_usd'])
        for k in ('prompt_tokens','completion_tokens','total_tokens'):
            setattr(meter,k,restored['totals'][k])
        cached_used=False
        cached_body=restored['cached_response']['body']
        cached_usage=cached_body['usage']
        def transport(payload,api_key):
            nonlocal cached_used
            if not cached_used:
                require(meter.case_id=='NEW_19' and payload['model']=='openai/gpt-4.1','Wrong cached stage')
                bounded,_,_=meter.reservation(payload)
                sha=hashlib.sha256(json.dumps(bounded,ensure_ascii=False,sort_keys=True).encode('utf-8')).hexdigest()
                require(sha==restored['cached_attempt']['request_sha256'],'Cached draft request differs')
                content=cached_body['choices'][0]['message']['content']
                result=json.loads(content) if isinstance(content,str) else content
                require(isinstance(result,dict),'Cached draft malformed')
                cached_used=True
                return result,{k:cached_usage[k] for k in ('prompt_tokens','completion_tokens','total_tokens')}
            return meter(payload,api_key)
        with patch('src.review_v18._request_openrouter',transport):
            try:
                for case in checked['cases'][18:]:
                    verify_freeze(bundle,REPO)
                    meter.case_id=case['case_id']
                    before=meter.accounting()
                    if not cached_used:
                        before['api_calls']-=1; before['total_tokens']-=cached_usage['total_tokens']
                        before['cost_usd']=str(meter.cost-Decimal(str(cached_usage['cost'])))
                    result=review_clause(case['housing_type'],case['clause_text'],retriever,api_key=key,allow_api=True)
                    after=meter.accounting()
                    row={'case_id':case['case_id'],'result':asdict(result),
                         'accounting':{'api_calls':after['api_calls']-before['api_calls'],
                                       'total_tokens':after['total_tokens']-before['total_tokens'],
                                       'cost_usd':str(meter.cost-Decimal(before['cost_usd']))}}
                    predictions.write(json.dumps(row,ensure_ascii=False)+'\n'); predictions.flush()
                    rows.append(row)
                    print(case['case_id']+' recorded',flush=True)
            except Exception as error:
                status,failure='partial_stopped',type(error).__name__
        final={'status':status,'failure_type':failure,'completed_case_ids':[r['case_id'] for r in rows],
               'accounting':meter.accounting(),'metrics':None,'citation_audit':'pending',
               'predictions_sha256':byte_hash(out/'predictions.jsonl'),'calls_sha256':byte_hash(out/'calls.jsonl'),
               'finished_at_utc':datetime.now(timezone.utc).isoformat()}
        with (out/'run_finished.json').open('x',encoding='utf-8') as file:
            json.dump(final,file,indent=2)
    print(json.dumps(final,indent=2))
    require(status=='complete','Recovery stopped; no further automatic retry')


if __name__=='__main__':
    main()
