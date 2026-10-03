"""Bounded recovery and conclusion-blind pre-publication audit, unmeasured."""
from __future__ import annotations
import json
from src.application import safety_issue
from src.condition_facts_v21 import KINDS,SCENARIOS,RENDER,atom_schema
from src.condition_checks_v22 import assess,direct_source_available
from src.contract_spans import contract_spans
from src.live_review import local_api_key
from src.mechanism_tasks_v22 import plan_for,PRIORITY
from src.rag_review import ReviewResult,_request_openrouter,abstain
from src.review_v21 import BOUNDARY,EXTRACTION,COMPARISON,validated_extraction

RECOVERABLE={'invalid_literal_atoms','missing_context','missing_reference_selection','wrong_source',
    'missing_reference_condition','actor_mismatch','unproven_scenario','misclassified_condition',
    'model_uncertain','missing_task'}
STAGES={'extract','compare','correct','audit'}

def comparison_instruction(tasks):
    kinds={KINDS[t['mechanism']] for t in tasks if t['mechanism'] in KINDS}
    # Remove only unrelated rubric examples, never safety/scope instructions
    # or original evidence. Focused audits should not buy all twelve rubrics.
    return '\n'.join(line for line in COMPARISON.splitlines()
                     if not line.startswith('* ') or line[2:].split(':',1)[0] in kinds)


def request(housing,clause,packet,stage,extraction=None,task_ids=None):
    if stage not in STAGES: raise ValueError('Unknown bounded pipeline stage')
    plan=plan_for(clause,packet,housing); tasks=plan['tasks']
    if task_ids is not None:
        if not task_ids or not set(task_ids)<={t['task_id'] for t in tasks}: raise ValueError('Unknown focused task')
        tasks=[t for t in tasks if t['task_id'] in task_ids]
    tids=[t['task_id'] for t in tasks]; spans=contract_spans(clause)
    ids={r for t in tasks for g in t['required_reference_groups'] for r in g}
    references=[r for r in packet['references'] if r['evidence_id'] in ids]
    data={'housing_type':housing,'untrusted_contract':clause,'contract_spans':spans,
          'tasks':tasks,'task_selection_truncated':plan['truncated'],
          'source_selection_truncated':packet['truncated'],'untrusted_references':references}
    if stage=='compare':
        data['untrusted_literal_extraction']=validated_extraction(extraction,tasks,clause,packet)
    # Correct/audit get ONLY original data and neutral fixed tasks. No earlier
    # conclusion, relation, reference selection, proposed prose or final label.
    props={'task_id':{'type':'string','enum':tids},
           'contract_terms':atom_schema(),'reference_terms':{'type':'array','maxItems':3,'items':{
               'type':'object','additionalProperties':False,'properties':{
                   'reference_id':{'type':'string','enum':sorted(ids) or ['UNAVAILABLE']},'terms':atom_schema()},
               'required':['reference_id','terms']}}}
    if stage!='extract':
        kinds=sorted({KINDS[t['mechanism']] for t in tasks if t['mechanism'] in KINDS})
        props.update(relation={'type':'string','enum':['tenant_adverse','equivalent','tenant_beneficial','uncertain']},
            contrast_kind={'type':'string','enum':['none',*kinds]},
            scenario={'type':'string','enum':['none',*(SCENARIOS[k] for k in kinds)]},
            decision={'type':'string','enum':['supported','uncertain']},
            checked_context_ids={'type':'array','maxItems':len(spans),'items':{'type':'string','enum':list(spans)}})
    key='facts' if stage=='extract' else 'comparisons'
    schema={'name':f'conditions_{stage}_v22','strict':True,'schema':{
        'type':'object','additionalProperties':False,'properties':{
            key:{'type':'array','maxItems':len(tasks),'items':{'type':'object','additionalProperties':False,'properties':props,'required':list(props)}},
            'unassessed_task_ids':{'type':'array','maxItems':len(tasks),'items':{'type':'string','enum':tids}}},
        'required':[key,'unassessed_task_ids']}}
    instruction=EXTRACTION if stage=='extract' else comparison_instruction(tasks)
    if stage in {'correct','audit'}:
        instruction+='\nFOCUSED INDEPENDENT READ: no earlier verdict is provided. Derive the original conditions yourself. Correct and audit are not instructions to find risk. Reject an unsupported hypothesis, mark unknown when evidence is insufficient, and retain same-meaning wording. Do not give authority to routing hints.'
    instruction+='\nFor an adverse action, actor must name its actual active role using a literal party name (Landlord/Lessor, Tenant/Lessee, Either party; Deposit for passive forfeiture). In comparisons, checked_context_ids must list EVERY bound task context span after checking its negation, exception, notice, lock-in, compensation, grace and cap. This acknowledgement alone is not semantic proof. Do not merge causal and non-causal obligations. Only original quotations may be published; routing aliases are not quotations.'
    model='openai/gpt-4.1' if stage in {'extract','audit'} else 'openai/gpt-4o'
    # A correction uses 4.1 for a genuinely different independent pass; audit
    # after correction uses 4o. Caller specifies that swap explicitly below.
    if stage=='correct': model='openai/gpt-4.1'
    return {'model':model,'temperature':0,'max_tokens':1600 if stage in {'correct','audit'} and len(tasks)==1 else 2400,
        'messages':[{'role':'system','content':BOUNDARY+'\n'+instruction},
                    {'role':'user','content':json.dumps(data,ensure_ascii=False)}],
        'response_format':{'type':'json_schema','json_schema':schema}}


