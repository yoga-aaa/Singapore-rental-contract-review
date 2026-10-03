"""Read-only v22 input coverage or request-bound trace diagnosis, no credits."""
import argparse
import json
import sys
from pathlib import Path

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO))
from src.condition_diagnostics_v22 import input_record,reproduce_trace
from src.evidence_packet_v22 import ConditionRetriever
from src.frozen_external import byte_hash,read_json,require,safe_member
from src.frozen_v18 import verify_freeze


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bundle',type=Path,required=True)
    p.add_argument('--run',type=Path)
    args=p.parse_args(); bundle=args.bundle.resolve()
    checked=verify_freeze(bundle,REPO)
    require(checked['manifest']['freeze_version']=='v22','Matching v22 freeze required')
    retriever=ConditionRetriever.from_repo(safe_member(bundle,checked['manifest']['snapshot_repo_path']))
    responses={}; attempts={}; completed=set()
    if args.run:
        run=args.run.resolve()
        require(not run.is_relative_to(REPO),'Keep raw runs private')
        finish=read_json(run/'run_finished.json'); start=read_json(run/'run_started.json')
        require(start['bundle_manifest_sha256']==checked['manifest_sha256'],'Wrong run freeze')
        require(byte_hash(run/'calls.jsonl')==finish['calls_sha256'],'Recorded calls changed')
        require(byte_hash(run/'predictions.jsonl')==finish['predictions_sha256'],'Recorded predictions changed')
        completed=set(finish['completed_case_ids'])
        for line in (run/'calls.jsonl').read_text(encoding='utf-8').splitlines():
            event=json.loads(line)
            if event['event']=='attempt':
                require(event['call_number'] not in attempts,'Duplicate recorded attempt')
                attempts[event['call_number']]=event
            if event['event']=='response': responses.setdefault(event['case_id'],[]).append(event)
    records=[]
    for case in checked['cases']:
        packet=retriever.packet(case['clause_text'],case['housing_type'])
        record={'case_id':case['case_id'],**input_record(case['clause_text'],packet,case['housing_type'])}
        if case['case_id'] in completed:
            record['recorded_trace']=reproduce_trace(case,packet,responses.get(case['case_id'],[]),attempts,checked['config'])
        elif args.run: record['recorded_trace_status']='Incomplete case; no replay or quality score'
        records.append(record)
    print(json.dumps({'version':'v22','manifest_sha256':checked['manifest_sha256'],
        'mode':'recorded_trace_diagnosis' if args.run else 'input_only_preflight',
        'api_calls_this_command':0,'fresh_predictions_this_command':0,'quality_metrics':None,
        'cases':records},ensure_ascii=False,indent=2))


if __name__=='__main__': main()
