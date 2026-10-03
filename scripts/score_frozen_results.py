"""Recompute a completed private batch and its bound audit; makes no API calls."""
import argparse
import hashlib
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.baseline_rules import review_clause
from src.frozen_external import safe_member

def load(path): return json.loads(path.read_text(encoding='utf-8'))
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def metrics(truth,pred):
    risk = {k for k,v in truth.items() if v=='review_required'}
    flags = {k for k,v in pred.items() if v=='review_required'}
    insufficient = {k for k,v in truth.items() if v=='insufficient_evidence'}
    unsafe = {k for k in insufficient if pred[k]!='insufficient_evidence'}
    return {'precision':len(risk&flags)/len(flags) if flags else None,
            'recall':len(risk&flags)/len(risk) if risk else None,
            'tp':len(risk&flags), 'fp':len(flags-risk), 'fn':len(risk-flags),
            'unsafe_non_abstention':len(unsafe)/len(insufficient) if insufficient else None,
            'unsafe_numerator':len(unsafe),'unsafe_denominator':len(insufficient),
            'abstention_count':sum(v=='insufficient_evidence' for v in pred.values())}

def score(bundle:Path,run:Path,audit:Path):
    manifest=load(bundle/'manifest.json')
    for entry in manifest['artifacts']:
        assert sha(safe_member(bundle,entry['path']))==entry['sha256'], 'Frozen artifact changed'
    finish=load(run/'run_finished.json')
    assert finish['status']=='complete', 'Do not headline a partial batch'
    assert sha(run/'predictions.jsonl')==finish['predictions_sha256']
    assert sha(run/'calls.jsonl')==finish['calls_sha256']
    rows=[json.loads(line) for line in (run/'predictions.jsonl').read_text(encoding='utf-8').splitlines()]
    cases=load(safe_member(bundle,manifest['input_path']))
    truths=load(safe_member(bundle,manifest['label_path']))['labels']
    truth={r['case_id']:r['ground_truth_label'] for r in truths}
    pred={r['case_id']:r['result']['label'] for r in rows}
    assert len(rows)==len(pred)==len(cases)==20 and set(pred)==set(truth)=={c['case_id'] for c in cases}
    baseline={c['case_id']:review_clause(c['housing_type'],c['clause_text']).predicted_label for c in cases}
    path=safe_member(bundle,manifest['section_index_path'])
    sources=[json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
    reviewed=load(audit)
    assert reviewed['predictions_sha256']==sha(run/'predictions.jsonl') and reviewed['index_sha256']==sha(path)
    findings={r['case_id']:r for r in reviewed['results']}
    non=[r for r in rows if r['result']['label']!='insufficient_evidence']
    assert len(findings)==len(reviewed['results'])==len(non) and set(findings)=={r['case_id'] for r in non}
    valid=0
    housing={c['case_id']:c['housing_type'] for c in cases}
    for r in non:
        assert r['result']['evidence'], 'Non-abstention without evidence'
        okay=all(any(s['source_id']==ev['source_id'] and s['section']==ev['source_section']
                      and s['housing_type']==housing[r['case_id']] and ev['quote'] in s['text']
                      for s in sources) for ev in r['result']['evidence'])
        valid+=okay
    return {'version':manifest['freeze_version'], 'evaluation_type':manifest['evaluation_type'],
            'rag':metrics(truth,pred),'baseline':metrics(truth,baseline),
            'locator_valid_numerator':valid,'non_abstention_denominator':len(non),
            'citation_supported_numerator':sum(f['verdict']=='supported' for f in findings.values()),
            'citation_supported_rate':sum(f['verdict']=='supported' for f in findings.values())/len(non) if non else None,
            'citation_auditor':reviewed['reviewer'],'owner_audit_confirmation':reviewed['owner_confirmation'],
            'accounting':finish['accounting'],'manifest_sha256':sha(bundle/'manifest.json'),
            'predictions_sha256':sha(run/'predictions.jsonl'),'labels_sha256':sha(safe_member(bundle,manifest['label_path'])),
            'index_sha256':sha(path),'audit_sha256':sha(audit)}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bundle',type=Path,required=True); p.add_argument('--run',type=Path,required=True)
    p.add_argument('--audit',type=Path,required=True)
    args=p.parse_args()
    print(json.dumps(score(args.bundle,args.run,args.audit),ensure_ascii=False,indent=2))
