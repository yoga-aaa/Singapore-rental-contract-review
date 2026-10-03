"""Observable literal condition atoms and bounded contrast rules, never gold labels.

Atoms are substrings of their bound original source. They are NOT sufficient
semantic proof: the independent comparison must re-read full paragraphs too.
Release rules require positive evidence on both sides, never source silence.
"""
from __future__ import annotations
import re
from src.comparison_checks import explicit_waiver
from src.contract_spans import contract_spans

FIELDS=('actor','action','trigger','deadline_rate','payer','prerequisite','exception')
KINDS={
    'refund_trigger':'refund_window',
    'deposit_forfeiture_amount':'forfeiture_amount',
    'deposit_deduction_process':'express_safeguard_waiver',
    'damage_after_handover':'later_damage_claim',
    'repair_completion_deadline':'repair_deadline_ambiguity',
    'repair_causation':'noncausal_compliance_condition',
    'landlord_exit_trigger':'compliant_tenant_exit',
    'exit_evidence_acceptance':'additional_evidence_acceptance',
    'current_term_rent_review':'original_term_rent_revision',
    'holdover_charge':'holdover_multiplier',
    'late_payment_charge':'late_rate_difference',
    'subletting_permission':'changed_subletting_permission',
}
SCENARIOS={
    'refund_window':'term_ended_handover_done_no_deductions',
    'forfeiture_amount':'breach_remedy_smaller_than_deposit',
    'express_safeguard_waiver':'deduction_with_express_waiver',
    'later_damage_claim':'damage_found_after_joint_handover',
    'repair_deadline_ambiguity':'repair_started_in_time_finishes_reasonably_later',
    'noncausal_compliance_condition':'fault_not_caused_by_servicing_lapse',
    'compliant_tenant_exit':'tenant_compliant_remaining_term',
    'additional_evidence_acceptance':'qualifying_event_documented',
    'original_term_rent_revision':'revision_during_original_term',
    'holdover_multiplier':'occupation_after_term_ends',
    'late_rate_difference':'short_overdue_period_before_cap',
    'changed_subletting_permission':'tenant_sharing_or_subletting',
}


def atom_schema():
    return {'type':'object','additionalProperties':False,
            'properties':{k:{'type':'string','maxLength':160} for k in FIELDS},
            'required':list(FIELDS)}


def atoms_issue(atoms,text):
    if not isinstance(atoms,dict) or set(atoms)!=set(FIELDS):
        return 'Invalid condition dimensions.'
    for value in atoms.values():
        if not isinstance(value,str) or len(value)>160 or (value and value not in text):
            return 'Condition atoms must be exact bound substrings, or empty for unknown.'
    if not atoms['action']:
        return 'An observable action is required.'
    return None


