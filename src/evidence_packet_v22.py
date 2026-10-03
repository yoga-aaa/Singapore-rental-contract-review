"""Select full, scope-checked registered sections using v22 task discovery."""
from src.evidence_packet_v19 import CoverageRetriever
from src.evidence_packet_v18 import MAX_PACKET_CHARS,TEMPLATE_KIND,web_eligible
from src.mechanism_tasks_v22 import plan_for
from src.routing_text_v22 import match_text


class ConditionRetriever(CoverageRetriever):
    def packet(self,query,housing):
        if housing not in {'HDB','Private Residential'}:
            return {'references':[],'truncated':False,'topics':[]}
        pool=[dict(r) for r in self.templates if r['housing_type']==housing and r['source_kind']==TEMPLATE_KIND]
        # Other authority is still evidence only for its stated scope, never
        # an arbitrary replacement for a required template mechanism.
        pool += [dict(r) for r in self.official if web_eligible(r,match_text(query),housing)]
        for i,row in enumerate(pool,1): row['evidence_id']=f'POOL{i:03d}'
        discovery=plan_for(query,{'references':pool},housing)
        lookup={r['evidence_id']:r for r in pool}
        required=[]; routes=[]
        for task in discovery['tasks']:
            groups=[]
            for group in task['required_reference_groups']:
                # Preserve the shortest complete registered matching section
                # first; no clipping or synthetic source paragraph.
                members=sorted((lookup[r] for r in group),key=lambda r:len(r['text']))
                groups.append(members)
                if members and members[0] not in required: required.append(members[0])
            routes.append(groups)
        extra=[]
        for groups in routes:
            for group in groups:
                for row in group:
                    if row not in required and row not in extra: extra.append(row)
        old=super().packet(match_text(query),housing)
        for row in old['references']:
            if not any(row['source_id']==r['source_id'] and row['section']==r['section'] for r in required+extra):
                extra.append(row)
        selected=[]; chars=0; template_count=0; official_count=0
        omitted=[]
        for row in required+extra:
            template=row['source_kind']==TEMPLATE_KIND
            over=(template_count>=12 if template else official_count>=3)
            if over or len(row['text'])>7500 or chars+len(row['text'])>MAX_PACKET_CHARS:
                if row in required: omitted.append({'source_id':row['source_id'],'section':row['section']})
                continue
            item=dict(row); item['evidence_id']=f'R{len(selected)+1:03d}'
            selected.append(item); chars+=len(row['text'])
            template_count+=int(template); official_count+=int(not template)
        return {'references':selected,'truncated':bool(omitted),
                'topics':old.get('topics',[]),'omitted_required_locations':omitted,
                'selection_scope':'Original complete registered text; routing aliases and candidate coverage are not support verdicts.'}