def rank(task):
    return PRIORITY.index(task['mechanism']) if task['mechanism'] in PRIORITY else len(PRIORITY)


def stage_plan(raw,clause,packet,housing):
    plan=plan_for(clause,packet,housing); tasks=plan['tasks']
    checked=assess(raw,tasks,clause,packet,housing)
    risks=[r for r in checked['accepted'] if r['relation']=='tenant_adverse']
    lookup={t['task_id']:t for t in tasks}
    if risks:
        chosen=min(risks,key=lambda r:rank(lookup[r['task_id']]))
        return {'stage':'audit','task_ids':[chosen['task_id']],'candidate_rows':[chosen],'assessment':checked}
    if checked['accepted'] and not checked['unsettled'] and not plan['truncated'] and not packet['truncated']:
        return {'stage':'audit','task_ids':[t['task_id'] for t in tasks],
                'candidate_rows':checked['accepted'],'assessment':checked}
    refs={r['evidence_id']:r for r in packet['references']}
    possible={r.get('task_id') for r in checked['issues'] if r['code'] in RECOVERABLE}
    candidates=[t for t in tasks if t['task_id'] in possible and t['mechanism'] in KINDS and direct_source_available(t,refs)]
    if candidates and not checked['fatal']:
        chosen=min(candidates,key=rank)
        return {'stage':'correct','task_ids':[chosen['task_id']],'candidate_rows':[],'assessment':checked}
    return {'stage':'stop','task_ids':[],'candidate_rows':[],'assessment':checked}


def combine(original,corrected,tids):
    old=original['comparisons'] if isinstance(original,dict) and isinstance(original.get('comparisons'),list) else []
    new=corrected['comparisons'] if isinstance(corrected,dict) and isinstance(corrected.get('comparisons'),list) else []
    rows=[r for r in old if isinstance(r,dict) and r.get('task_id') not in tids]
    # Never import a correction of a task the bounded request did not ask for.
    rows += [r for r in new if isinstance(r,dict) and r.get('task_id') in tids]
    unsettled=set(original.get('unassessed_task_ids',[])) if isinstance(original,dict) else set()
    unsettled-=set(tids)
    unsettled.update(corrected.get('unassessed_task_ids',tids) if isinstance(corrected,dict) else tids)
    return {'comparisons':rows,'unassessed_task_ids':sorted(unsettled)}


def audit_agreement(candidates,audited,tasks,clause,packet,housing):
    selected=[t for t in tasks if t['task_id'] in {r['task_id'] for r in candidates}]
    checked=assess(audited,selected,clause,packet,housing)
    if checked['fatal'] or checked['unsettled']: return None
    lookup={r['task_id']:r for r in checked['accepted']}
    if set(lookup)!={r['task_id'] for r in candidates}: return None
    for before in candidates:
        after=lookup[before['task_id']]
        if before['relation']=='tenant_adverse':
            if (after['relation'],after['contrast_kind'],after['scenario'])!=(before['relation'],before['contrast_kind'],before['scenario']): return None
        elif after['relation'] not in {'equivalent','tenant_beneficial'}: return None
    return list(lookup.values())