def task_issue(row,task,clause,refs,housing):
    spans=contract_spans(clause)
    selected=' '.join(spans[c] for c in task['contract_span_ids'])
    issue=atoms_issue(row['contract_terms'],selected)
    if issue: return issue
    chosen={f['reference_id'] for f in row['reference_terms']}
    groups=task['required_reference_groups']
    if not chosen or not groups or any(not chosen.intersection(g) for g in groups):
        return 'A required positive mechanism reference is missing.'
    if not chosen <= {rid for g in groups for rid in g}:
        return 'A neighboring reference cannot settle this mechanism.'
    fact_text=[]
    for fact in row['reference_terms']:
        ref=refs[fact['reference_id']]
        if ref['housing_type'] not in {housing,'Both'}: return 'Wrong housing scope.'
        issue=atoms_issue(fact['terms'],ref['text'])
        if issue: return issue
        fact_text.extend(fact['terms'].values())
    reference_atoms=' '.join(fact_text)
    if any(t.casefold() not in reference_atoms.casefold() for t in task['required_fact_terms']):
        return 'A material reference condition was not extracted.'
    # Exact atom binding is not a meaning check. Require a matching reference
    # mechanism even for passes; named occupiers/mediation do not settle guests/fees.
    reference_text=' '.join(refs[r]['text'] for r in chosen)
    if task['mechanism']=='expert_evidence_and_fees' and not (
            has(r'\b(?:expert|surveyor|report)\w*\b',reference_text)
            and has(r'\b(?:fee|cost)\w*\b',reference_text)):
        return 'Expert fees lack direct expert-fee comparison evidence.'
    if task['mechanism']=='guest_documentation' and not has(r'\bguests?\b',reference_text):
        return 'Named occupiers do not establish ordinary guest rules.'
    if task['mechanism']=='other': return 'No registered mechanism for this material span.'
    if row['relation']=='tenant_adverse':
        kind=KINDS.get(task['mechanism'])
        if not kind or row['contrast_kind']!=kind or row['scenario']!=SCENARIOS[kind]:
            return 'The adverse comparison has no matching bounded contrast and scenario.'
        return contrast_issue(kind,selected,reference_text,row,clause)
    if row['contrast_kind']!='none' or row['scenario']!='none':
        return 'A settled non-adverse task cannot carry an adverse scenario.'
    # Reject plainly unresolved trigger contrasts, rather than publishing a
    # confident pass. A rejection never automatically becomes a risk label.
    candidate=KINDS.get(task['mechanism'])
    if candidate and contrast_issue(candidate,selected,reference_text,row,clause) is None:
        return 'An observable condition contrast was equated with unchanged meaning.'
    return None


def has(pattern,text):
    return re.search(pattern,text,re.I|re.S) is not None


def ordered_atoms(atoms,text):
    """Restore quote order, not schema field order (trigger can precede rate)."""
    return ' '.join(v for v in sorted(set(atoms.values())-{''},key=text.find))


