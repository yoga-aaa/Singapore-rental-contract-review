"""Private guard-only replay of v18 responses; NOT a v19 model evaluation.

No labels, credentials or API calls. Mechanism tags are diagnostic heuristics
for old responses that did not include them. This cannot predict new recall.
"""
import argparse
import json
import re
import sys
from pathlib import Path

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO))
from src.contract_spans import contract_spans
from src.evidence_packet_v18 import PacketRetriever
from src.evidence_packet_v19 import CoverageRetriever
from src.frozen_external import byte_hash,read_json,require,safe_member
from src.review_v19 import claim_issue, finalize


def mechanism(row,clause):
    spans=contract_spans(clause)
    text=' '.join(spans[c] for c in row['contract_span_ids'])
    topic=row['topic']
    if topic=='security_deposit':
        if re.search(r'\bforfeit\w*\b',text,re.I): return 'deposit_forfeiture_amount'
        if re.search(r'\b(?:deduct|recover|replenish)\w*\b',text,re.I): return 'deposit_deduction_process'
        return 'refund_trigger'
    if topic=='minor_repair':
        if re.search(r'\bcarry out\b.{0,100}\bwithin\b',text,re.I): return 'repair_completion_deadline'
        if re.search(r'\b(?:air.condition\w*|servic\w*)\b',text,re.I): return 'repair_causation'
        return 'repair_allocation'
    if topic=='rent':
        if re.search(r'\bdouble.{0,20}rent\b',text,re.I): return 'holdover_charge'
        if re.search(r'\b(?:late|interest|overdue)\b',text,re.I): return 'late_payment_charge'
        if re.search(r'\b(?:review|revis\w*|increas\w*)\b',text,re.I): return 'current_term_rent_review'
        return 'other'
    if topic=='termination_notice':
        if re.search(r'\b(?:acceptable|satisfactory) to the Landlord\b',text,re.I): return 'exit_evidence_acceptance'
        return 'landlord_exit_trigger' if re.search(r'\bLandlord\b.{0,30}\bterminat\w*\b',text,re.I) else 'tenant_break_clause'
    if topic=='occupancy_subletting':
        return 'guest_documentation' if re.search(r'\bguest\w*\b',text,re.I) else 'subletting_permission' if re.search(r'\bsublet\w*\b',text,re.I) else 'occupancy'
    if topic=='dispute_resolution': return 'expert_evidence_and_fees' if re.search(r'\b(?:surveyor|report|expert)\b',text,re.I) else 'dispute_route'
    return {'utilities':'utilities','stamp_duty':'stamp_duty'}.get(topic,'other')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bundle',type=Path,required=True)
    p.add_argument('--run',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    args=p.parse_args()
    manifest=read_json(args.bundle/'manifest.json')
    for entry in manifest['artifacts']:
        require(byte_hash(safe_member(args.bundle,entry['path']))==entry['sha256'],'Frozen artifact changed')
    finish=read_json(args.run/'run_finished.json')
    require(finish['status']=='complete','Only completed historical outputs can be replayed')
    require(byte_hash(args.run/'calls.jsonl')==finish['calls_sha256'],'Calls changed')
    require(byte_hash(args.run/'predictions.jsonl')==finish['predictions_sha256'],'Historical predictions changed')
    cases=read_json(safe_member(args.bundle,manifest['input_path']))
    inputs={c['case_id']:c for c in cases}
    events=[json.loads(l) for l in (args.run/'calls.jsonl').read_text(encoding='utf-8').splitlines()]
    snapshot=safe_member(args.bundle,manifest['snapshot_repo_path'])
    old,new=PacketRetriever.from_repo(snapshot),CoverageRetriever.from_repo(snapshot)
    diagnostics=[]
    for event in events:
        if event['event']!='response' or event['call_number']%2:
            continue
        case=inputs[event['case_id']]
        packet=old.packet(case['clause_text'],case['housing_type'])
        proposed=new.packet(case['clause_text'],case['housing_type'])
        refs={r['evidence_id']:r for r in packet['references']}
        raw=json.loads(event['body']['choices'][0]['message']['content'])
        tagged_raw={**raw,'comparisons':[{**r,'mechanism':mechanism(r,case['clause_text'])} for r in raw['comparisons']]}
        rejected=[]
        for i,row in enumerate(raw['comparisons']):
            if row['verdict']=='supported' and row['relation']!='uncertain':
                tagged={**row,'mechanism':mechanism(row,case['clause_text'])}
                issue=claim_issue(tagged,case['clause_text'],refs)
                if issue:
                    rejected.append({'comparison_number':i+1,'mechanism':tagged['mechanism'],'issue':issue})
        guarded=finalize(tagged_raw,case['clause_text'],packet,case['housing_type'])
        diagnostics.append({'case_id':case['case_id'],'rejected_old_comparisons':rejected,
                            'historical_guard_only_output_label':guarded.label,
                            'historical_released_comparison_count':len(guarded.comparisons),
                            'v19_reference_locations':[r['section'] for r in proposed['references']],
                            'v19_omitted_required_locations':proposed['omitted_required_locations'],
                            'v19_packet_truncated':proposed['truncated']})
    result={'status':'guard_only_offline_replay','new_api_calls':0,'new_cost_usd':'0',
            'v19_model_predictions':0,'v19_metrics':None,
            'limitation':'Heuristic tags and guard-only finalization on old v18 outputs/old packets; no new prompt executed. Not evidence of v19 recall, precision or citation support.',
            'historical_calls_sha256':finish['calls_sha256'],
            'rejected_old_comparison_count':sum(len(r['rejected_old_comparisons']) for r in diagnostics),
            'results':diagnostics}
    require(not args.out.resolve().is_relative_to(REPO),'Keep case-level diagnostics private')
    with args.out.open('x',encoding='utf-8') as file:
        json.dump(result,file,ensure_ascii=False,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!='results'},indent=2))


if __name__=='__main__':
    main()
