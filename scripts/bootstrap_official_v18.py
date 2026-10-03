"""Download dated official snapshots; --inspect does not activate them.

The confirmed registry pins bytes. A changed page needs a new reviewed version,
not an automatic replacement of historical evidence.
"""
import argparse
import json
import sys
from datetime import datetime,timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.official_sources import article_text, article_digest, digest, fetch, sections


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inspect', action='store_true')
    parser.add_argument('--build-reviewed-index', action='store_true', help='Build from hash-verified, manually inspected registry; print derived hash for pinning')
    parser.add_argument('--print-article-hashes',action='store_true',help='Inspect derived substantive hashes, without building or activating an index')
    args = parser.parse_args()
    directory = ROOT/'data/official_sources_v18'
    directory.mkdir(exist_ok=True)
    registry = ROOT/'data/official_reference_registry_v18.json'
    data = json.loads((ROOT/'data/reference_candidates.json' if args.inspect else registry).read_text(encoding='utf-8'))
    chunks, snapshots = [], []
    for source in data['sources']:
        source = {**source, 'source_id': source['source_id'].removesuffix('_CANDIDATE')}
        file = directory/f"{source['source_id']}.html"
        final_url = source['url']
        if file.exists():
            body = file.read_bytes()
        else:
            body, final_url = fetch(source)
            if not args.inspect:
                _, downloaded_text = article_text(body,source)
                if article_digest(sections(downloaded_text,source)) != source['article_sha256']:
                    raise ValueError('Official article changed: a new reviewed source version is required')
            with file.open('xb') as output:
                output.write(body)
        title, text = article_text(body, source)
        if args.inspect:
            # A private inspectable extraction, never a substitute for the HTML.
            target = directory/f"{source['source_id']}.txt"
            if not target.exists():
                with target.open('x', encoding='utf-8') as output:
                    output.write(text)
            print(json.dumps({'source_id':source['source_id'], 'title':title,
                              'url':final_url, 'html_sha256':digest(body), 'characters':len(text)}, ensure_ascii=False))
        else:
            extracted = sections(text, source)
            article_hash = article_digest(extracted)
            if args.print_article_hashes:
                print(json.dumps({'source_id':source['source_id'],'article_sha256':article_hash}))
                continue
            if article_hash != source['article_sha256']:
                raise ValueError('Cached official article differs from reviewed substance')
            chunks.extend(extracted)
            snapshots.append({'source_id':source['source_id'],'actual_html_sha256':digest(body),
                              'article_sha256':article_hash,'final_url':final_url})
    if not args.inspect and not args.print_article_hashes:
        payload = ''.join(json.dumps(c, ensure_ascii=False, sort_keys=True)+'\n' for c in chunks).encode('utf-8')
        if not args.build_reviewed_index and digest(payload) != data['index_sha256']:
            raise ValueError('Rebuilt official index hash mismatch')
        target = directory/'index_v18.jsonl'
        if target.exists():
            if target.read_bytes() != payload:
                raise ValueError('Existing index differs; refusing overwrite')
        else:
            with target.open('xb') as output:
                output.write(payload)
        manifest = directory/'snapshot_manifest_v18.json'
        if manifest.exists():
            existing = json.loads(manifest.read_text(encoding='utf-8'))
            if existing['sources'] != snapshots:
                raise ValueError('Local snapshot manifest changed; do not overwrite')
        else:
            with manifest.open('x',encoding='utf-8') as output:
                json.dump({'created_at_utc':datetime.now(timezone.utc).isoformat(),'sources':snapshots},output,indent=2)
        print(json.dumps({'status':'built_pending_pin' if args.build_reviewed_index else 'verified', 'sources':len(data['sources']), 'sections':len(chunks), 'index_sha256':digest(payload), 'api_calls':0}))


if __name__ == '__main__':
    main()
