"""Five synthetic PDF intake/review checks, explicitly offline and zero credits."""
import json
import sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.application import extract_pdf,run_document
ROOT=Path(__file__).resolve().parents[1]
def main():
    examples=json.loads((ROOT/'data/demo_examples.json').read_text(encoding='utf-8'))
    expected=['review_required','no_material_difference_found','insufficient_evidence','no_material_difference_found','model_needed']
    records=[]
    with patch('src.live_review._request_openrouter',side_effect=AssertionError('No paid request allowed')):
        for n,(sample,label) in enumerate(zip(examples,expected),1):
            path=ROOT/f'data/demo_pdfs/demo_{n:02d}.pdf'
            clauses=extract_pdf(path.read_bytes())
            report=run_document(clauses,sample['housing_type'],synthetic_confirmed=True,extraction_confirmed=True)
            assert report['accounting']['api_calls']==0
            assert len(report['clauses'])==1,report
            row=report['clauses'][0]
            actual=row['result']['label'] if row['result'] else row['status']
            assert actual==label,(sample['title'],actual,label)
            records.append({'file':path.name,'expected':label,'actual':actual,'api_calls':0,'report':report})
    print(json.dumps({'test_kind':'Five reused synthetic demonstrations, not generalization evaluation',
                      'passed':5,'api_calls':0,'cost_usd':'0','records':records},ensure_ascii=True,indent=2))
if __name__=='__main__':main()
