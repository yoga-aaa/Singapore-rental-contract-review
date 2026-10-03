"""Input-only private reviewer package; no old labels, predictions or API call.

Only reviewed first-party source text and owner-approved synthetic cases are
included. An explicit allowlist prevents accidental inclusion of private logs.
"""
import argparse
import csv
import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.application import safety_issue
from src.official_sources import load_official_index, digest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cases',type=Path,required=True)
    parser.add_argument('--output',type=Path,default=ROOT/'submission/Blind_Review_v18')
    args=parser.parse_args()
    destination=args.output.resolve()
    if not destination.is_relative_to((ROOT/'submission').resolve()) or destination==(ROOT/'submission').resolve():
        raise ValueError('Reviewer package must be in a named ignored submission subdirectory')
    archive=destination.with_suffix('.zip')
    if destination.exists() or archive.exists():
        raise ValueError('Do not overwrite or silently repeat a reviewer package')
    payload=args.cases.read_bytes()
    cases=json.loads(payload)
    if not isinstance(cases,list) or len(cases)!=20 or len({r.get('case_id') for r in cases})!=20:
        raise ValueError('Expected twenty unique synthetic cases')
    for case in cases:
        if set(case)!={'case_id','housing_type','clause_text'} or safety_issue(case['clause_text'],case['housing_type']):
            raise ValueError('Input contains annotation, personal identifiers or unsupported housing/text')
    rows=load_official_index(ROOT)
    registry=json.loads((ROOT/'data/official_reference_registry_v18.json').read_text(encoding='utf-8'))
    destination.mkdir(parents=True)
    (destination/'references').mkdir()
    with (destination/'cases.input_only.json').open('xb') as output: output.write(payload)
    shutil.copyfile(ROOT/'docs/blind_reviewer_prompt_v18_zh.md',destination/'REVIEWER_PROMPT_ZH.md')
    shutil.copyfile(ROOT/'docs/blind_relabel_v18_zh.md',destination/'LABELING_RULES_ZH.md')
    manifest={'version':'v18_reference_scope_candidate_labels_pending',
              'cases_sha256':digest(payload), 'case_count':len(cases),
              'information_boundary':'No old labels, product code, predictions, scores or case-specific hints. Existing exposed cases remain regression material.',
              'sources':[]}
    templates=[('CEA_HDB_TA','HDB','cea_hdb_tenancy_agreement_template_v1_4.pdf',
                'ec914123e04142de531f8995a528760e7157936017efc2620d94c74e184f8622'),
               ('CEA_PRIVATE_TA','Private Residential','cea_private_tenancy_agreement_template_v1_4.pdf',
                'bca8b00b386351e1d1a69892c44412af0d0ab90007d379aa045d12122ef8b02a')]
    with (ROOT/'data/source_registry.csv').open(encoding='utf-8') as file:
        template_registry={r['source_id']:r for r in csv.DictReader(file)}
    for source_id,housing,filename,expected in templates:
        original=ROOT/'data/source_documents'/filename
        if digest(original.read_bytes())!=expected: raise ValueError('CEA template hash changed')
        target=destination/'references'/filename
        shutil.copyfile(original,target)
        manifest['sources'].append({'source_id':source_id,'authority':'CEA','housing_type':housing,
                                   'source_kind':'tenancy_agreement_template','file':target.relative_to(destination).as_posix(),
                                   'title':template_registry[source_id]['title'],'url':template_registry[source_id]['url'],
                                   'sha256':expected,'scope':'Optional template comparison, not mandatory law. Blank schedule fields are variables.'})
    for source in registry['sources']:
        text='\n\n'.join(r['text'] for r in rows if r['source_id']==source['source_id'])
        body=text.encode('utf-8')
        if digest(body)!=source['article_sha256']: raise ValueError('Reviewer text differs from verified article')
        file=destination/'references'/f"{source['source_id']}.txt"
        with file.open('xb') as output: output.write(body)
        manifest['sources'].append({**{k:source[k] for k in ['source_id','title','authority','housing_type','source_kind','url','verified_on','not_for']},
                                   'file':file.relative_to(destination).as_posix(),'sha256':digest(body),
                                   'original_html_sha256':source['html_sha256'],
                                   'scope':'Read complete article conditions; source kind limits the claims it supports.'})
    with (destination/'source_manifest.json').open('x',encoding='utf-8') as output:
        json.dump(manifest,output,ensure_ascii=False,indent=2)
    files=sorted(p for p in destination.rglob('*') if p.is_file())
    # All generated/copied files above are known; there is no directory-wide
    # copy of external evidence, code, results or historical annotations.
    integrity={'files':[{'path':p.relative_to(destination).as_posix(),'sha256':digest(p.read_bytes())} for p in files]}
    with (destination/'package_integrity.json').open('x',encoding='utf-8') as output:
        json.dump(integrity,output,indent=2)
    with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as output:
        for path in sorted(p for p in destination.rglob('*') if p.is_file()):
            output.write(path,path.relative_to(destination).as_posix())
    with zipfile.ZipFile(archive) as check:
        if check.testzip() is not None: raise ValueError('Reviewer archive integrity failed')
        for entry in integrity['files']:
            if digest(check.read(entry['path']))!=entry['sha256']: raise ValueError('Reviewer archive file hash differs')
    print(json.dumps({'output':str(destination),'archive':str(archive),'archive_sha256':digest(archive.read_bytes()),
                      'sources':len(manifest['sources']),'cases':len(cases),'api_calls':0,
                      'old_labels_included':False,'predictions_included':False},ensure_ascii=False,indent=2))


if __name__=='__main__': main()