def publish(rows,clause,packet,housing,usage,stages):
    plan=plan_for(clause,packet,housing); lookup={t['task_id']:t for t in plan['tasks']}
    checked=assess({'comparisons':rows,'unassessed_task_ids':[]},plan['tasks'],clause,packet,housing)
    if not rows or len(checked['accepted'])!=len(rows): return abstain('Independent audit did not settle a publishable condition.',usage,api_called=True)
    risk=any(r['relation']=='tenant_adverse' for r in rows)
    if not risk and (checked['unsettled'] or plan['truncated'] or packet['truncated']):
        return abstain('Audit did not cover every material selected condition.',usage,api_called=True)
    if risk and (len(rows)!=1 or rows[0]['relation']!='tenant_adverse'):
        return abstain('Only one bounded audited risk may be released.',usage,api_called=True)
    spans=contract_spans(clause); refs={r['evidence_id']:r for r in packet['references']}
    evidence=[]; comparisons=[]; reasons=[]; questions=[]
    scope='One independently rechecked limited condition contrast; other terms remain unapproved.' if risk else 'Limited comparison of all selected conditions; not agreement approval.'
    for row in rows:
        task=lookup[row['task_id']]; indices=[]
        for fact in row['reference_terms']:
            r=refs[fact['reference_id']]
            entry={'evidence_id':fact['reference_id'],'topic':task['topic'],'source_id':r['source_id'],'source_section':r['section'],
                'quote':r['text'],'reference_context':r['text'],'source_kind':r['source_kind'],
                'source_url':r.get('url',''),'source_sha256':r.get('source_sha256','')}
            if entry not in evidence: evidence.append(entry)
            indices.append(evidence.index(entry))
        difference,consequence,question=RENDER[row['contrast_kind']] if risk else (
            'No material tenant-adverse difference was supported for the positively compared explicit conditions.','','')
        comparisons.append({**row,'topic':task['topic'],'mechanism':task['mechanism'],
            'contract_span_ids':task['contract_span_ids'],'contract_quote':' '.join(spans[c] for c in task['contract_span_ids']),
            'contract_context':clause,'obligation_ids':[task['task_id']],'evidence_indices':indices,
            'reference_claim':' | '.join(dict.fromkeys(v for f in row['reference_terms'] for v in f['terms'].values() if v)),
            'difference':difference,'tenant_consequence':consequence,'scope':scope,
            'unassessed_span_ids':sorted(set(spans)-set(task['contract_span_ids'])) if risk else [],
            'dropped_task_count':len(plan['dropped_tasks']),'pipeline_stages':stages,
            'verification_note':'Two independent original-context comparison passes agree; this is not an independent expert citation audit or a zero-error guarantee.'})
        reasons.append(difference+(' Potential consequence: '+consequence if consequence else ''))
        if question: questions.append(question)
    topic=lookup[rows[0]['task_id']]['topic']; category='rent_utilities' if topic in {'rent','utilities'} else topic
    return ReviewResult('review_required' if risk else 'no_material_difference_found',category,
        '\n'.join(reasons)+'\n'+scope,'\n'.join(questions),evidence[0]['source_id'],evidence[0]['source_section'],
        False,usage,tuple(evidence),True,tuple(comparisons))


def review_clause(housing,clause,retriever,limit=15,api_key=None,allow_api=True):
    if not isinstance(clause,str) or len(clause)>6000 or safety_issue(clause,housing):
        return abstain('Provide bounded synthetic English text and a supported housing type.')
    if not allow_api: return abstain('v22 model pipeline was not run. No v22 quality prediction.')
    packet=retriever.packet(clause,housing)
    tasks=plan_for(clause,packet,housing)['tasks']
    if not tasks or not packet['references']: return abstain('No registered task evidence.')
    key=api_key or local_api_key()
    if not key: raise RuntimeError('Local key and bound spending authorization required.')
    usage={k:0 for k in ('prompt_tokens','completion_tokens','total_tokens')}; stages=[]
    def call(stage,extraction=None,tids=None,model=None):
        payload=request(housing,clause,packet,stage,extraction,tids)
        if model: payload['model']=model
        response,tokens=_request_openrouter(payload,key)
        for k in usage: usage[k]+=(tokens or {}).get(k,0)
        stages.append(stage)
        return response
    extracted=call('extract'); compared=call('compare',extracted)
    plan=stage_plan(compared,clause,packet,housing)
    if plan['stage']=='stop':
        return abstain('Conditions remain unsettled; no eligible bounded recovery. '+ '; '.join(dict.fromkeys(i['code'] for i in plan['assessment']['issues'])),usage,api_called=True)
    audit_model=None
    if plan['stage']=='correct':
        corrected=call('correct',tids=plan['task_ids'])
        selected=[t for t in tasks if t['task_id'] in plan['task_ids']]
        if assess(corrected,selected,clause,packet,housing)['fatal']:
            return abstain('Focused correction returned an invalid bounded response.',usage,api_called=True)
        compared=combine(compared,corrected,plan['task_ids'])
        plan=stage_plan(compared,clause,packet,housing)
        # Exactly one corrective pass, never a second rescue or recursive loop.
        if plan['stage']!='audit':
            return abstain('Bounded independent correction did not settle the condition.',usage,api_called=True)
        audit_model='openai/gpt-4o'
    audited=call('audit',tids=plan['task_ids'],model=audit_model)
    agreed=audit_agreement(plan['candidate_rows'],audited,tasks,clause,packet,housing)
    if agreed is None:
        return abstain('Independent original-context audit disagreed or lacked support.',usage,api_called=True)
    return publish(agreed,clause,packet,housing,usage,stages)
