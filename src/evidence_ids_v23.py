"""Exact, offset-bound evidence selection; IDs are not semantic proof."""
import hashlib
import re
from src.contract_spans import contract_spans
from src.condition_facts_v21 import FIELDS,SCENARIOS


def context_id(task,clause):
    text=' '.join(contract_spans(clause)[c] for c in task['contract_span_ids'])
    return task['task_id']+':'+hashlib.sha256(text.encode('utf-8')).hexdigest()[:12]


def catalogue(clause,packet,tasks):
    spans=contract_spans(clause); entries={}
    cids={c for t in tasks for c in t['contract_span_ids']}
    rids={r for t in tasks for g in t['required_reference_groups'] for r in g}
    owners=[(c,spans[c],'contract') for c in spans if c in cids]
    owners += [(r['evidence_id'],r['text'],'reference') for r in packet['references'] if r['evidence_id'] in rids]
    for owner,text,kind in owners:
        def add(key,start,end):
            if text[start:end].strip():
                entries[key]={'owner':owner,'kind':kind,'start':start,'end':end,'quote':text[start:end]}
        add(owner,0,len(text))
        # Full originals stay available, including long dependent conditions.
        for n,m in enumerate(re.finditer(r'[^;\n]+(?:[;\n]|$)',text),1):
            start=m.start()
            while start<m.end() and text[start].isspace(): start+=1
            add(f'{owner}.S{n}',start,m.end())
        for n,m in enumerate(re.finditer(r'\b(?:Either party|Security Deposit|Deposit|Landlord|Lessor|Tenant|Lessee)\b',text,re.I),1):
            add(f'{owner}.A{n}',m.start(),m.end())
    return entries


def terms_schema(ids):
    return {'type':'object','additionalProperties':False,'properties':{
        k:{'type':'array','maxItems':3,'items':{'type':'string','enum':ids or ['UNAVAILABLE']}}
        for k in FIELDS},'required':list(FIELDS)}


def resolve_terms(terms,allowed,entries,text,offsets):
    if not isinstance(terms,dict) or set(terms)!=set(FIELDS): raise ValueError('Invalid evidence dimensions')
    resolved={}
    for field,ids in terms.items():
        if (not isinstance(ids,list) or len(ids)>3 or any(not isinstance(i,str) for i in ids)
                or len(set(ids))!=len(ids)): raise ValueError('Invalid evidence selection')
        values=[]
        for eid in ids:
            if eid not in entries or entries[eid]['owner'] not in allowed: raise ValueError('Evidence ID outside task/source')
            e=entries[eid]; base=offsets[e['owner']]
            if text[base+e['start']:base+e['end']]!=e['quote']: raise ValueError('Evidence offset mismatch')
            values.append((base+e['start'],base+e['end']))
        # Multiple IDs restore the enclosing original interval, not a new
        # sentence assembled from disconnected quotes. All intervening
        # qualifications are retained, and full context is independently read.
        resolved[field]=text[min(a for a,b in values):max(b for a,b in values)] if values else ''
    if not resolved['action']: raise ValueError('Observable action evidence required')
    return resolved


def resolve_row(row,task,clause,packet,entries,comparison=True):
    expected={'task_id','contract_terms','reference_terms','context_id'}
    if comparison: expected|={'relation','contrast_kind','scenario','decision'}
    if not isinstance(row,dict) or set(row)!=expected or row['task_id']!=task['task_id']:
        raise ValueError('Malformed evidence row')
    if row['context_id']!=context_id(task,clause): raise ValueError('Wrong bound context')
    spans=contract_spans(clause); offsets={}; chunks=[]; size=0
    for c in task['contract_span_ids']:
        offsets[c]=size; chunks.append(spans[c]); size+=len(spans[c])+1
    text=' '.join(chunks)
    out={'task_id':row['task_id'],'contract_terms':resolve_terms(row['contract_terms'],set(offsets),entries,text,offsets),
         'reference_terms':[]}
    refs={r['evidence_id']:r for r in packet['references']}; seen=set()
    allowed={r for g in task['required_reference_groups'] for r in g}
    if not isinstance(row['reference_terms'],list) or len(row['reference_terms'])>3: raise ValueError('Invalid reference rows')
    for f in row['reference_terms']:
        if not isinstance(f,dict) or set(f)!={'reference_id','terms'}: raise ValueError('Malformed source facts')
        rid=f['reference_id']
        if not isinstance(rid,str) or rid not in refs or rid not in allowed or rid in seen: raise ValueError('Wrong or duplicate source')
        seen.add(rid)
        out['reference_terms'].append({'reference_id':rid,
            'terms':resolve_terms(f['terms'],{rid},entries,refs[rid]['text'],{rid:0})})
    if comparison:
        enums={'relation':{'tenant_adverse','equivalent','tenant_beneficial','uncertain'},
               'decision':{'supported','uncertain'},'contrast_kind':{'none',*SCENARIOS},
               'scenario':{'none',*SCENARIOS.values()}}
        if any(not isinstance(row[k],str) or row[k] not in v for k,v in enums.items()): raise ValueError('Invalid judgment enums')
        out.update({k:row[k] for k in enums})
        # Program-bound coverage, NOT a claim that an acknowledgement proves
        # the model read/understood every condition.
        out['checked_context_ids']=list(task['contract_span_ids'])
    return out


def validated_extraction(raw,tasks,clause,packet):
    entries=catalogue(clause,packet,tasks); lookup={t['task_id']:t for t in tasks}
    accepted=[]; rejected=0; seen=set()
    rows=raw.get('facts',[]) if isinstance(raw,dict) else []
    if not isinstance(rows,list): rows=[]
    for row in rows[:len(tasks)]:
        try:
            tid=row.get('task_id') if isinstance(row,dict) else None
            if tid not in lookup or tid in seen: raise ValueError('Unknown/duplicate extraction')
            fact=resolve_row(row,lookup[tid],clause,packet,entries,False)
        except ValueError: rejected+=1; continue
        accepted.append(fact); seen.add(tid)
    return {'facts':accepted,'rejected_fact_rows':rejected,'unassessed_task_ids':sorted(set(lookup)-seen),
            'notice':'Program-restored original intervals only, not correctness or completeness proof.'}
