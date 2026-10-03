"""Local-only document intake and safe, explicit review execution for the UI."""
from __future__ import annotations
import hashlib
import io
import json
import os
import re
import threading
from contextlib import ExitStack
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from pypdf import PdfReader
from src.frozen_external import MeteredTransport
from src.index_paths import CURRENT_SECTION_INDEX
from src.live_review import ModelReviewRequired, review_clause, local_api_key
from src.retrieval import LocalBM25Retriever

REPO = Path(__file__).resolve().parents[1]
API_LOCK = threading.Lock()
MAX_BYTES, MAX_PAGES, MAX_CHARS = 2_000_000, 20, 80_000
POLICY = json.loads((REPO/'data/live_budget_policy.json').read_text(encoding='utf-8'))
EXPECTED_INDEX_SHA = 'a29c34e93271281696a74766fc18b854c7d175f08004ca592c160749290d0018'

@dataclass(frozen=True)
class Clause:
    clause_id: str
    pages: tuple[int, ...]
    text: str

def safety_issue(text: str, housing: str) -> str | None:
    if housing not in {'HDB', 'Private Residential'}: return 'Select a supported housing type.'
    if not text.strip(): return 'Provide a clause.'
    if len(text) > MAX_CHARS: return 'Document exceeds the 80,000-character limit.'
    patterns = [r'\b[STFGM]\d{7}[A-Z]\b', r'\b[A-Z]\d{7,9}\b',
                r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}', r'(?<!\d)(?:\+65[ -]?)?[689]\d{7}(?!\d)',
                r'\b(?:address|passport number|tenant name|landlord name|NRIC)\s*[:=]\s*\S+',
                r'\bSingapore\s+\d{6}\b', r'\b(?:Block|Blk)\s+\d+\b']
    if any(re.search(p, text, re.I) for p in patterns):
        return 'Potential personal identifier or address detected. Remove it; this prototype accepts synthetic text only.'
    letters = sum(c.isalpha() for c in text)
    if letters and sum(c.isalpha() and not c.isascii() for c in text)/letters > .15:
        return 'Only readable English clauses are supported.'
    if housing == 'Private Residential' and re.search(r'\b(?:HDB|Housing and Development Board)\b', text, re.I):
        return 'The document explicitly mentions HDB. Confirm the housing type; private review is blocked.'
    if housing == 'HDB' and re.search(r'\b(?:private residential|condominium|management corporation)\b', text, re.I):
        return 'The document appears to describe private residential property. Confirm the housing type.'
    return None

def extract_pdf(payload: bytes) -> list[Clause]:
    if len(payload) > MAX_BYTES: raise ValueError('PDF exceeds the 2 MB limit.')
    if not payload.startswith(b'%PDF'): raise ValueError('This is not a PDF.')
    try:
        reader = PdfReader(io.BytesIO(payload), strict=True)
        if reader.is_encrypted: raise ValueError('Encrypted PDFs are not supported.')
        if not 1 <= len(reader.pages) <= MAX_PAGES: raise ValueError('Use a PDF with 1 to 20 pages.')
        pages = [(p.extract_text(extraction_mode='layout') or '') if p.get('/Contents') else '' for p in reader.pages]
    except ValueError: raise
    except Exception: raise ValueError('PDF could not be read safely. Use a readable text PDF.') from None
    # Stop on a low-text page rather than silently overlooking a scanned page.
    if any(len(re.sub(r'\s+', '', text)) < 30 for text in pages):
        raise ValueError('At least one page has too little extractable text. Scans and partial extraction are not supported.')
    if sum(map(len, pages)) > MAX_CHARS: raise ValueError('PDF text exceeds the character limit.')
    chunks, current, locations = [], [], []
    for number, text in enumerate(pages, 1):
        blocks = re.split(r'\n\s*\n|(?=^\s*\d+(?:\.\d+)*[.)]?\s+[A-Za-z])', text, flags=re.M)
        for block in blocks:
            clean = re.sub(r'\s+', ' ', block).strip()
            if not clean: continue
            if current:
                chunks.append(Clause(f'CL_{len(chunks)+1:02d}', tuple(locations), ' '.join(current)))
            current, locations = [clean], [number]
    if current: chunks.append(Clause(f'CL_{len(chunks)+1:02d}', tuple(locations), ' '.join(current)))
    if not chunks or len(chunks) > 60: raise ValueError('Could not form 1 to 60 review fragments. Paste a selected clause instead.')
    if any(len(c.text) > 6000 for c in chunks):
        raise ValueError('A fragment exceeds 6,000 characters. Copy and split it manually without removing conditions.')
    return chunks

