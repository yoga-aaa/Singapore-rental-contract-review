"""Read-only private error diagnosis, never a quality evaluation or prediction."""
import argparse
import json
import sys
from pathlib import Path

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO))
from src.evidence_packet_v19 import CoverageRetriever
from src.frozen_external import byte_hash,read_json,require,safe_member
from src.review_v18 import supported_issue
from src.review_v19 import claim_issue,normalized,response_issue
from src.contract_spans import contract_spans


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bundle',type=Path,required=True)
    p.add_argument('--run',type=Path,required=True)
    p.add_argument('--case',nargs='+')
    args=p.parse_args()
    manifest=read_json(args.bundle/'manifest.json')
    finish=read_json(args.run/'run_finished.json')
    require(finish['status']=='complete','Wait for completion before diagnosing')
    require(byte_hash(args.run/'calls.jsonl')==finish['calls_sha256'],'Recorded calls changed')
    for entry in manifest['artifacts']:
        require(byte_hash(safe_member(args.bundle,entry['path']))==entry['sha256'],'Frozen artifact changed')
    cases={r['case_id']:r for r in read_json(safe_member(args.bundle,manifest['input_path']))}
    retriever=CoverageRetriever.from_repo(safe_member(args.bundle,manifest['snapshot_repo_path']))
    for line in (args.run/'calls.jsonl').read_text(encoding='utf-8').splitlines():
        event=json.loads(line)
        if event['event']!='response' or event['call_number']%2 or (args.case and event['case_id'] not in args.case):
            continue
        case=cases[event['case_id']]
        packet=retriever.packet(case['clause_text'],case['housing_type'])
        refs={r['evidence_id']:r for r in packet['references']}
        spans=contract_spans(case['clause_text'])
        raw=json.loads(event['body']['choices'][0]['message']['content'])
        issue=response_issue(raw,case['clause_text'],packet,True)
        rows=[]
        if not issue:
            for row in raw['comparisons']:
                rows.append({'contract':' '.join(spans[c] for c in row['contract_span_ids']),
                             'mechanism':row['mechanism'],'topic':row['topic'],'verdict':row['verdict'],'relation':row['relation'],
                             'references':[{'section':refs[r]['section'],'clause_id':refs[r].get('clause_id'),'topics':refs[r]['topics']} for r in row['reference_ids']],
                             'reference_claim':row['reference_claim'],'difference':row['difference'],
                             'consequence':row['tenant_consequence'],'question':row['question'],
                             'v19_issue':claim_issue(row,case['clause_text'],refs),
                             'base_issue':supported_issue(normalized({'comparisons':[row]})['comparisons'][0],case['clause_text'],refs,case['housing_type'])})
        print(json.dumps({'case_id':event['case_id'],'shape_issue':issue,'rows':rows},ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
