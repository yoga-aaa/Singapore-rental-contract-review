"""Revalidate saved final outputs only; no new inference or quote repair."""
import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.live_review import validate_output
from src.retrieval import LocalBM25Retriever
from src.rag_review import OUTPUT_SCHEMA

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bundle',type=Path,required=True); p.add_argument('--run',type=Path,required=True)
    args=p.parse_args()
    cases={c['case_id']:c for c in json.loads((args.bundle/'inputs/cases.json').read_text(encoding='utf-8'))}
    retriever=LocalBM25Retriever.from_jsonl(args.bundle/'snapshot/data/derived/source_sections_v15.jsonl')
    rows=[]
    for line in (args.run/'predictions.jsonl').read_text(encoding='utf-8').splitlines():
        row=json.loads(line); original=row['result']; case=cases[row['case_id']]
        if original['abstained']:
            rows.append({'case_id':row['case_id'],'label':original['label'],'changed':False})
            continue
        raw={key:original[key] for key in OUTPUT_SCHEMA['schema']['required']}
        raw['comparisons']=original['comparisons']
        result=validate_output(raw,retriever.search(case['clause_text'],case['housing_type'],limit=4),
                               clause_text=case['clause_text'],require_grounding=True)
        rows.append({'case_id':row['case_id'],'label':result.label,'changed':result.label!=original['label'],
                     'reason':result.reason})
    print(json.dumps({'kind':'v17 guards on saved v16 final outputs; NOT fresh live evaluation',
                      'api_calls':0,'cases':rows},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
