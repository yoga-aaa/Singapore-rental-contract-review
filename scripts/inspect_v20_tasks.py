"""Input-only task/reference coverage diagnostic. No labels, prediction or API."""
import argparse
import json
import sys
from pathlib import Path

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO))
from src.evidence_packet_v19 import CoverageRetriever
from src.mechanism_tasks_v20 import tasks_for


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--inputs',type=Path,required=True)
    p.add_argument('--show-text',action='store_true')
    args=p.parse_args()
    retriever=CoverageRetriever.from_repo(REPO)
    for case in json.loads(args.inputs.read_text(encoding='utf-8')):
        if set(case)!={'case_id','housing_type','clause_text'}:
            raise ValueError('Expected input-only cases, not annotated data')
        packet=retriever.packet(case['clause_text'],case['housing_type'])
        refs={r['evidence_id']:r for r in packet['references']}
        tasks,truncated=tasks_for(case['clause_text'],packet,case['housing_type'])
        summary={'case_id':case['case_id'],'task_count':len(tasks),'task_truncated':truncated,
                 'packet_truncated':packet['truncated'],
                 'tasks':[{'id':t['task_id'],'mechanism':t['mechanism'],'spans':t['contract_span_ids'],
                           'reference_groups':[[refs[r]['section'] for r in group] for group in t['required_reference_groups']],
                           'missing_reference_group':any(not group for group in t['required_reference_groups'])}
                          for t in tasks]}
        if args.show_text: summary['contract']=case['clause_text']
        print(json.dumps(summary,ensure_ascii=False))


if __name__=='__main__': main()
