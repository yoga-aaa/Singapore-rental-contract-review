"""v24 original-ID binding plus unchanged positive semantic contrast gates."""
from src.condition_facts_v21 import FIELDS,KINDS,SCENARIOS,atoms_issue,contrast_issue,has
from src.contract_spans import contract_spans
from src.review_v21 import row_shape_issue as base_shape
from src.routing_text_v22 import match_text
from src.evidence_ids_v24 import catalogue,resolve_row

def bound_atoms_issue(atoms,text):
    if not isinstance(atoms,dict) or set(atoms)!=set(FIELDS):
        return 'Invalid condition dimensions.'
    if any(not isinstance(v,str) or (v and v not in text) for v in atoms.values()):
        return 'Restored interval is not bound to the original.'
    return None if atoms['action'] else 'Observable action required.'

CORE={'task_id','contract_terms','reference_terms','relation','contrast_kind','scenario','decision'}


def core(row):
    return {k:v for k,v in row.items() if k!='checked_context_ids'}


def shape_issue(row,tasks,refs):
    if not isinstance(row,dict) or set(row)!=CORE|{'checked_context_ids'}:
        return 'Malformed condition comparison fields.'
    issue=base_shape(core(row),tasks,refs,True)
    if issue: return issue
    ids=row['checked_context_ids']
    if not isinstance(ids,list) or any(not isinstance(c,str) for c in ids) or len(ids)!=len(set(ids)):
        return 'Malformed context acknowledgement.'
    return None


def direct_source_available(task,refs):
    groups=task['required_reference_groups']
    if not groups or any(not g for g in groups): return False
    text=' '.join(refs[r]['text'] for g in groups for r in g)
    return all(term.casefold() in text.casefold() for term in task['required_fact_terms'])


def row_issue(row,task,clause,refs,housing):
    spans=contract_spans(clause)
    selected=' '.join(spans[c] for c in task['contract_span_ids'])
    issue=bound_atoms_issue(row['contract_terms'],selected)
    if issue: return ('invalid_literal_atoms',issue)
    if set(row['checked_context_ids'])!=set(task['contract_span_ids']):
        return ('missing_context','Not all bound original context was assessed.')
    chosen={f['reference_id'] for f in row['reference_terms']}
    groups=task['required_reference_groups']
    if not direct_source_available(task,refs):
        return ('source_gap','No direct positive source for a required mechanism condition.')
    if not chosen or any(not chosen.intersection(g) for g in groups):
        return ('missing_reference_selection','A required source group was not selected.')
    if not chosen <= {r for g in groups for r in g}:
        return ('wrong_source','Neighbor evidence was selected for a different mechanism.')
    for f in row['reference_terms']:
        ref=refs[f['reference_id']]
        if ref['housing_type'] not in {housing,'Both'}:
            return ('wrong_housing','Wrong housing source scope.')
        issue=bound_atoms_issue(f['terms'],ref['text'])
        if issue: return ('invalid_literal_atoms',issue)
    reference_atoms=' '.join(v for f in row['reference_terms'] for v in f['terms'].values())
    if any(t.casefold() not in reference_atoms.casefold() for t in task['required_fact_terms']):
        return ('missing_reference_condition','A material positive reference condition was not extracted.')
    mechanism=task['mechanism']
    reference=' '.join(refs[r]['text'] for r in sorted(chosen))
    if mechanism=='other': return ('unsupported_mechanism','No registered comparison mechanism.')
    if mechanism=='expert_evidence_and_fees' and not (has(r'\b(?:expert|surveyor|report)\w*\b',reference) and has(r'\b(?:fee|cost)\w*\b',reference)):
        return ('source_gap','Dispute routes do not settle expert fees.')
    if mechanism=='guest_documentation' and not has(r'\bguests?\b',reference):
        return ('source_gap','Occupiers do not settle ordinary guests.')
    kind=KINDS.get(mechanism)
    if row['relation']=='tenant_adverse':
        if kind=='compliant_tenant_exit' and has(
            r'\bonly (?:if|when|where)\b.{0,60}\bTenant\b.{0,40}\b(?:defaults?|breaches?|fails? to pay)\b',
            selected):
            return ('unproven_scenario','An express tenant-default-only exit does not apply to the compliant-tenant scenario.')
        if not kind or row['contrast_kind']!=kind or row['scenario']!=SCENARIOS[kind]:
            return ('wrong_contrast','No supported typed scenario for this mechanism.')
        expected={'refund_trigger':{'landlord'},'repair_causation':{'landlord'},
            'landlord_exit_trigger':{'landlord','either party'},
            'current_term_rent_review':{'landlord'},'repair_completion_deadline':{'tenant'},
            'late_payment_charge':{'tenant'},'holdover_charge':{'tenant'},
            'deposit_forfeiture_amount':{'landlord','deposit','security deposit'},
            'exit_evidence_acceptance':{'tenant','landlord'},'damage_after_handover':{'landlord','tenant'},
            'subletting_permission':{'tenant'},'deposit_deduction_process':{'landlord'}}
        actor=match_text(row['contract_terms']['actor']).strip().casefold()
        if mechanism in expected and actor.removeprefix('the ') not in expected[mechanism]:
            return ('actor_mismatch','The active role for the selected action is missing or mismatched.')
    elif row['contrast_kind']!='none' or row['scenario']!='none':
        return ('wrong_contrast','Non-adverse conclusions cannot contain an adverse scenario.')
    # Matching aliases never alter the quotation or the source object.
    matched={**row,'contract_terms':{k:match_text(v) for k,v in row['contract_terms'].items()},
        'reference_terms':[{'reference_id':f['reference_id'],'terms':{k:match_text(v) for k,v in f['terms'].items()}} for f in row['reference_terms']]}
    issue=contrast_issue(kind,match_text(selected),match_text(reference),matched,match_text(clause)) if kind else 'No adverse rule'
    # Original safeguards override a matching adverse fragment. Never remove
    # a term-end deadline by normalising "no later than" for route matching.
    if kind=='refund_window' and has(
        r'\b(?:no later than|not later than|by)\b.{0,45}\b(?:expiry|expiration|termination|end of (?:the )?Term)\b',
        selected):
        issue='An explicit term-end upper bound prevents the proposed later-refund scenario.'
    if row['relation']=='tenant_adverse':
        return ('unproven_scenario',issue) if issue else None
    if kind and issue is None:
        return ('misclassified_condition','An observable positive condition contrast was called unchanged or beneficial.')
    return None


