"""Score only after predictions are finished; no model or key access.

Citation locator validity and independently audited substantive support are
separate. The latter stays null without an exact-output-bound audit.
"""
import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.frozen_external import byte_hash, read_json, require, safe_member
from scripts.score_frozen_results import metrics


def lines(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def score(bundle: Path, run: Path, audit: Path | None = None) -> dict:
    manifest = read_json(bundle/'manifest.json')
    require(manifest['freeze_version'] in {'v18','v19'}, 'Expected expanded-source freeze')
    for entry in manifest['artifacts']:
        require(byte_hash(safe_member(bundle,entry['path'])) == entry['sha256'], 'Frozen artifact changed')
    started, finish = read_json(run/'run_started.json'), read_json(run/'run_finished.json')
    require(started['bundle_manifest_sha256'] == byte_hash(bundle/'manifest.json'), 'Run belongs to another freeze')
    require(finish['status'] == 'complete' and not finish['accounting']['unaccounted_attempt'],
            'Partial or unaccounted batch must not produce headline metrics')
    for name in ('predictions','calls'):
        require(byte_hash(run/(name+'.jsonl')) == finish[name+'_sha256'], 'Run artifact changed')
    rows = lines(run/'predictions.jsonl')
    cases = read_json(safe_member(bundle,manifest['input_path']))
    labels_path = safe_member(bundle,manifest['label_path'])
    require(byte_hash(labels_path) == manifest['original_labels_sha256'], 'Labels changed')
    labels = read_json(labels_path)['labels']
    truth = {row['case_id']:row['ground_truth_label'] for row in labels}
    pred = {row['case_id']:row['result']['label'] for row in rows}
    require(len(rows) == len(cases) == len(labels) == len(truth) == len(pred) == 20
            and set(truth) == set(pred) == {c['case_id'] for c in cases}, 'Missing/duplicated cases')
    require(set(truth.values()) <= {'review_required','no_material_difference_found','insufficient_evidence'}
            and set(pred.values()) <= {'review_required','no_material_difference_found','insufficient_evidence'},
            'Unknown label')
    calls = lines(run/'calls.jsonl')
    attempts = [c for c in calls if c['event']=='attempt']
    responses = [c for c in calls if c['event']=='response']
    require(len(attempts) == len(responses) == finish['accounting']['api_calls']
            and {c['call_number'] for c in attempts} == {c['call_number'] for c in responses}
            and not any(c['event']=='stop' for c in calls), 'Incomplete call accounting')
    require(sum(c['body']['usage']['total_tokens'] for c in responses) == finish['accounting']['total_tokens']
            and sum((Decimal(str(c['body']['usage']['cost'])) for c in responses),Decimal('0'))
            == Decimal(finish['accounting']['cost_usd']), 'Provider accounting mismatch')
    require(sum(r['accounting']['api_calls'] for r in rows) == len(responses)
            and sum(r['accounting']['total_tokens'] for r in rows) == finish['accounting']['total_tokens']
            and sum((Decimal(r['accounting']['cost_usd']) for r in rows),Decimal('0'))
            == Decimal(finish['accounting']['cost_usd']), 'Case accounting mismatch')
    sources = lines(safe_member(bundle,manifest['section_index_path'])) + lines(safe_member(bundle,manifest['official_index_path']))
    housing = {c['case_id']:c['housing_type'] for c in cases}
    non = [r for r in rows if r['result']['label'] != 'insufficient_evidence']
    locator_valid = []
    for row in non:
        evidence = row['result']['evidence']
        okay = bool(evidence) and all(any(s['source_id'] == e['source_id']
                    and s['section'] == e['source_section'] and e['quote'] and e['quote'] in s['text']
                    and s['housing_type'] in {housing[row['case_id']],'Both'}
                    and s['source_kind'] == e['source_kind']
                    for s in sources) for e in evidence)
        if okay:
            locator_valid.append(row['case_id'])
    measured=metrics(truth,pred)
    recall_met=measured['recall']>=0.85
    safety_met=measured['fp']==0 and measured['unsafe_numerator']==0
    summary = {'version':manifest['freeze_version'],'evaluation_type':manifest['evaluation_type'],
               'case_count':20,'rag':metrics(truth,pred),
               'false_negative_case_ids':[k for k in truth if truth[k]=='review_required' and pred[k]!='review_required'],
               'false_positive_case_ids':[k for k in truth if truth[k]!='review_required' and pred[k]=='review_required'],
               'unsafe_case_ids':[k for k in truth if truth[k]=='insufficient_evidence' and pred[k]!='insufficient_evidence'],
               'target_recall':0.85,'recall_target_met':recall_met,'safety_gate_met':safety_met,
               'target_met':False,
               'acceptance_rule':'Recall >=85%, zero false positives, zero unsafe non-abstentions, citation support >=95%; audit required. No real-world zero-error guarantee.',
               'locator_valid_numerator':len(locator_valid),'non_abstention_denominator':len(non),
               'locator_valid_rate':len(locator_valid)/len(non) if non else None,
               'citation_supported_numerator':None,'citation_supported_rate':None,
               'citation_audit_status':'pending; not inferred from the model verifier',
               'accounting':finish['accounting'], 'manifest_sha256':byte_hash(bundle/'manifest.json'),
               'predictions_sha256':byte_hash(run/'predictions.jsonl'), 'labels_sha256':byte_hash(labels_path),
               'index_sha256':byte_hash(safe_member(bundle,manifest['section_index_path'])),
               'official_index_sha256':byte_hash(safe_member(bundle,manifest['official_index_path']))}
    if audit:
        reviewed = read_json(audit)
        for key in ('predictions_sha256','index_sha256','official_index_sha256'):
            require(reviewed[key] == summary[key], 'Citation audit bound to another output/source')
        findings = {r['case_id']:r for r in reviewed['results']}
        require(len(findings) == len(reviewed['results']) == len(non)
                and set(findings) == {r['case_id'] for r in non}, 'Audit must cover every non-abstention')
        require(all(r['verdict'] in {'supported','unsupported','uncertain'} and r['reason'].strip()
                    for r in findings.values()), 'Invalid audit verdict or empty rationale')
        supported = sum(r['verdict']=='supported' for r in findings.values())
        summary.update(citation_supported_numerator=supported,
                       citation_supported_rate=supported/len(non) if non else None,
                       citation_audit_status=reviewed['reviewer'],
                       owner_audit_confirmation=reviewed['owner_confirmation'], audit_sha256=byte_hash(audit))
        summary['target_met']=recall_met and safety_met and len(locator_valid)==len(non) and bool(non) and supported/len(non)>=0.95
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--run',type=Path,required=True)
    parser.add_argument('--audit',type=Path)
    parser.add_argument('--out',type=Path)
    args = parser.parse_args()
    result = score(args.bundle,args.run,args.audit)
    if args.out:
        require(args.out.resolve().is_relative_to(args.run.resolve().parent)
                and not args.out.resolve().is_relative_to(Path(__file__).resolve().parents[1]), 'Keep results private')
        with args.out.open('x',encoding='utf-8') as file:
            json.dump(result,file,ensure_ascii=False,indent=2)
    print(json.dumps(result,ensure_ascii=False,indent=2))