def contrast_issue(kind,contract,reference,row,whole_clause):
    """Necessary positive conditions, not a standalone risk classifier.

    Both the independent model's supported decision and these checks are
    required. Full original context is retained in the published comparison.
    """
    c=ordered_atoms(row['contract_terms'],contract)
    # Each original is independently bound. Preserve field quote order within
    # it, but do not pretend that atoms from different references are one sentence.
    r=' '.join(ordered_atoms(f['terms'],reference) for f in row['reference_terms'])
    def require(ok,message): return None if ok else message
    if kind=='refund_window':
        return require(has(r'\b(?:refund|return|repay)\w*\b',c)
            and has(r'\bwithin\b.{0,45}\bdays?\b.{0,35}\bafter\b',c)
            and has(r'\b(?:handover|vacant possession|vacat\w*)\b',c)
            and has(r'\b(?:refund|return)\w*\b',r)
            and has(r'\bwhen\b.{0,35}\bTerm\b.{0,35}\b(?:expir\w*|terminat\w*)\b',r)
            and not has(r'\b(?:same day|immediately|earlier|before)\b',c),
            'Refund comparison requires an explicit later window and a term-end comparator.')
    if kind=='forfeiture_amount':
        return require(has(r'\bdeposit\b',c) and has(r'\bforfeit\w*\b',c)
            and has(r'\breasonable\b',r) and has(r'\b(?:breach|remedy)\b',r)
            and not has(r'\b(?:not|never|no)\b.{0,25}\bforfeit\w*\b',contract)
            and not has(r'\b(?:only|limited to|reasonable (?:amount|cost)|actual loss)\b.{0,45}\bforfeit\w*\b|\bforfeit\w*\b.{0,45}\b(?:only|reasonable (?:amount|cost)|actual loss)\b',contract),
            'Forfeiture amount must concern the deposit itself, not an expressly limited reasonable sum.')
    if kind=='repair_deadline_ambiguity':
        return require(has(r'\b(?:carry out|complete)\b.{0,140}\bwithin\b',c)
            and has(r'\b(?:cost|recover)\w*\b',contract)
            and has(r'\bproceed\b',r) and has(r'\breasonable time\b',r)
            and not has(r'\b(?:start|commence|proceed)\w*\b.{0,50}\bwithin\b',contract),
            'Repair deadline requires a cost trigger distinct from starting and reasonable-time completion.')
    if kind=='noncausal_compliance_condition':
        return require(has(r'\bnot (?:attributable|due|caused)\b',c)
            and has(r'\bprovided that\b.{0,100}\b(?:complied|servic\w*|maintain\w*)\b',c)
            and has(r'\bLandlord\b',c) and has(r'\b(?:bear|cost|pay)\w*\b',c)
            and has(r'\bLandlord\b',r) and has(r'\b(?:breakdown|repair|replacement)\b',r)
            and has(r'\bdue to\b.{0,60}\b(?:negligence|maintenance)\b',r),
            'Formal compliance must add a condition to landlord payment for a non-causal fault.')
    if kind=='compliant_tenant_exit':
        return require(has(r'\b(?:Landlord|Either party)\b.{0,70}\b(?:may|can|entitled)\b.{0,30}\bterminat\w*\b',c)
            and has(r'\b(?:before.{0,30}expir\w*|own (?:use|occupation)|sale|remaining Term|ceases? to reside)\b',contract)
            and has(r'\bHOLD AND ENJOY\b',r) and has(r'\bduring the Term\b',r)
            and has(r'\b(?:pay|perform|observe)\w*\b',r)
            and not default_only_exit(contract)
            and not has(r'\bonly (?:if|where|when)\b.{0,90}\b(?:breach|default|unpaid)\b',contract),
            'Landlord exit needs a trigger applying to a compliant tenant, not tenant-default termination.')
    if kind=='original_term_rent_revision':
        return require(has(r'\brent\b',c) and has(r'\b(?:revis\w*|review|increase|adjust\w*)\b',c)
            and has(r'\b(?:during the Term|after the first|remaining|original term)\b',whole_clause)
            and not has(r'\bonly\b.{0,45}\b(?:renewal|extension)\b',contract)
            and has(r'\brent\b',r) and has(r'\b(?:agreed|ITEM 8|ITEM8|monthly)\b',r),
            'Rent revision needs an original-term change and positive agreed-rent evidence.')
    if kind=='holdover_multiplier':
        return require(has(r'\bdouble\b.{0,45}\brent\b',c)
            and has(r'\b(?:expir|terminat|end)\w*\b',c)
            and has(r'\b(?:perform|continue|obligations)\w*\b',r)
            and has(r'\brent\b',r) and has(r'\b(?:ITEM 8|agreed|monthly)\b',r),
            'Holdover needs the multiplier, continuing end obligations and agreed-rent baseline.')
    if kind=='additional_evidence_acceptance':
        return require(has(r'\b(?:acceptable|satisfactory) to the Landlord\b',c)
            and has(r'\bdocumentary evidence\b',r)
            and not has(r'\b(?:reasonable|objective|authenticity)\b',contract),
            'Evidence acceptance must be an added condition, not an objective authenticity check.')
    if kind=='later_damage_claim':
        return require(has(r'\b(?:damage|defect)\w*\b',c)
            and has(r'\b(?:after|subsequen\w*|later)\b.{0,90}\b(?:handover|inspection|refund)\b|\b(?:handover|refund)\b.{0,90}\b(?:subsequen\w*|later)\b',contract)
            and has(r'\bjoint inspection\b',r) and has(r'\bascertain\w*\b',r),
            'Later damage claims need positive joint-inspection ascertainment evidence.')
    if kind=='late_rate_difference':
        # Rate units must be explicit. Words/figures are read from source, not
        # a fabricated annualisation. Numerical comparison supports short-delay
        # scenarios only, not all durations beyond a contractual total cap.
        weekly=rate(c,r'(?:per|each|a)\s+week|weekly')
        annual=rate(r,r'per\s+annum|per\s+year|annual')
        cap=late_cap(contract)
        grace=grace_days(contract)
        return require(weekly is not None and annual is not None and grace is not None
            and weekly>annual*(grace+7)/365
            and (cap is None and not has(r'\b(?:cap\w*|not exceed|maximum)\b',contract)
                 or cap is not None and cap>weekly)
            and has(r'\b(?:late|overdue|unpaid|days)\b',contract),
            'A short-delay higher charge must remain possible with the actual grace period and cap.')
    if kind=='express_safeguard_waiver':
        return require((explicit_waiver('notice',contract) or explicit_waiver('cure',contract))
            and has(r'\bwritten notice\b',r) and has(r'\b(?:remedy|breach)\b',r),
            'Omitted wording is not an express waiver of notice or remedy.')
    if kind=='changed_subletting_permission':
        # Direct consent/prohibition only. No owner permission transfers and no
        # unstated immediate termination or procedural claim is rendered.
        prohib=r'\b(?:shall not|must not|may not|not permitted|cannot)\b.{0,70}\b(?:sublet|sub.let|share|assign)\w*\b'
        permit=r'\b(?:prior written consent|written consent)\b'
        return require(has(prohib,c) and has(permit,r) and has(r'\bTenant\b',r)
            and not has(r'\b(?:without|unless)\b.{0,30}\b(?:written consent|consent in writing)\b',contract),
            'Subletting needs a direct tenant consent-versus-prohibition contrast.')
    return 'Unknown contrast type.'


