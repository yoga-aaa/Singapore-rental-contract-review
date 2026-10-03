"""Unmeasured v19 candidate: explicit mechanisms and claim-scoped release gates.

Same two models and sources as v18. No labels/test IDs in predictor code.
No new paid run is implied by a replay or by passing deterministic tests.
"""
from __future__ import annotations
import copy
import json
import re
from dataclasses import replace

from src.comparison_checks import explicit_waiver
from src.contract_spans import contract_spans
from src.live_review import local_api_key, review_clause as legacy_review
from src.rag_review import _request_openrouter, abstain
from src.review_v18 import build_request as v18_request, finalize as v18_finalize, shape_issue

MECHANISMS=['refund_trigger','deposit_deduction_process','deposit_forfeiture_amount',
            'repair_allocation','repair_completion_deadline','repair_causation','repair_self_help',
            'landlord_exit_trigger','exit_evidence_acceptance','tenant_break_clause',
            'current_term_rent_review','holdover_charge','late_payment_charge',
            'guest_documentation','occupancy','subletting_permission','utilities',
            'expert_evidence_and_fees','dispute_route','stamp_duty','other']

INSTRUCTIONS="""
# v19 comparison workflow
Identify actor, action, object, trigger, deadline/rate, prerequisite and exception for each obligation. Choose the named mechanism. Compare the two tuples before choosing a relation. Report short observable facts, not hidden reasoning. Use the packet's coverage hints to FIND references, not as support verdicts.
For reciprocal early-exit rights, examine the landlord's and tenant's rights separately. A tenant exit option does not erase the landlord-triggered loss of a compliant tenant's remaining term. Conditional quiet enjoyment is a positive comparator, not proof that all other termination grounds are forbidden. Preserve lock-in, notice and relocation compensation where present.
Refund 'within N days after handover' and refund 'when term expires/is terminated' have different triggers/windows. A stated later window is not automatically beneficial just because it is clearer. End-of-tenancy key-return obligations are context; do not assert a statutory zero-day deadline.
Starting/proceeding with repair within a deadline is not completing/carrying out repair within that deadline. Keep the reference's reasonable-time completion condition separate. A fixed contractual carry-out trigger may need clarification even if notice is provided.
Breakdown caused by failure to maintain is not the same as a requirement to prove servicing compliance even when servicing did not cause the fault. A servicing duty alone does not prove replacement-cost allocation. Compare causal liability with the additional formal condition.
Documentary evidence of an objective relocation/employment event is not automatically identical to evidence additionally acceptable to the landlord. Inspect the acceptance standard and any reasonable/objective limitation. A one-use break right is not itself a demonstrated detriment when its exercise ends the tenancy.
Compare current-term rent review with agreed current-term rent and separately any mutually agreed extension-rate provision. Do not call an extension clause an exhaustive ban on all revisions. Notice and a penalty-free exit do not by themselves preserve staying at the old rent.
Post-expiry double rent is not late-payment interest. Match holdover with end-of-tenancy/agreed-rent clauses; match overdue-payment charges with annual late interest. Preserve weekly/annual units and cumulative caps.
# Release prohibitions
An omitted pre-deduction safeguard is NOT an express waiver. Never infer 'immediate', 'without notice', 'no cure', or loss of rectification from 'may deduct', 'replenish', or 'material breach'. Full forfeiture can be compared with reasonable remedial deduction AMOUNT without inventing a notice waiver.
Ordinary guests are not established named occupiers: do not invent a guest threshold/ID standard from occupier duties. HDB owner duties do not authorise a tenant to further rent rooms. If an official paragraph prohibits further tenant rental, read that prohibition before suggesting registration cures it.
Preserve reference exceptions, including an agreed remedy period. Silence cannot support equivalence, benefit, extra fees or an exhaustive negative rule. Do not transfer a condition from a different mechanism. Release only supported atomic findings; unsupported neighbours must be unassessed, not bundled into a risk reason or a pass.
The verifier must independently reselect evidence and recheck the tuples, especially trigger, causation and deadline; do not accept a comparison because its general topic matches. Return the schema only.
"""


