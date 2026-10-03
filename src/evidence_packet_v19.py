"""Coverage-first selection over the SAME pinned v18 sources; no new gold data.

Reserve evidence by material mechanism, not by the first topic in the clause.
Selection limits are explicit. A retained quote is a whole indexed section;
no fabricated reference paragraph or cross-housing join is created.
"""
from __future__ import annotations
import re
from src.evidence_packet_v18 import MAX_PACKET_CHARS, PacketRetriever, TEMPLATE_KIND, topics_for
from src.review_v18 import obligation_inventory

MAX_TEMPLATES=12
MAX_OFFICIAL=3


class CoverageRetriever(PacketRetriever):
    def packet(self,query: str,housing: str) -> dict:
        if housing not in {'HDB','Private Residential'}:
            return {'references':[],'truncated':False,'topics':[],'coverage':{}}
        hdb=housing=='HDB'
        topics=topics_for(query)
        inventory=obligation_inventory(query)
        mechanisms=list(dict.fromkeys(o['mechanism'] for o in inventory.values()))
        rows=[r for r in self.templates if r['housing_type']==housing and r['source_kind']==TEMPLATE_KIND]
        def find(cid,purpose=''):
            matches=[r for r in rows if r.get('clause_id')==cid]
            if purpose=='quiet':
                matches=[r for r in matches if 'HOLD AND ENJOY' in r['text']]
            elif purpose=='structural' and hdb:
                matches=[r for r in matches if '(f)' in r['section']]
            elif purpose=='extension' and hdb:
                matches=[r for r in matches if '(c)' in r['section']]
            elif cid=='5.1':
                matches=[r for r in matches if 'The Tenant further agrees' in r['text']]
            return matches
        quiet=find('7.1' if hdb else '6.1','quiet')
        structural=find('7.1' if hdb else '6.1','structural')
        end=find('19.1' if hdb else '20.1')
        rent=find('1.4' if hdb else '1.3')+find('ITEM8')
        default=find('8.1' if hdb else '7.1')
        break_rows=find('ITEM16' if hdb else 'ITEM14')
        holdover=bool(re.search(r'\b(?:holdover|holding over|remains? in (?:occupation|possession)|double.{0,20}rent|keys?|vacant possession)\b',query,re.I))
        routes={}
        for mechanism in mechanisms:
            selected=[]
            if mechanism=='deposit_settlement':
                selected=find('2.2')+(end if holdover else [])
            elif mechanism=='deposit_deduction':
                selected=find('2.2')
            elif mechanism=='repair_allocation':
                selected=(structural if re.search(r'\b(?:structur\w*|concealed|pipes?|wiring)\b',query,re.I) else [])+find('4.2')+find('ITEM10')+find('4.3')
            elif mechanism=='repair_self_help':
                selected=find('4.7')+find('4.9')
            elif mechanism=='ac_maintenance':
                selected=find('4.5')+find('4.4')
            elif mechanism=='damage_after_handover':
                selected=find('5.4' if hdb else '5.5')
            elif mechanism=='expert_evidence_and_fees':
                selected=find('12.2' if hdb else '13.2')
                if re.search(r'\b(?:charge.out|contractor|no (?:fault|defect))\b',query,re.I):
                    selected+=find('4.8')
            elif mechanism=='exit_terms':
                selected=(end+rent if holdover else quiet+default)
                if re.search(r'\b(?:relocat\w*|employment|work permit|diplomatic|documentary|break clause)\b',query,re.I):
                    selected=break_rows+selected
                if re.search(r'\b(?:email|registered post|notice.{0,20}served)\b',query,re.I):
                    selected+=find('11.1' if hdb else '12.1')
            elif mechanism=='subletting':
                selected=find('5.1')+default+find('2.2')
            elif mechanism=='occupancy_and_guests':
                selected=find('1.1')+find('ITEM6')
                if re.search(r'\b(?:passport|identit\w*|immigration|status)\b',query,re.I):
                    selected+=find('3.2')+find('3.3')
            elif mechanism=='rent_amount_and_revision':
                selected=rent+find('2.1')
                if re.search(r'\b(?:review|revis\w*|increas\w*|adjust\w*)\b',query,re.I):
                    selected=find('7.1','extension')+selected if hdb else quiet+selected
            elif mechanism=='late_charges':
                selected=end+rent if re.search(r'\bdouble.{0,20}rent\b',query,re.I) else find('8.4' if hdb else '7.4')
            elif mechanism=='utilities_and_billing':
                selected=find('2.3')
                if re.search(r'\b(?:management|service charge|conservancy|outgoings)\b',query,re.I):
                    selected+=find('7.1' if hdb else '6.1','quiet')
            elif mechanism=='dispute_route':
                selected=find('12.2' if hdb else '13.2')
            routes[mechanism]=selected
        # A repair cost-recovery trigger needs 4.7 even if the cue inventory's
        # broad repair category did not classify it as self-help.
        if re.search(r'\brepairs?\b.{0,160}\b(?:within|notice)\b|\b(?:recover|carry out)\b.{0,80}\brepairs?\b',query,re.I):
            routes['repair_deadline']=find('4.7')
        if holdover:
            routes['end_of_tenancy']=end
        if (re.search(r'\b(?:damage|inspection)\b',query,re.I)
                and re.search(r'\b(?:refund|handover|joint inspection)\b',query,re.I)):
            routes['damage_handover_context']=find('5.4' if hdb else '5.5')
        # Fair rotation: each mechanism gets its primary section first.
        required=[]
        depth=0
        while any(depth<len(group) for group in routes.values()):
            for group in routes.values():
                if depth<len(group) and group[depth] not in required:
                    required.append(group[depth])
            depth+=1
        selected=required[:MAX_TEMPLATES]
        for chunk in self.legacy.search(query,housing,limit=12):
            row=next(r for r in rows if r['section']==chunk.section and r['text']==chunk.text)
            if row not in selected and len(selected)<MAX_TEMPLATES:
                selected.append(row)
        old=super().packet(query,housing)
        official=[r for r in old['references'] if r['source_kind']!=TEMPLATE_KIND][:MAX_OFFICIAL]
        references=[]
        chars=0
        omitted=[]
        for row in selected+official:
            if len(row['text'])>7500 or chars+len(row['text'])>MAX_PACKET_CHARS:
                omitted.append((row['source_id'],row['section']))
                continue
            enriched=dict(row)
            row_topics=set(row.get('topics',[]))
            cid=row.get('clause_id')
            if cid in {'19.1' if hdb else '20.1'}:
                row_topics|={'termination_notice','rent'}
            if cid in {'ITEM16' if hdb else 'ITEM14'}:
                row_topics|={'termination_notice','rent'}
            if cid==('7.1' if hdb else '6.1') and 'HOLD AND ENJOY' in row['text']:
                row_topics|={'termination_notice','rent','utilities','minor_repair'}
            if cid in {'12.2' if hdb else '13.2'}:
                row_topics.add('dispute_resolution')
            enriched['topics']=sorted(row_topics)
            enriched['evidence_id']=f'R{len(references)+1:03d}'
            references.append(enriched)
            chars+=len(row['text'])
        available={(r['source_id'],r['section']) for r in references}
        omitted_required=[{'source_id':r['source_id'],'section':r['section']} for r in required
                          if (r['source_id'],r['section']) not in available]
        coverage={m:{'reference_ids':[r['evidence_id'] for r in references
                    if any(r['source_id']==candidate['source_id'] and r['section']==candidate['section'] for candidate in group)],
                     'requested_sections':[r['section'] for r in group]} for m,group in routes.items()}
        return {'references':references,'truncated':bool(omitted or omitted_required),
                'topics':sorted(topics),'coverage':coverage,'omitted_required_locations':omitted_required,
                'selection_scope':'Mechanism cues guide retrieval; do not prove semantic coverage.'}