def rate(text,units):
    match=re.search(r'(\d+(?:\.\d+)?)\s*%(?:\s*\))?[^%.;]{0,100}?(?:'+units+r')',text,re.I)
    if match: return float(match.group(1))
    match=re.search(r'(one|two|five|ten)\s*(?:\(\s*(\d+(?:\.\d+)?)\s*%?\s*\))?\s*(?:per cent|percent|%)\s*(?:'+units+r')',text,re.I)
    if match: return float(match.group(2) or {'one':1,'two':2,'five':5,'ten':10}[match.group(1).lower()])
    return None


def default_only_exit(text):
    for sentence in re.split(r'[.;]',text):
        if (has(r'\b(?:Landlord|Either party)\b.{0,70}\b(?:may|can|entitled)\b.{0,30}\bterminat\w*\b',sentence)
                and has(r'\bTenant(?:\W+s)?\b.{0,40}\b(?:default|breach|unpaid|fails? to pay)\b',sentence)
                and not has(r'\b(?:regardless of|without)\b.{0,30}\b(?:default|breach)\b',sentence)):
            return True
    return False


def late_cap(text):
    match=re.search(r'\b(?:cap\w*\s*(?:at|of|to)?|not exceed|maximum(?: of)?)\b[^%.;]{0,65}?(\d+(?:\.\d+)?)\s*%',text,re.I)
    return float(match.group(1)) if match else None


def grace_days(text):
    match=re.search(r'\b(?:unpaid|overdue|late)\b.{0,50}?\b(\d+|one|two|three|five|seven|ten|fourteen|thirty)\b\s*(?:\(\s*(\d+)\s*\))?\s*days?',text,re.I)
    if match:
        value=match.group(2) or match.group(1).lower()
        return int(value) if value.isdigit() else {'one':1,'two':2,'three':3,'five':5,'seven':7,'ten':10,'fourteen':14,'thirty':30}[value]
    return None if has(r'\b(?:grace|days)\b',text) else 0