def build_request(housing,clause,packet,draft=None):
    request=v18_request(housing,clause,packet,draft)
    request['messages'][0]['content']+='\n'+INSTRUCTIONS
    schema=request['response_format']['json_schema']
    schema['name']='atomic_verification_v19' if draft is not None else 'atomic_comparison_v19'
    item=schema['schema']['properties']['comparisons']['items']
    item['properties']['mechanism']={'type':'string','enum':MECHANISMS}
    item['required'].append('mechanism')
    return request


def normalized(raw):
    if not isinstance(raw,dict):
        return raw
    result=copy.deepcopy(raw)
    rows=result.get('comparisons',[])
    if not isinstance(rows,list):
        return result
    for row in rows:
        if isinstance(row,dict):
            row.pop('mechanism',None)
    return result


def response_issue(raw,clause,packet,verifier):
    issue=shape_issue(normalized(raw),clause,packet,verifier)
    if issue:
        return issue
    if any(row.get('mechanism') not in MECHANISMS for row in raw['comparisons']):
        return 'Unknown or missing factual comparison mechanism.'
    return None


def tenant_rental_permission(text):
    """A positive tenant permission, not 'may not'/'not permitted'."""
    for match in re.finditer(r'\btenant\w*\b[^.;]{0,55}\b(?:may|can|allowed|permitted|authorised|authorized)\b[^.;]{0,55}\b(?:sublet|sub.let|rent out)\w*\b',text,re.I):
        if not re.search(r'\b(?:not|never|no|cannot)\b',match.group(0),re.I):
            return True
    return False


