"""Label-free, span-bound comparison tasks; cues never assign a risk label."""
from __future__ import annotations
import re
from src.contract_spans import contract_spans

MAX_TASKS=12
TOPICS={
    'refund_trigger':'security_deposit','deposit_forfeiture_amount':'security_deposit','deposit_holding':'security_deposit',
    'deposit_deduction_process':'security_deposit','damage_after_handover':'security_deposit',
    'repair_completion_deadline':'minor_repair','repair_causation':'minor_repair',
    'repair_allocation':'minor_repair','ac_servicing':'minor_repair','repair_self_help':'minor_repair',
    'landlord_exit_trigger':'termination_notice','exit_evidence_acceptance':'termination_notice',
    'tenant_break_clause':'termination_notice','notice_delivery':'termination_notice',
    'current_term_rent_review':'rent','holdover_charge':'rent','late_payment_charge':'rent',
    'rent_payment':'rent','guest_documentation':'occupancy_subletting','occupancy':'occupancy_subletting',
    'subletting_permission':'occupancy_subletting','utilities':'utilities','stamp_duty':'stamp_duty',
    'expert_evidence_and_fees':'dispute_resolution','dispute_route':'dispute_resolution','other':'unknown'}


def tasks_for(clause,packet,housing):
    spans=contract_spans(clause)
    refs=packet['references']
    hdb=housing=='HDB'
    def ids(cids,contains=None,kind=None):
        return [r['evidence_id'] for r in refs if (r.get('clause_id') in cids if cids else True)
                and (not contains or contains.casefold() in r['text'].casefold())
                and (not kind or r['source_kind']==kind)]
    quiet=ids({'7.1' if hdb else '6.1'},'HOLD AND ENJOY')
    rent=ids({'1.4' if hdb else '1.3','ITEM8'})
    end=ids({'19.1' if hdb else '20.1'})
    break_ids=ids({'ITEM16' if hdb else 'ITEM14'})
    aircon=bool(re.search(r'\bair.condition\w*\b',clause,re.I))
    # Related clauses preserve exceptions and mitigation. They are context,
    # not permission to declare every neighboring duty settled.
    exit_context=[c for c,t in spans.items() if re.search(r'\b(?:terminat\w*|forfeit\w*|relocation compensation|shall not exercise|first \w+.{0,12}months)\b',t,re.I)]
    rent_context=[c for c,t in spans.items() if re.search(r'\brent\b|\b(?:revised|revision|increase)\b',t,re.I)]
    tasks=[]
    def add(cid,mechanism,groups,check,terms=(),context=()):
        span_ids=list(dict.fromkeys([cid,*context]))
        tasks.append({'task_id':f'T{len(tasks)+1:03d}','mechanism':mechanism,'topic':TOPICS[mechanism],
                      'contract_span_ids':span_ids,'required_reference_groups':groups,
                      'required_fact_terms':list(terms),'comparison_question':check})
    for cid,text in spans.items():
        matched=False
        def task(mechanism,groups,check,terms=(),context=()):
            nonlocal matched
            add(cid,mechanism,groups,check,terms,context); matched=True
        if re.search(r'\b(?:refund|return|repay)\w*\b.{0,60}\b(?:deposit|balance)\b|\bdeposit\b.{0,80}\b(?:refund|return)\w*\b',text,re.I):
            task('refund_trigger',[ids({'2.2'})],
                 'Compare expiry/termination with the actual refund trigger and later window. A stated post-handover window can delay receipt; clarity alone is not a tenant benefit. Do not invent a statutory zero-day deadline.',('refund','Term'))
        if re.search(r'\bforfeit\w*\b',text,re.I):
            task('deposit_forfeiture_amount',[ids({'2.2'})],
                 'Compare whole-deposit forfeiture with a reasonable breach-remedy amount. Preserve express exceptions for permitted early exit. Do not infer a notice waiver or treat silent further-damage wording as a prohibition.',('reasonable','breach'),exit_context)
        elif (re.search(r'\b(?:deduct|replenish|recover)\w*\b.{0,100}\bdeposit\b|\bdeposit\b.{0,70}\b(?:deduct|replenish)\w*\b',text,re.I)
              or (re.search(r'\blandlord\b.{0,90}\bdeduct\w*\b',text,re.I) and re.search(r'\bdeposit\b',clause,re.I))):
            task('deposit_deduction_process',[ids({'2.2'})],
                 'Compare an EXPRESS process change only. May deduct and post-deduction replenishment do not waive prior notice/cure. A missing phrase is unsettled, not an adverse waiver.')
        if re.search(r'\bdeposit\b',text,re.I) and not matched:
            task('deposit_holding',[ids({'2.2'})], 'Compare security purpose/payment/holding or rent set-off only. Blank deposit amounts are negotiated, not fixed mandatory standards.')
        if re.search(r'\b(?:damage|defect)\w*\b',text,re.I) and re.search(r'\b(?:refund|handover|joint inspection)\b',text,re.I):
            task('damage_after_handover',[ids({'5.4' if hdb else '5.5'})],
                 'Compare later damage claims with damage ascertained at joint inspection; retain written notice, time limit and fair-wear qualifiers. Do not compare this with pre-deduction cure.',('joint inspection',))
        if re.search(r'\brepairs?\b',text,re.I) and re.search(r'\bwithin\b',text,re.I) and re.search(r'\b(?:carry out|complete|recover)\b',text,re.I):
            task('repair_completion_deadline',[ids({'4.7'})],
                 'Reference separates proceeding within a deadline and completing within reasonable time. Compare the contract carry-out/completion cost-recovery trigger. If carry out is ambiguous, state that ambiguity and ask whether completion is required; do not assert identical start and completion conditions.',('proceed','reasonable time'))
        elif re.search(r'\b(?:repair|structur|concealed|wiring|pipes?)\w*\b',text,re.I) and not aircon and not re.search(r'\bdeduct\w*\b',text,re.I):
            task('repair_allocation',[ids({'4.2','4.3','7.1' if hdb else '6.1'})],
                 'Compare repair allocation and preserved wear/structural conditions, not just a matching general topic.')
        if aircon and re.search(r'\b(?:repair|replacement|replac\w*)\b',text,re.I):
            task('repair_causation',[ids({'4.5'})],
                 'Is payment tied to a fault CAUSED by non-maintenance, or additionally to formal compliance even where the fault is NOT attributable? A quarterly schedule alone is not an independent non-causal cost condition. Inspect provided-that qualifications.',('breakdown',))
        if aircon and re.search(r'\b(?:service|servicing)\b',text,re.I) and not re.search(r'\b(?:replacement|repair)\b',text,re.I):
            task('ac_servicing',[ids({'4.4'})], 'Compare servicing/receipts duties only; this paragraph is not replacement-causation evidence.')
        if re.search(r'\b(?:landlord|either party)\b\s+(?:(?:may|can|shall be entitled to|is entitled to)\s+(?:elect to\s+)?(?:terminat\w*|end (?:this |the )?(?:tenancy|agreement))\b|terminates?\b)',text,re.I):
            task('landlord_exit_trigger',[quiet],
                 'Assess loss of the COMPLIANT tenant remaining term against positive conditional quiet enjoyment. Evaluate landlord and tenant rights separately; reciprocal tenant exit does not cancel landlord-triggered relocation. Retain lock-in, notice and relocation compensation. Default wording is not an exhaustive catalogue of termination grounds.',('hold and enjoy',),exit_context)
        if re.search(r'\b(?:acceptable|satisfactory) to the Landlord\b',text,re.I):
            task('exit_evidence_acceptance',[break_ids],
                 'Compare documentary evidence of an objective event with an added landlord acceptance condition. Do not imply unlimited discretion where reasonable/objective authenticity conditions appear.',('documentary evidence',))
        elif re.search(r'\btenant\b.{0,65}\bterminat\w*\b',text,re.I):
            task('tenant_break_clause',[break_ids],
                 'Preserve qualifying events and the optional nature of the clause. Blank negotiated periods are not standards. A one-use termination right is not loss of repeated exits because exercise ends the tenancy.')
        if re.search(r'\brent\b',text,re.I) and re.search(r'\b(?:revis\w*|review|increase|adjust\w*)\b',text,re.I):
            task('current_term_rent_review',[rent],
                 'Compare an original-term revision with the agreed rent. Preserve the initial fixed period, notice and penalty-free exit; exit does not allow staying at the previous rent. Do not turn an extension-only paragraph into an exhaustive ban on revisions.',('rent',),rent_context)
        elif re.search(r'\bdouble\b.{0,30}\brent\b',text,re.I):
            task('holdover_charge',[end,rent],
                 'Compare the post-expiry multiplier with continuing obligations and agreed Rent. Both end-of-tenancy and rent-definition facts are needed. Late-payment interest is a different mechanism.',('rent',))
        elif re.search(r'\b(?:late payment|late charge|overdue)\b|\binterest\b(?!\s*,?\s*(?:less|within))',text,re.I) and not re.search(r'\bwithout interest\b',text,re.I):
            task('late_payment_charge',[ids({'8.4' if hdb else '7.4'})],
                 'Compare weekly/annual units with the same unpaid trigger; preserve the total cap and grace period. Do not release a neighboring invented immediate deposit deduction.',('per annum',))
        elif (re.search(r'\b(?:rent|monthly payment)\b',text,re.I) and not re.search(r'\bdeposit\b',text,re.I)
              and re.search(r'\btenant\b.{0,30}\b(?:shall |must |agrees? to )?pay\w*\b|\bmonthly rent\b.{0,70}\bshall be\b',text,re.I)):
            task('rent_payment',[rent,ids({'2.1'})], 'Compare stated rent/payment terms without treating blank amounts as mandatory standards.')
        if re.search(r'\bguests?\b',text,re.I) or (re.search(r'\b(?:person|occupiers?)\b',text,re.I) and re.search(r'\bconsecutive days\b',text,re.I)):
            guest_ids=[r['evidence_id'] for r in refs if re.search(r'\bguests?\b',r['text'],re.I)]
            task('guest_documentation',[guest_ids], 'Named occupiers and headcount are not ordinary guest identity/reporting/stay-threshold standards. Without direct guest evidence this task is uncertain.')
        elif re.search(r'\b(?:occup|resid|passport|identity)\w*\b',text,re.I) and not re.search(r'\bterminat\w*\b',text,re.I):
            task('occupancy',[ids({'1.1','ITEM6'})], 'Compare named occupiers only, retaining exclusions and scope; do not invent personal-residence termination rules.')
        if re.search(r'\b(?:sublet|sub.let|share the Premises|co.tenant|assign|part with possession)\w*\b',text,re.I):
            task('subletting_permission',[ids({'5.1'})],
                 'Compare actual consent/prohibition and actors. Owner HDB permissions do not transfer to tenants. Do not infer an immediate termination procedure from material breach alone.')
        if re.search(r'\b(?:utilit\w*|electricity|water(?:.borne)?|gas|sewer\w*)\b',text,re.I) and not re.search(r'\b(?:deposit|refund|repair|replacement|concealed pipe|gas top.up)\b',text,re.I):
            terms=[]
            for pattern,term in [(r'\btransfer\w*\b','transfer'),(r'\binterruption\b','interruption'),
                                 (r'\bapportion\w*\b','apportion'),(r'\b(?:surcharge|mark.up)\b','surcharge')]:
                if re.search(pattern,text,re.I): terms.append(term)
            task('utilities',[ids({'2.3'})], 'Compare utility payer only. Transfer deadlines, shared-meter allocations and supply-interruption liability need direct evidence; do not approve them from a generic payer paragraph.',terms)
        if re.search(r'\b(?:surveyor|expert|report)\b',text,re.I):
            task('expert_evidence_and_fees',[ids({'12.2' if hdb else '13.2'})], 'A dispute route does not establish binding expert decisions or expert fee allocation. Unsupported fees are uncertain.')
        elif re.search(r'\b(?:mediat|arbitrat|tribunal|court)\w*\b',text,re.I):
            task('dispute_route',[ids({'12.2' if hdb else '13.2'})], 'Compare only the expressed dispute route; it does not settle fees or enforceability.')
        if re.search(r'\bstamp duty\b',text,re.I):
            task('stamp_duty',[ids(set(),kind='stamp_duty_guidance')], 'Compare tax payer and timing only; no legal-validity verdict.')
        if not matched:
            task('other',[], 'This material span has no registered comparison mechanism. Keep it unassessed; never invent a standard.')
    return tasks[:MAX_TASKS],len(tasks)>MAX_TASKS
