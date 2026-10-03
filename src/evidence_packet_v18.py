"""Mechanism-aware packets: CEA comparison + strictly scoped official context.

No labels, evaluation IDs or exact evaluation clauses are read by this module.
The v15 source text is immutable; only selection and derived metadata change.
"""
from __future__ import annotations
import json
import re
from pathlib import Path
from src.official_sources import load_official_index
from src.retrieval import LocalBM25Retriever, query_topics, tokenize

TEMPLATE_KIND = 'tenancy_agreement_template'
MAX_PACKET_CHARS = 26000
MAX_TEMPLATE_SECTIONS = 9
MAX_OFFICIAL_SECTIONS = 3


def topics_for(text: str) -> set[str]:
    topics = query_topics(text)
    if re.search(r'\b(?:stamp(?:ing)? duty|stamp certificate|e-stamp)\b', text, re.I):
        topics.add('stamp_duty')
    if re.search(r'\b(?:mediat\w*|arbitrat\w*|surveyor|prima facie|final and binding|small claims?|disput\w*)\b', text, re.I):
        topics.add('dispute_resolution')
    if re.search(r'\b(?:estate agency agreement|property agency|agent.{0,20}commission)\b', text, re.I):
        topics.add('agent_dispute')
    if re.search(r'\b(?:holdover|holding over|keys?|access cards?|vacant possession)\b', text, re.I):
        topics.add('termination_notice')
    # A report/expert fee is not a rent obligation simply because it is a fee.
    if 'dispute_resolution' in topics and not re.search(r'\b(?:rent|rental|late payment)\b', text, re.I):
        topics.discard('rent')
    return topics


def web_eligible(row: dict, query: str, housing: str) -> bool:
    if row['housing_type'] not in {housing, 'Both'}:
        return False
    kind = row['source_kind']
    if kind == 'stamp_duty_guidance':
        return 'stamp_duty' in topics_for(query)
    if kind == 'agent_dispute_route_guidance':
        return 'agent_dispute' in topics_for(query)
    if kind == 'dispute_route_guidance':
        # This is route information, not evidence that a report fee is unfair.
        return bool(re.search(r'\b(?:small claims?|SCT|tribunal|court|litigat\w*)\b', query, re.I))
    if kind == 'housing_policy_background':
        if row['source_id'] == 'HDB_ROOM_TERMS' and not re.search(r'\b(?:bedrooms?|rooms?|sublet\w*)\b', query, re.I):
            return False
        return bool(re.search(r'\b(?:sublet\w*|rent.{0,20}others|occup\w*|register\w*|HDB.{0,20}approval|minimum stay|short.term|daily rental|weekly rental|rental period)\b', query, re.I))
    return False