def claim_issue(row,clause,refs):
    spans=contract_spans(clause)
    selected=' '.join(spans[c] for c in row['contract_span_ids'])
    prose=' '.join(row[k] for k in ('reference_claim','difference','tenant_consequence','check_note','question'))
    chosen=[refs[r] for r in row['reference_ids']]
    quote=' '.join(r['text'] for r in chosen)
    mechanism=row['mechanism']
    if row['relation']=='tenant_adverse' and mechanism=='other':
        return 'An unspecified adverse mechanism cannot pass the strict release gate.'
    if row['relation']=='tenant_adverse':
        for protection,pattern in [
            ('notice',r'\b(?:without (?:prior |written )*(?:notice|warning)|no (?:prior |written )*notice)\b'),
            ('cure',r'\b(?:no (?:pre.deduction )*cure|without (?:a |any |prior |pre.deduction )*(?:cure|chance to (?:cure|remedy)|opportunity to (?:cure|remedy|fix)))\b'),
            ('cure',r'\b(?:removes?|waives?|los[est]+)\b.{0,30}\b(?:rectification|cure|remedy|opportunity)\b')]:
            if re.search(pattern,prose,re.I) and not explicit_waiver(protection,selected):
                return 'An unexpressed safeguard waiver was inferred.'
        if (mechanism=='deposit_deduction_process' and re.search(r'\bimmediat\w*\b',prose,re.I)
                and not re.search(r'\bimmediat\w*\b.{0,50}\b(?:deduct|recover)|\b(?:deduct|recover)\w*\b.{0,50}\bimmediat\w*\b',selected,re.I)):
            return 'Immediate deduction is not expressly stated in the selected contract.'
    if ((mechanism=='guest_documentation' or row['topic']=='occupancy_subletting')
            and (re.search(r'\bguests?\b',prose,re.I)
                 or (re.search(r'\bguests?\b',selected,re.I)
                     and re.search(r'\b(?:passport|identit\w*|notify|notification|consecutive days)\b',selected,re.I)))
            and not re.search(r'\bguests?\b',quote,re.I)):
        return 'Occupier duties do not settle ordinary guest documentation or stay thresholds.'
    hdb_policy=any(r.get('source_kind')=='housing_policy_background' and r.get('source_id','').startswith('HDB_') for r in chosen)
    if hdb_policy:
        if tenant_rental_permission(prose) and not any(tenant_rental_permission(r['text']) for r in chosen):
            return 'Owner rental permissions were transferred to a tenant without tenant-specific permission evidence.'
        if (re.search(r'\btenant\w*\b',selected,re.I) and re.search(r'\b(?:sublet|sub.let|rent out)\w*\b',selected,re.I)
                and re.search(r'\bowners?\b',row['reference_claim'],re.I)
                and not re.search(r'\btenants?\s+(?:further\s+)?(?:must|shall|may|can|cannot|will|agree\w*|does?|are|is)\b',row['reference_claim'],re.I)):
            return 'Owner-only duties do not settle the selected tenant subletting obligation.'
    if (mechanism=='expert_evidence_and_fees' and re.search(r'\b(?:fee|cost)\w*\b',selected,re.I)
            and not any(re.search(r'\b(?:expert|surveyor|report)\w*\b',r['text'],re.I)
                        and re.search(r'\b(?:fee|cost)\w*\b',r['text'],re.I) for r in chosen)):
        return 'A dispute route does not establish expert/report fee allocation.'
    if (re.search(r'\bmaterial breach\b',selected,re.I) and not re.search(r'\bterminat\w*\b',selected,re.I)
            and re.search(r'\bimmediate termination\b|\bremoves?.{0,30}rectification\b',prose,re.I)):
        return 'Material breach was converted to an unstated termination procedure.'
    if mechanism=='holdover_charge' and not any(r.get('clause_id') in {'19.1','20.1'} for r in chosen):
        return 'A holdover charge needs end-of-tenancy evidence, not late interest.'
    if mechanism=='late_payment_charge' and not any(r.get('clause_id') in {'7.4','8.4'} for r in chosen):
        return 'A late-payment rate lacks matching default-interest evidence.'
    if mechanism=='current_term_rent_review' and not any(r.get('clause_id') in {'1.3','1.4','ITEM8'} for r in chosen):
        return 'A current-term rent change needs positive agreed-rent evidence.'
    if mechanism=='deposit_forfeiture_amount' and not any(r.get('clause_id')=='2.2' for r in chosen):
        return 'A forfeiture amount needs the deposit-settlement comparator.'
    if mechanism=='repair_self_help' and not any(r.get('clause_id') in {'4.7','4.9'} for r in chosen):
        return 'Self-help repair conditions need the relevant repair process.'
    if mechanism=='repair_completion_deadline' and not any(r.get('clause_id')=='4.7' for r in chosen):
        return 'Repair starting/completion deadlines need their matching process clause.'
    if (mechanism=='repair_completion_deadline' and row['relation'] in {'equivalent','tenant_beneficial'}
            and re.search(r'\bcarry out\b.{0,120}\bwithin\b',selected,re.I)
            and re.search(r'\breasonable time\b',quote,re.I)
            and not re.search(r'\b(?:start|commence|proceed)\w*\b',selected,re.I)):
        return 'A carry-out deadline was equated with separate start/completion conditions.'
    if mechanism=='repair_causation' and not any(r.get('clause_id')=='4.5' for r in chosen):
        return 'A servicing duty is not repair-causation evidence.'
    if (mechanism=='repair_causation' and row['relation'] in {'equivalent','tenant_beneficial'}
            and re.search(r'\bnot attributable\b|\bnot (?:due to|caused by)\b',selected,re.I)
            and re.search(r'\bprovided that\b.{0,80}\b(?:complied|servic\w*|maintain\w*)\b',selected,re.I)):
        return 'A separate compliance condition was equated with breakdown causation.'
    if mechanism=='exit_evidence_acceptance' and not any(r.get('clause_id') in {'ITEM14','ITEM16'} for r in chosen):
        return 'Exit evidence acceptance needs the optional break-clause text.'
    if (mechanism=='exit_evidence_acceptance' and row['relation']=='equivalent'
            and re.search(r'\b(?:acceptable|satisfactory) to the Landlord\b',selected,re.I)
            and not re.search(r'\b(?:objective|reasonabl\w*|authenticity)\b',selected,re.I)):
        return 'Landlord evidence acceptance was equated with an objective-document requirement.'
    if (mechanism=='exit_evidence_acceptance' and row['relation']=='tenant_adverse'
            and re.search(r'\b(?:objective|reasonabl\w*|authenticity)\b',selected,re.I)
            and re.search(r'\b(?:unrestricted|unlimited|absolute|sole|arbitrary)\b.{0,40}\b(?:discretion|veto|approval|acceptance)\b',prose,re.I)
            and not re.search(r'\b(?:sole|absolute|unrestricted)\b.{0,20}\bdiscretion\b',selected,re.I)):
        return 'A qualified evidence check was converted into an unrestricted landlord veto.'
    if mechanism=='refund_trigger' and not any(r.get('clause_id')=='2.2' for r in chosen):
        return 'Refund timing was compared with a different process.'
    if (mechanism=='landlord_exit_trigger'
            and not any('HOLD AND ENJOY' in r['text'].upper() for r in chosen)):
        return 'A default clause alone is not an exhaustive comparator for a compliant tenant early-exit trigger.'
    if (mechanism=='refund_trigger' and row['relation']=='tenant_beneficial'
            and re.search(r'\bwithin\b.{0,35}\bdays?\b.{0,25}\bafter\b',selected,re.I)
            and re.search(r'\bwhen the Term expires or is terminated\b',quote,re.I)
            and not re.search(r'\b(?:before|earlier|immediate|same day)\b',selected,re.I)):
        return 'A clearer later refund window was treated as automatically beneficial.'
    if (re.search(r'\b(?:fourteen|14)\b.{0,15}\b(?:day|cure|remedy)\w*\b',row['reference_claim'],re.I)
            and re.search(r'\bperiod as may be agreed\b',quote,re.I)
            and not re.search(r'\b(?:agreed|agree|alternative|unless)\b',row['reference_claim'],re.I)):
        return 'The reference-side agreed-period exception was omitted.'
    if (re.search(r'\b(?:does not|not|no)\b.{0,35}\b(?:consent to sharing|guest threshold|report fee)\b',row['reference_claim'],re.I)
            and not re.search(r'\b(?:consent to sharing|guest threshold|report fee)\b',quote,re.I)):
        return 'A negative reference rule was inferred from silence.'
    return None


