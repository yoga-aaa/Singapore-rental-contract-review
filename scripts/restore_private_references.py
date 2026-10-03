"""Restore only the two fixed CEA PDFs omitted from a course-only evidence ZIP.

Run bootstrap first. This copies verified local official downloads without API
calls, overwriting files, changing a freeze or restoring any private case data.
"""
import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.bootstrap import HASHES
from src.frozen_external import safe_member


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def restore_bundle(bundle, sources):
    manifest = json.loads((bundle / 'manifest.json').read_text(encoding='utf-8'))
    entries = [e for e in manifest['artifacts'] if e['path'].lower().endswith('.pdf')]
    allowed = {'snapshot/data/source_documents/' + name: sha for name, sha in HASHES.items()}
    if len(entries) != 2 or {e['path'] for e in entries} != set(allowed):
        raise ValueError('Only the two registered template snapshot paths can be restored')
    planned = []
    for entry in entries:
        relative = entry['path']
        if entry['sha256'] != allowed[relative]:
            raise ValueError('Frozen PDF hash is not the registered fixed version')
        target = safe_member(bundle, relative)
        source = sources / Path(relative).name
        if not source.is_file() or digest(source) != entry['sha256']:
            raise ValueError('Run bootstrap to obtain the fixed official template: ' + source.name)
        if target.exists() and digest(target) != entry['sha256']:
            raise ValueError('Existing snapshot differs; refusing to overwrite: ' + relative)
        planned.append((source, target, entry['sha256']))
    restored = 0
    for source, target, expected in planned:
        if target.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        with source.open('rb') as reader, target.open('xb') as writer:
            shutil.copyfileobj(reader, writer)
        if digest(target) != expected:
            raise ValueError('Restored PDF hash failed')
        restored += 1
    return {'restored': restored, 'already_verified': 2 - restored, 'model_api_calls': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(restore_bundle(args.bundle, ROOT / 'data/source_documents'), indent=2))


if __name__ == '__main__':
    main()
