"""Label-free stage diagnostics; these counts are not quality scores."""
from src.condition_facts_v21 import task_issue
from src.mechanism_tasks_v21 import tasks_for
from src.review_v21 import validated_extraction,row_shape_issue


def diagnose(extraction,comparison,clause,packet,housing):
    tasks,truncated=tasks_for(clause,packet,housing)
    lookup={t['task_id']:t for t in tasks}; refs={r['evidence_id']:r for r in packet['references']}
    literal=validated_extraction(extraction,tasks,clause,packet)
    rows=comparison.get('comparisons',[]) if isinstance(comparison,dict) else []
    if not isinstance(rows,list): rows=[]
    checks=[]
    for row in rows:
        shape=row_shape_issue(row,lookup,refs,True)
        if shape:
            checks.append({'stage':'comparison_shape','issue':shape}); continue
        task=lookup[row['task_id']]
        gate=(task_issue(row,task,clause,refs,housing)
              if row['decision']=='supported' and row['relation']!='uncertain' else None)
        checks.append({'task_id':row['task_id'],'mechanism':task['mechanism'],
            'model_decision':row['decision'],'model_relation':row['relation'],
            'model_contrast':row['contrast_kind'],'release_gate_issue':gate,
            'required_groups_present':all(bool(g) for g in task['required_reference_groups'])
                and bool(task['required_reference_groups'])})
    return {'task_count':len(tasks),'task_selection_truncated':truncated,
            'source_selection_truncated':packet['truncated'],
            'literal_fact_rows_bound':len(literal['facts']),
            'literal_fact_rows_rejected':literal['rejected_fact_rows'],
            'checks':checks,'quality_metrics':None,
            'notice':'Engineering diagnosis only: no gold labels, fresh predictions, citation audit or generalization score.'}
