"""Private, explicit aggregate-cost reservation before credentials or requests."""
from decimal import Decimal,InvalidOperation
from pathlib import Path
from src.frozen_external import byte_hash,read_json,require,safe_member


def money(value):
    try: amount=Decimal(str(value))
    except InvalidOperation as error: raise ValueError('Invalid monetary budget') from error
    require(amount.is_finite() and amount>=0,'Invalid monetary budget')
    return amount


def verify_campaign(path: Path|None,repo: Path,run_cap) -> dict:
    require(path is not None,'A human-approved cumulative campaign budget is required')
    path=path.resolve(); repo=repo.resolve()
    require(not path.is_relative_to(repo),'Keep campaign approval outside the public repository')
    approval=read_json(path)
    require(approval.get('approved_by')=='human_owner'
            and isinstance(approval.get('user_authorization_quote'),str)
            and bool(approval['user_authorization_quote'].strip()),'Human campaign budget approval required')
    cap=money(approval.get('max_cost_usd'))
    require(cap>0,'Positive cumulative budget required')
    runs=approval.get('completed_runs')
    require(isinstance(runs,list),'Cumulative accounting records required')
    seen=set(); spent=Decimal('0')
    for entry in runs:
        require(isinstance(entry,dict) and set(entry)=={'run_finished_path','sha256'},'Invalid cumulative run record')
        finished=safe_member(path.parent,entry['run_finished_path'])
        require(not finished.is_relative_to(repo) and finished not in seen,'Duplicated or public run record')
        seen.add(finished)
        require(byte_hash(finished)==entry['sha256'],'Recorded campaign accounting changed')
        record=read_json(finished)
        require(record.get('status') in {'complete','partial_stopped'},'Unfinished campaign run')
        accounting=record.get('accounting',{})
        require(accounting.get('unaccounted_attempt') is False,'Unknown charges prevent another paid run')
        spent+=money(accounting.get('cost_usd'))
    reservation=money(run_cap)
    require(reservation>0 and spent+reservation<=cap,'Cumulative campaign budget cannot reserve another full run')
    return {'campaign_sha256':byte_hash(path),'cap_usd':str(cap),'prior_spend_usd':str(spent),
            'reserved_run_cap_usd':str(reservation),'remaining_after_reservation_usd':str(cap-spent-reservation)}
