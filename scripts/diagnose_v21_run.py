"""Read-only, request-bound v21 diagnostics. Never reads labels or spends."""
import argparse
import hashlib
import io
import json
import sys
from pathlib import Path

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO))
from src.condition_diagnostics_v21 import diagnose
from src.evidence_packet_v19 import CoverageRetriever
from src.frozen_external import MeteredTransport,byte_hash,read_json,require,safe_member
from src.frozen_v18 import verify_freeze
from src.mechanism_tasks_v21 import tasks_for
from src.review_v21 import build_request


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bundle',type=Path,required=True)
    p.add_argument('--run',type=Path)
    args=p.parse_args(); bundle=args.bundle.resolve()
    checked=verify_freeze(bundle,REPO)
    require(checked['manifest']['freeze_version']=='v21','Only a matching v21 runtime can diagnose this freeze')
    retriever=CoverageRetriever.from_repo(safe_member(bundle,checked['manifest']['snapshot_repo_path']))
    responses={}; attempts={}; run=None
    if args.run:
        run=args.run.resolve()
        require(not run.is_relative_to(REPO),'Keep raw runs private')
        finish=read_json(run/'run_finished.json'); start=read_json(run/'run_started.json')
        require(start['bundle_manifest_sha256']==checked['manifest_sha256'],'Wrong run freeze')
        require(byte_hash(run/'calls.jsonl')==finish['calls_sha256'],'Recorded calls changed')
        for line in (run/'calls.jsonl').read_text(encoding='utf-8').splitlines():
            event=json.loads(line)
            if event['event']=='attempt': attempts[event['call_number']]=event
            if event['event']=='response': responses.setdefault(event['case_id'],[]).append(event)
    meter=MeteredTransport(checked['config'],io.StringIO())
    result=[]
    for case in checked['cases']:
        clause,housing=case['clause_text'],case['housing_type']
        packet=retriever.packet(clause,housing); tasks,truncated=tasks_for(clause,packet,housing)
        record={'case_id':case['case_id'],'task_count':len(tasks),'task_selection_truncated':truncated,
                'source_selection_truncated':packet['truncated'],
                'unknown_mechanism_tasks':sum(t['mechanism']=='other' for t in tasks),
                'tasks_with_source_gap':sum(not t['required_reference_groups'] or any(not g for g in t['required_reference_groups']) for t in tasks)}
        events=responses.get(case['case_id'],[])
        if len(events)==2:
            parsed=[json.loads(e['body']['choices'][0]['message']['content']) for e in events]
            requests=[build_request(housing,clause,packet),build_request(housing,clause,packet,parsed[0])]
            for request,event in zip(requests,events):
                bounded,_,_=meter.reservation(request)
                sha=hashlib.sha256(json.dumps(bounded,ensure_ascii=False,sort_keys=True).encode('utf-8')).hexdigest()
                require(sha==attempts[event['call_number']]['request_sha256'],'Cannot reproduce actual model input')
            record['recorded_stage_diagnostics']=diagnose(parsed[0],parsed[1],clause,packet,housing)
        elif run: record['recorded_stage_status']='missing or partial; no quality score'
        result.append(record)
    print(json.dumps({'version':'v21','manifest_sha256':checked['manifest_sha256'],
        'mode':'recorded_trace_diagnosis' if run else 'input_only_preflight',
        'api_calls_this_command':0,'predictions_this_command':0,'quality_metrics':None,
        'cases':result},ensure_ascii=False,indent=2))


if __name__=='__main__': main()