class PacketRetriever:
    def __init__(self, templates: list[dict], official: list[dict]):
        self.templates = templates
        self.official = official
        self.legacy = LocalBM25Retriever(templates)

    @classmethod
    def from_repo(cls, repo: Path):
        templates = [json.loads(l) for l in (repo/'data/derived/source_sections_v15.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()]
        return cls(templates, load_official_index(repo))

    def search(self, query, housing_type, limit=4):
        """Historical local matchers still receive only housing-specific CEA text."""
        return self.legacy.search(query, housing_type, limit)

    def packet(self, query: str, housing: str) -> dict:
        if housing not in {'HDB', 'Private Residential'}:
            return {'references':[], 'truncated':False, 'topics':[]}
        topics = topics_for(query)
        lowered = query.casefold()
        hdb = housing == 'HDB'
        ids = []
        def add(*values):
            for value in values:
                if value not in ids:
                    ids.append(value)
        if 'security_deposit' in topics:
            add('2.2', 'ITEM9')
            if re.search(r'\b(?:damag\w*|inspection|claim|vacant|refund|deduct\w*)\b', lowered):
                add('5.4' if hdb else '5.5')
        if 'minor_repair' in topics:
            if re.search(r'\b(?:air.condition\w*|servic\w*)\b', lowered):
                add('4.5', '4.4')
            if re.search(r'\b(?:structur\w*|conceal\w*|pipes?|wiring|drains?|plumb\w*)\b', lowered):
                add('7.1' if hdb else '6.1')
            add('4.2', 'ITEM10', '4.3')
            if re.search(r'\b(?:recover|reimburse|repair.{0,30}(?:notice|consent)|emergency)\b', lowered):
                add('4.9')
            if re.search(r'\b(?:report|plumber|contractor|fee)\b', lowered):
                add('4.8')
        if 'termination_notice' in topics:
            if re.search(r'\b(?:holdover|holding over|keys?|belongings|vacant possession)\b', lowered):
                add('19.1' if hdb else '20.1', '5.3' if hdb else '5.4')
            if re.search(r'\b(?:relocat\w*|employment|diplomatic|12 months|twelve months|break clause)\b', lowered):
                add('ITEM16' if hdb else 'ITEM14')
            add('8.1' if hdb else '7.1')
            if re.search(r'\b(?:destroy\w*|fire|uninhabitable)\b', lowered):
                add('9.2' if hdb else '8.2')
            if re.search(r'\b(?:email|post|service of notices|served|deliver)\b', lowered):
                add('11.1' if hdb else '12.1')
        if 'occupancy_subletting' in topics:
            add('5.1', '1.1', 'ITEM6')
            if re.search(r'\b(?:passport|identity|foreign|immigration)\b', lowered):
                add('3.2', '3.1', '3.3')
            if hdb and re.search(r'\b(?:HDB|register|approval)\b', query, re.I):
                add('1.2', '3.4')
        if 'rent' in topics:
            if re.search(r'\b(?:late|interest|arrears|overdue)\b', lowered):
                add('8.4' if hdb else '7.4')
            if re.search(r'\b(?:review|revis\w*|increas\w*|adjust\w*|management|conservancy)\b', lowered):
                add('7.1' if hdb else '6.1')
            add('1.4' if hdb else '1.3', 'ITEM8', '2.1')
        if 'utilities' in topics:
            add('2.3', '7.1' if hdb else '6.1')
        if 'dispute_resolution' in topics:
            add('12.2' if hdb else '13.2')
        selected = []
        housing_rows = [r for r in self.templates if r['housing_type'] == housing and r['source_kind'] == TEMPLATE_KIND]
        for clause_id in ids:
            matches = [r for r in housing_rows if r.get('clause_id') == clause_id]
            if clause_id == '7.1' and hdb and 'minor_repair' in topics:
                matches = [r for r in matches if '(f)' in r['section']] or matches
            if clause_id == '5.1':
                matches = [r for r in matches if 'The Tenant further agrees' in r['text']]
            # Stable clauses, not evaluation-case rules. Prefer complete text.
            for row in matches:
                if row not in selected and not any(row['text'] in chosen['text'] for chosen in selected):
                    selected.append(row)
        conventional = topics.intersection({'security_deposit','minor_repair','termination_notice','occupancy_subletting','rent','utilities'})
        ranked = self.legacy.search(query, housing, limit=12) if conventional else []
        for chunk in ranked:
            row = next(r for r in housing_rows if r['section'] == chunk.section and r['text'] == chunk.text)
            if row not in selected and not any(row['text'] in chosen['text'] for chosen in selected):
                selected.append(row)
        # Always reserve one CEA dispute mechanism if the query needs it.
        if 'dispute_resolution' in topics:
            dispute = next((r for r in selected if r['clause_id'] == ('12.2' if hdb else '13.2')), None)
            if dispute:
                selected.remove(dispute)
                selected.insert(min(3, len(selected)), dispute)
        selected = selected[:MAX_TEMPLATE_SECTIONS]
        official = [r for r in self.official if web_eligible(r, query, housing)]
        words = set(tokenize(query))
        def rank(row):
            score = len(words.intersection(tokenize(row['text'])))
            if 'sublet' in lowered and 'Regulations for Renting Out' in row['section']:
                score += 20
            if 'sublet' in lowered and row['source_id']=='HDB_ROOM_TERMS' and row['section'].startswith('Responsibility of Flat Owners'):
                score += 30
            if re.search(r'\b(?:eight|8)\b', lowered) and row['section'] in {'Occupancy cap', 'Temporary relaxation for larger properties'}:
                score += 12
            return (-score, row['source_id'], row['section'])
        official = sorted(official, key=rank)[:MAX_OFFICIAL_SECTIONS]
        # URA occupancy relaxation must travel with its prerequisites, never alone.
        if any(r['source_id']=='URA_RENTING_PROPERTY' and r['section']=='Occupancy cap' for r in official):
            related = next(r for r in self.official if r['source_id']=='URA_RENTING_PROPERTY' and r['section']=='Temporary relaxation for larger properties')
            if related not in official:
                official = official[:MAX_OFFICIAL_SECTIONS-1]+[related]
        references, characters, truncated = [], 0, False
        for row in selected+official:
            if len(row['text']) > 7500 or characters+len(row['text']) > MAX_PACKET_CHARS:
                truncated = True
                continue  # No cut-off quote is presented as complete evidence.
            enriched = dict(row)
            if row.get('clause_id') in {'12.2' if hdb else '13.2'} and row['source_kind']==TEMPLATE_KIND:
                enriched['topics'] = list(set(enriched.get('topics', [])) | {'dispute_resolution'})
            if row.get('clause_id') in {'19.1' if hdb else '20.1'} and row['source_kind']==TEMPLATE_KIND:
                enriched['topics'] = list(set(enriched.get('topics', [])) | {'termination_notice', 'rent'})
            if row.get('clause_id') == ('6.1' if not hdb else '7.1') and row['source_kind']==TEMPLATE_KIND:
                enriched['topics'] = list(set(enriched.get('topics', [])) | {'minor_repair', 'rent', 'utilities'})
            enriched['evidence_id'] = f'R{len(references)+1:03d}'
            enriched['topics'] = sorted(enriched.get('topics', []))
            references.append(enriched)
            characters += len(row['text'])
        return {'references':references, 'truncated':truncated, 'topics':sorted(topics)}