def load_retriever() -> LocalBM25Retriever:
    if not CURRENT_SECTION_INDEX.exists():
        raise ValueError('Reference index missing. Run python scripts/bootstrap.py first.')
    if hashlib.sha256(CURRENT_SECTION_INDEX.read_bytes()).hexdigest() != EXPECTED_INDEX_SHA:
        raise ValueError('Reference index does not match the validated v15 snapshot. Rebuild or investigate; do not silently proceed.')
    return LocalBM25Retriever.from_jsonl(CURRENT_SECTION_INDEX)

def run_document(clauses: list[Clause], housing: str, *, synthetic_confirmed: bool,
                 extraction_confirmed: bool, live: bool = False, spending_confirmed: bool = False,
                 budget: str = '.25', request=None) -> dict:
    if not synthetic_confirmed: raise ValueError('Confirm that all input is synthetic and contains no personal data.')
    if not extraction_confirmed: raise ValueError('Check and confirm the extracted text before review.')
    if not 1 <= len(clauses) <= 20: raise ValueError('Review 1 to 20 selected clauses at a time.')
    for clause in clauses:
        issue = safety_issue(clause.text, housing)
        if issue: raise ValueError(issue)
        if len(clause.text) > 6000: raise ValueError('A clause exceeds 6,000 characters.')
    try: dollars = Decimal(budget)
    except Exception: raise ValueError('Invalid dollar budget.') from None
    if not dollars.is_finite() or not Decimal('0') < dollars <= Decimal('1'):
        raise ValueError('Budget must be greater than zero and no more than US$1.')
    if live and (os.getenv('RENTAL_ENABLE_LIVE') != '1' or not spending_confirmed):
        raise ValueError('Live API is disabled. Server-side enablement and a new explicit spending confirmation are required.')
    retriever = load_retriever()
    result = {'version':'v17', 'mode':'live' if live else 'offline', 'housing_type':housing,
              'scope':'Selected fragments only; not a whole-contract approval or legal advice',
              'source_index_sha256':EXPECTED_INDEX_SHA, 'clauses':[], 'stopped':False}
    config = {**POLICY, 'max_cost_usd':str(dollars)}
    log = io.StringIO()
    meter = MeteredTransport(config, log, **({'request':request} if request is not None else {}))
    with API_LOCK, ExitStack() as stack:
        key = None
        if live:
            key = local_api_key()
            if not key: raise ValueError('API key missing. Keep it in the ignored repository-root .env.')
            stack.enter_context(patch('src.live_review._request_openrouter', meter))
            stack.enter_context(patch('src.evidence_verifier._request_openrouter', meter))
        for clause in clauses:
            meter.case_id = clause.clause_id
            before = meter.cost
            row = {'clause_id':clause.clause_id, 'pages':clause.pages, 'text':clause.text}
            try:
                reviewed = review_clause(housing, clause.text, retriever, limit=4, api_key=key, allow_api=live)
                row.update(status='completed', result=asdict(reviewed))
            except ModelReviewRequired:
                row.update(status='model_needed', result=None)
            except Exception as error:
                # Do not expose provider body, credentials or internal exception text.
                row.update(status='stopped', result=None, error_type=type(error).__name__)
                result['stopped'] = True
            row['cost_usd'] = str(meter.cost-before)
            result['clauses'].append(row)
            if result['stopped']: break
    result['accounting'] = meter.accounting()
    result['not_processed_count'] = len(clauses)-len(result['clauses'])
    return result
