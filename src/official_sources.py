"""Pinned, locally cached first-party HTML. No web search at prediction time.

Authority is a provenance check, not a licence to make unrelated legal claims.
All table cells, list items and nested qualifications stay in the section text.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

HOSTS = {
    'HDB': 'www.hdb.gov.sg', 'URA': 'www.ura.gov.sg',
    'IRAS': 'www.iras.gov.sg', 'Singapore Courts': 'www.judiciary.gov.sg',
    'CEA': 'www.cea.gov.sg',
}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class SameAuthorityRedirect(HTTPRedirectHandler):
    def __init__(self, host: str):
        self.host = host

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urlparse(newurl)
        if parsed.scheme != 'https' or parsed.hostname != self.host:
            raise ValueError('Redirect left the allowlisted official publisher')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(source: dict) -> tuple[bytes, str]:
    parsed = urlparse(source['url'])
    host = HOSTS[source['authority']]
    if parsed.scheme != 'https' or parsed.hostname != host or parsed.username:
        raise ValueError('Not an allowlisted official HTTPS URL')
    req = Request(source['url'], headers={'User-Agent': 'Mozilla/5.0 (academic source verification)'})
    with build_opener(SameAuthorityRedirect(host)).open(req, timeout=35) as response:
        if 'text/html' not in response.headers.get('Content-Type', ''):
            raise ValueError('Expected an HTML source')
        body = response.read(4_000_001)
        final_url = response.geturl()
    if len(body) > 4_000_000:
        raise ValueError('Official page exceeds the download limit')
    return body, final_url


@dataclass
class Node:
    tag: str
    attrs: dict = field(default_factory=dict)
    children: list = field(default_factory=list)


class TreeParser(HTMLParser):
    VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node('root')
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = Node(tag, dict(attrs))
        self.stack[-1].children.append(node)
        if tag not in self.VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.stack[-1].children.append(Node(tag, dict(attrs)))

    def handle_endtag(self, tag):
        for n in range(len(self.stack)-1, 0, -1):
            if self.stack[n].tag == tag:
                del self.stack[n:]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def nodes(root):
    yield root
    for item in root.children:
        if isinstance(item, Node):
            yield from nodes(item)


def visible(node: Node) -> str:
    if node.tag in {'script', 'style', 'noscript', 'svg', 'nav', 'header', 'footer'}:
        return ''
    if node.attrs.get('aria-hidden') == 'true':
        return ''
    # Do not drop collapsed accordions: their conditions are meaningful evidence.
    content = ' '.join(visible(c) if isinstance(c, Node) else c for c in node.children)
    if node.tag in {'h1', 'h2', 'h3', 'h4', 'p', 'li', 'tr', 'div', 'section', 'article', 'main', 'br'}:
        content = '\n' + content.strip() + '\n'
    return content


def article_text(body: bytes, source: dict) -> tuple[str, str]:
    parser = TreeParser()
    parser.feed(body.decode('utf-8-sig'))
    all_nodes = list(nodes(parser.root))
    title = next((re.sub(r'\s+', ' ', visible(n)).strip() for n in all_nodes if n.tag == 'title'), '')
    mains = [n for n in all_nodes if n.tag == 'main']
    target = mains[0] if mains else parser.root
    if source['authority'] == 'HDB':
        # HDB publishes its rich text in the page's own Sitecore/Next payload.
        # Read only BodyContent / bodyContent.value, not arbitrary script text.
        script = next((n for n in all_nodes if n.attrs.get('id') == '__NEXT_DATA__'), None)
        if script is None:
            raise ValueError('HDB publisher payload missing')
        data = json.loads(''.join(script.children))
        placeholders = data['props']['pageProps']['layoutData']['sitecore']['route']['placeholders']
        parts = []
        for components in placeholders.values():
            for component in components:
                if component.get('componentName') == 'BodyContent':
                    parts.append(component['fields']['bodyContent']['value'])
        if not parts:
            raise ValueError('HDB article body missing from publisher payload')
        inner = TreeParser()
        inner.feed('\n'.join(parts))
        target = inner.root
    text = visible(target)
    text = '\n'.join(re.sub(r'[\t \r\u00a0]+', ' ', line).strip() for line in text.splitlines())
    text = re.sub(r'\n{3,}', '\n\n', text).strip()
    if len(text) < 400:
        raise ValueError('No substantive official page body; possibly an access-denied response')
    return title, text


def sections(text: str, source: dict) -> list[dict]:
    """Keep complete contiguous paragraphs; never silently cut a qualification."""
    blocks = [b.strip() for b in text.split('\n\n') if b.strip()]
    # Heading-based selection is configured after inspection of the cached page.
    normalize = lambda value: re.sub(r'\s+', ' ', value).strip()
    start = source['article_start']
    end = source['article_end']
    starts = [i for i, b in enumerate(blocks) if normalize(b) == start]
    occurrence = source.get('article_start_occurrence', 1)
    begin = starts[occurrence-1] if len(starts) >= occurrence else None
    if begin is None:
        raise ValueError(f"Verified article start missing: {source['source_id']}")
    finish = len(blocks) if end == '__END_OF_ARTICLE__' else next(
        (i for i in range(begin+1, len(blocks)) if blocks[i].startswith(end)), None)
    if finish is None:
        raise ValueError(f"Verified article end missing: {source['source_id']}")
    content = blocks[begin:finish]
    # Whole sections preserve scope, actors, prerequisites, table rows and dates.
    headings = set(source['section_headings'])
    result, current, heading = [], [], start
    for block in content:
        if normalize(block) in headings and current:
            result.append((heading, '\n\n'.join(current)))
            current, heading = [], normalize(block)
        current.append(block)
    if current:
        result.append((heading, '\n\n'.join(current)))
    return [{**{key: source[key] for key in ('source_id', 'housing_type', 'source_kind', 'title', 'topics')},
             'section': heading, 'clause_id': '', 'page_number': 0, 'text': value,
             'url': source['url'], 'authority': source['authority'],
             'not_for': source['not_for'], 'verified_on': source['verified_on'],
             'source_sha256': source.get('article_sha256',source['html_sha256']),
             'source_hash_kind':'sha256_normalized_visible_article_utf8'}
            for heading, value in result if len(value) > 50]


def load_official_index(repo: Path) -> list[dict]:
    registry = json.loads((repo/'data/official_reference_registry_v18.json').read_text(encoding='utf-8'))
    index = repo/'data/official_sources_v18/index_v18.jsonl'
    if digest(index.read_bytes()) != registry['index_sha256']:
        raise ValueError('Official source index differs from the verified snapshot')
    snapshots = json.loads((repo/'data/official_sources_v18/snapshot_manifest_v18.json').read_text(encoding='utf-8'))
    local_hashes = {r['source_id']:r['actual_html_sha256'] for r in snapshots['sources']}
    for source in registry['sources']:
        body = (repo/'data/official_sources_v18'/f"{source['source_id']}.html").read_bytes()
        if digest(body) != local_hashes.get(source['source_id']):
            raise ValueError('Official source HTML differs from the verified snapshot')
        _, text = article_text(body,source)
        if article_digest(sections(text,source)) != source['article_sha256']:
            raise ValueError('Official article differs from the reviewed substance')
    return [json.loads(line) for line in index.read_text(encoding='utf-8').splitlines() if line.strip()]


def article_digest(chunks: list[dict]) -> str:
    return digest('\n\n'.join(r['text'] for r in chunks).encode('utf-8'))