def finalize(raw,clause,packet,housing,usage=None):
    issue=response_issue(raw,clause,packet,True)
    if issue:
        return abstain(issue,usage,api_called=True)
    refs={r['evidence_id']:r for r in packet['references']}
    filtered=normalized(raw)
    rejected=[]
    for original,row in zip(raw['comparisons'],filtered['comparisons']):
        if original['verdict']=='supported' and original['relation']!='uncertain':
            error=claim_issue(original,clause,refs)
            if error:
                row['verdict']='unsupported'
                rejected.append(error)
    result=v18_finalize(filtered,clause,packet,housing,usage)
    if result.abstained and rejected:
        return replace(result,reason=result.reason+' Release checks: '+'; '.join(dict.fromkeys(rejected)))
    return result


def review_clause(housing,clause,retriever,limit=15,api_key=None,allow_api=True):
    if housing not in {'HDB','Private Residential'} or not clause.strip() or len(clause)>6000:
        return abstain('Provide a supported housing type and a bounded English clause.')
    packet=retriever.packet(clause,housing)
    if not packet['references'] or not packet['topics']:
        return abstain('No relevant registered evidence was found.')
    if not allow_api:
        return legacy_review(housing,clause,retriever.legacy,limit=4,allow_api=False)
    key=api_key or local_api_key()
    if not key:
        raise RuntimeError('Local credential and separate spending authorization required.')
    draft,first=_request_openrouter(build_request(housing,clause,packet),key)
    issue=response_issue(draft,clause,packet,False)
    if issue:
        return abstain(issue,first,api_called=True)
    verified,second=_request_openrouter(build_request(housing,clause,packet,draft),key)
    usage={k:(first or {}).get(k,0)+(second or {}).get(k,0) for k in
           ('prompt_tokens','completion_tokens','total_tokens')}
    return finalize(verified,clause,packet,housing,usage)