def assess_resolved(raw,tasks,clause,packet,housing):
    lookup={t['task_id']:t for t in tasks}; refs={r['evidence_id']:r for r in packet['references']}
    if (not isinstance(raw,dict) or set(raw)!={'comparisons','unassessed_task_ids'}
        or not isinstance(raw['comparisons'],list) or len(raw['comparisons'])>len(tasks)
        or not isinstance(raw['unassessed_task_ids'],list)
        or any(not isinstance(t,str) or t not in lookup for t in raw['unassessed_task_ids'])
        or len(raw['unassessed_task_ids'])!=len(set(raw['unassessed_task_ids']))):
        return {'accepted':[],'issues':[{'code':'malformed_response','detail':'Invalid response structure.'}],'unsettled':set(lookup),'fatal':True}
    accepted=[]; issues=[]; seen=set()
    for row in raw['comparisons']:
        issue=shape_issue(row,lookup,refs)
        if issue:
            issues.append({'code':'malformed_row','detail':issue}); continue
        tid=row['task_id']
        if tid in seen:
            return {'accepted':[],'issues':[{'code':'duplicate_task','detail':'Ambiguous duplicate task.'}],'unsettled':set(lookup),'fatal':True}
        seen.add(tid)
        if row['decision']!='supported' or row['relation']=='uncertain':
            issues.append({'task_id':tid,'code':'model_uncertain','detail':'Independent comparison unsettled.'}); continue
        issue=row_issue(row,lookup[tid],clause,refs,housing)
        if issue: issues.append({'task_id':tid,'code':issue[0],'detail':issue[1]})
        else: accepted.append(row)
    unsettled=set(lookup)-{r['task_id'] for r in accepted}|set(raw['unassessed_task_ids'])
    for tid in set(lookup)-seen: issues.append({'task_id':tid,'code':'missing_task','detail':'Task was not compared.'})
    # Explicitly unassessed means unsettled even if a conflicting supported row
    # is present; never release that row as a settled finding.
    accepted=[r for r in accepted if r['task_id'] not in raw['unassessed_task_ids']]
    return {'accepted':accepted,'issues':issues,'unsettled':unsettled,'fatal':False}


def assess(raw,tasks,clause,packet,housing):
    lookup={t['task_id']:t for t in tasks}
    if (not isinstance(raw,dict) or set(raw)!={'comparisons','unassessed_task_ids'}
            or not isinstance(raw['comparisons'],list) or len(raw['comparisons'])>len(tasks)
            or not isinstance(raw['unassessed_task_ids'],list)
            or any(not isinstance(t,str) or t not in lookup for t in raw['unassessed_task_ids'])
            or len(set(raw['unassessed_task_ids']))!=len(raw['unassessed_task_ids'])):
        return {'accepted':[],'issues':[{'code':'malformed_response','detail':'Invalid response structure.'}],
                'unsettled':set(lookup),'fatal':True}
    entries=catalogue(clause,packet,tasks); rows=[]; errors=[]; seen=set()
    for row in raw['comparisons']:
        tid=row.get('task_id') if isinstance(row,dict) else None
        if not isinstance(tid,str) or tid not in lookup:
            errors.append({'code':'invalid_evidence_selection','detail':'Unknown task'}); continue
        if tid in seen:
            return {'accepted':[],'issues':[{'code':'duplicate_task','detail':'Duplicate task'}],
                    'unsettled':set(lookup),'fatal':True}
        seen.add(tid)
        try: rows.append(resolve_row(row,lookup[tid],clause,packet,entries))
        except ValueError as error:
            errors.append({'task_id':tid,'code':'invalid_evidence_selection','detail':str(error)})
    checked=assess_resolved({'comparisons':rows,'unassessed_task_ids':raw['unassessed_task_ids']},
                            tasks,clause,packet,housing)
    checked['issues']=errors+checked['issues']
    return checked
