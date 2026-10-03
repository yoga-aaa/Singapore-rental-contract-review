"""Download fixed references and build versioned indexes for a new checkout."""
import hashlib
import subprocess
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
HASHES={'cea_hdb_tenancy_agreement_template_v1_4.pdf':'ec914123e04142de531f8995a528760e7157936017efc2620d94c74e184f8622',
        'cea_private_tenancy_agreement_template_v1_4.pdf':'bca8b00b386351e1d1a69892c44412af0d0ab90007d379aa045d12122ef8b02a'}
def main():
    subprocess.run([sys.executable,'scripts/download_sources.py'],cwd=ROOT,check=True)
    for filename,digest in HASHES.items():
        path=ROOT/'data/source_documents'/filename
        if hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
            raise ValueError('Reference changed: '+filename+'. Do not reuse frozen scores; obtain and verify the intended version.')
    for script,target in [('build_source_index.py','source_pages_v15.jsonl'),('build_section_index.py','source_sections_v15.jsonl')]:
        if not (ROOT/'data/derived'/target).exists():
            subprocess.run([sys.executable,'scripts/'+script],cwd=ROOT,check=True)
    from src.application import load_retriever
    load_retriever()
    print('References and index ready. Run: python -m streamlit run app.py')
if __name__=='__main__':
    sys.path.insert(0,str(ROOT)); main()
