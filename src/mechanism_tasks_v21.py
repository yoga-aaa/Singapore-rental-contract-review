"""Keep distinct causal duties; collapse duplicate contextual comparison tasks."""
from src.mechanism_tasks_v20 import tasks_for as original_tasks,MAX_TASKS


def tasks_for(clause,packet,housing):
    tasks,truncated=original_tasks(clause,packet,housing)
    seen=set(); selected=[]
    for task in tasks:
        key=(task['mechanism'],tuple(sorted(task['contract_span_ids'])),
             tuple(tuple(g) for g in task['required_reference_groups']))
        if key in seen: continue
        seen.add(key)
        selected.append({**task,'task_id':f'T{len(selected)+1:03d}'})
    # Do not hide an original task-cap drop. Distinct spans of the same
    # mechanism (e.g. causal vs formal AC conditions) must never be merged.
    return selected,truncated