RENDER={
    'refund_window':('The contract allows a stated post-handover refund window; the reference links refund of the deposit balance to expiry or termination.',
        'If the term has ended and handover is complete with no deductions, receipt can be later under the contractual window. This is a template comparison, not a statutory zero-day deadline.',
        'Can the refund event and latest payment date be clarified, including the effect of any justified deductions?'),
    'forfeiture_amount':('The contract provides forfeiture of the deposit for its stated trigger; the reference permits an amount reasonable to remedy the breach.',
        'Where the reasonable remedy amount is smaller than the deposit, the contractual forfeiture can expose the tenant to a larger loss, subject to the quoted exceptions. No notice or cure waiver is inferred.',
        'Can deposit retention be tied to the reasonable remedy amount rather than forfeiture of the deposit?'),
    'repair_deadline_ambiguity':('The contractual carry-out deadline is linked to recovery of repair costs. The reference distinguishes proceeding with repairs by the stated deadline from carrying them out within a reasonable time.',
        'If repairs start on time but reasonably finish later, the contractual cost trigger needs clarification. Carry out may mean completion; this is a material ambiguity, not a categorical assertion that completion is required.',
        'Does carry out mean starting or completing repairs, and how is reasonable completion time treated?'),
    'noncausal_compliance_condition':('The contract additionally conditions landlord replacement payment on servicing compliance even where the replacement need is not attributable to the servicing failure. The reference links its landlord-payment exception to a fault due to tenant negligence or non-maintenance.',
        'For a non-causal fault and a separate servicing lapse, the contractual assurance of landlord payment can be lost. This does not establish that the tenant automatically pays all replacement costs.',
        'Who pays where servicing compliance is incomplete but did not cause the replacement need?'),
    'compliant_tenant_exit':('The contract grants a landlord early-exit trigger. The reference positively provides quiet enjoyment during the term where the tenant pays and performs their obligations.',
        'A compliant tenant can lose the remaining term if that contractual trigger is exercised, subject to the quoted notice, lock-in and compensation conditions. Reciprocal tenant exit does not remove landlord-triggered relocation; the reference is not an exhaustive prohibition of termination grounds.',
        'Can the landlord-triggered loss of the remaining term and its notice or compensation protections be clarified?'),
    'original_term_rent_revision':('The contract permits rent revision during the original term; the reference identifies the rent agreed for that term.',
        'When the quoted revision conditions apply, staying may require the revised rent. The full initial-period, notice and exit protections remain relevant; an exit option does not preserve staying at the previous rent.',
        'Can original-term rent changes require mutual agreement, separately from any renewal rent?'),
    'holdover_multiplier':('The contract expressly applies double rent after the term ends. The references identify the agreed rent and continuing obligations pending handover.',
        'Continued occupation after the term ends can attract the express multiplier rather than the agreed-rent baseline. This comparison does not establish a legal ban on holdover charges.',
        'Can the post-term rent multiplier and its start and end conditions be clarified?'),
    'additional_evidence_acceptance':('The contract adds landlord acceptance of qualifying documentary evidence to the break condition; the reference specifies documentary evidence of the qualifying event.',
        'Providing documents of the qualifying event may not alone satisfy the added acceptance condition. This is not a claim of unlimited discretion or a general unconditional tenant exit right.',
        'Can evidence acceptance be tied to objective proof of the qualifying event?'),
    'later_damage_claim':('The contract provides later damage claims following handover or refund; the reference ties the stated damage liability to ascertainment during joint inspection.',
        'The tenant can face a later claim under the quoted conditions rather than only the inspection-linked assessment. The contractual notice, time limit and wear-and-tear protections are retained in full context.',
        'Can the relationship between joint-inspection findings and later damage claims be clarified?'),
    'late_rate_difference':('The contract uses a weekly late-payment rate while the reference uses an annual rate for overdue payment.',
        'For an eligible short overdue period before the contractual total cap applies, the weekly rate can impose a greater charge. The quoted grace period and cap still apply; the charge is not necessarily greater at every duration.',
        'Can the rate units and calculation for a short overdue period be clarified alongside the grace period and cap?'),
    'express_safeguard_waiver':('The contract expressly waives a deduction safeguard; the reference positively requires written notice and an opportunity to remedy the breach.',
        'For the expressly waived safeguard, deposit deductions may proceed with less protection. No additional waiver is inferred from missing wording.',
        'Can the expressly waived deduction safeguard be retained?'),
    'changed_subletting_permission':('The contract prohibits the stated tenant sharing or subletting; the reference permits the stated activity with prior written consent.',
        'The contractual prohibition can remove the consent-based option for that activity. This does not transfer owner permissions to tenants or establish an immediate termination procedure.',
        'Can the stated activity be subject to prior written consent instead of an outright prohibition?'),
}
