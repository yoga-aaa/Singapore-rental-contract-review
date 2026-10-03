"""Input-only diagnostics and exact recorded-request replay; never fresh eval."""
import hashlib
import io
import json
from unittest.mock import patch
from src.condition_checks_v23 import assess,direct_source_available
from src.frozen_external import MeteredTransport,require
from src.mechanism_tasks_v22 import plan_for
from src.review_v23 import review_clause


def input_record(clause,packet,housing):
    plan=plan_for(clause,packet,housing)
    refs={r['evidence_id']:r for r in packet['references']}
    return {'source_count':len(refs),'source_selection_truncated':packet['truncated'],
        'candidate_task_count':plan['candidate_count'],'deduplicated_task_count':plan['deduplicated_count'],
        'selected_task_count':len(plan['tasks']),'dropped_task_count':len(plan['dropped_tasks']),
        'task_selection_truncated':plan['truncated'],
        'unknown_mechanism_tasks':sum(t['mechanism']=='other' for t in plan['tasks']),
        'tasks_without_positive_source_conditions':sum(not direct_source_available(t,refs) for t in plan['tasks']),
        'coverage_is_not_semantic_support':True}


def reproduce_trace(case,packet,events,attempts,config):
    """Uses only persisted responses; all executed requests must hash-match."""
    meter=MeteredTransport(config,io.StringIO())
    position=0; stages=[]
    class Retriever:
        def packet(self,*args): return packet
    def recorded(payload,unused_key):
        nonlocal position
        require(position<len(events),'Missing recorded stage; no API fallback')
        event=events[position]; position+=1
        attempt=attempts.get(event['call_number'])
        require(attempt and attempt['case_id']==case['case_id']==event['case_id'],'Wrong recorded case')
        bounded,_,_=meter.reservation(payload)
        sha=hashlib.sha256(json.dumps(bounded,ensure_ascii=False,sort_keys=True).encode('utf-8')).hexdigest()
        require(sha==attempt['request_sha256'],'Cannot reproduce actual v23 model input')
        body=event['body']; content=body['choices'][0]['message']['content']
        raw=json.loads(content) if isinstance(content,str) else content
        require(isinstance(raw,dict),'Invalid recorded JSON completion')
        data=json.loads(payload['messages'][1]['content'])
        stage=payload['response_format']['json_schema']['name'].removeprefix('conditions_').removesuffix('_v23')
        entry={'stage':stage,'request_sha256_matched':True,'model':payload['model'],
               'task_ids':[t['task_id'] for t in data['tasks']]}
        if stage!='extract':
            checked=assess(raw,data['tasks'],case['clause_text'],packet,case['housing_type'])
            entry.update(accepted_task_count=len(checked['accepted']),unsettled_task_count=len(checked['unsettled']),
                         issue_codes=sorted({i['code'] for i in checked['issues']}),fatal=checked['fatal'])
        stages.append(entry)
        return raw,{k:body['usage'][k] for k in ('prompt_tokens','completion_tokens','total_tokens')}
    with (patch('src.review_v23._request_openrouter',side_effect=recorded),
          patch('src.review_v23.local_api_key',side_effect=AssertionError('Diagnostic cannot read keys'))):
        result=review_clause(case['housing_type'],case['clause_text'],Retriever(),api_key='recorded-trace-only')
    require(position==len(events),'Recorded extra stages do not match the bounded pipeline')
    return {'mode':'recorded_response_replay_not_fresh_inference','matched_requests':position,
            'stages':stages,'replayed_recorded_decision':result.label,'quality_metrics':None}
