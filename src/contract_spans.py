"""Bind model-selected IDs to exact contract text; never repair invented quotes."""
import copy
import re

def contract_spans(text: str) -> dict[str, str]:
    parts = [m.group(0).strip() for m in re.finditer(r'.+?(?:[.!?](?=\s|$)|$)', text, re.S) if m.group(0).strip()]
    bounded = []
    for part in parts:
        while len(part) > 480:
            cut = part.rfind(' ', 0, 480)
            if cut < 12:
                cut = 480
            bounded.append(part[:cut])
            part = part[cut:].lstrip()
        if part:
            bounded.append(part)
    return {f'C{n:03d}': part for n, part in enumerate(bounded, 1)}

def id_schema(schema: dict) -> dict:
    result = copy.deepcopy(schema)
    result['name'] = 'contract_span_selection_v17'
    item = result['schema']['properties']['comparisons']['items']
    item['properties'].pop('contract_quote')
    item['properties']['contract_span_id'] = {'type': 'string'}
    item['required'] = [field if field != 'contract_quote' else 'contract_span_id' for field in item['required']]
    return result

def resolve_contract_spans(raw: dict, clause: str) -> dict:
    result = copy.deepcopy(raw)
    spans = contract_spans(clause)
    for item in result.get('comparisons', []):
        if 'contract_span_id' in item:
            if 'contract_quote' in item or item['contract_span_id'] not in spans:
                raise ValueError('Unknown or ambiguous contract span ID')
            item['contract_quote'] = spans[item.pop('contract_span_id')]
    return result
