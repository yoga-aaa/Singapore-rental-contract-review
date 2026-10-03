import io
import json
import unittest
from unittest.mock import patch
from pathlib import Path
from pypdf import PdfWriter
from src.application import Clause, extract_pdf, run_document, safety_issue, load_retriever

class IntakeTests(unittest.TestCase):
    def test_personal_identifiers_blocked(self):
        for value in ['S1234567A','contact me@example.com','+65 81234567','Address: sample','Singapore 123456']:
            self.assertIsNotNone(safety_issue(value,'HDB'))
    def test_currency_not_personal_identifier(self):
        self.assertIsNone(safety_issue('The rent is S$3000 each month.','HDB'))
    def test_housing_mismatch(self):
        self.assertIsNotNone(safety_issue('This is a lease of an HDB flat.','Private Residential'))
    def test_non_english_blocked(self):
        self.assertIsNotNone(safety_issue('租客每月支付房租。','HDB'))
    def test_bad_and_oversized_pdf(self):
        for payload in [b'not pdf',b'%PDF'+b'x'*2_000_000]:
            with self.assertRaises(ValueError): extract_pdf(payload)
    def test_no_text_pdf_does_not_silently_pass(self):
        writer=PdfWriter(); writer.add_blank_page(width=612,height=792)
        output=io.BytesIO(); writer.write(output)
        with self.assertRaisesRegex(ValueError,'little extractable'): extract_pdf(output.getvalue())
    def test_confirmations_required_before_api(self):
        c=[Clause('C',(),'The Tenant pays rent.')]
        for args in [dict(synthetic_confirmed=False,extraction_confirmed=True),dict(synthetic_confirmed=True,extraction_confirmed=False)]:
            with self.assertRaises(ValueError): run_document(c,'HDB',**args)
    def test_live_off_even_with_paid_checkbox(self):
        with patch.dict('os.environ',{'RENTAL_ENABLE_LIVE':'0'}):
            with self.assertRaisesRegex(ValueError,'disabled'):
                run_document([Clause('C',(),'The Tenant pays rent.')],'HDB',synthetic_confirmed=True,
                             extraction_confirmed=True,live=True,spending_confirmed=True)
    def test_offline_never_reads_key_or_calls_transport(self):
        with patch('src.application.local_api_key',side_effect=AssertionError('No key in offline mode')):
            report=run_document([Clause('C',(),'All matters will be managed appropriately by the parties.')],
                                'HDB',synthetic_confirmed=True,extraction_confirmed=True)
        self.assertEqual(report['accounting']['api_calls'],0)
        self.assertEqual(report['clauses'][0]['result']['label'],'insufficient_evidence')
    def test_model_needed_is_not_finished_prediction(self):
        report=run_document([Clause('C',(),'The Tenant shall pay the cost of a pet-related repair subject to prior approval and a refundable bond of S$150.')],
                            'Private Residential',synthetic_confirmed=True,extraction_confirmed=True)
        # Topic coverage may locally abstain; neither path invents a model response.
        self.assertEqual(report['accounting']['api_calls'],0)
        if report['clauses'][0]['status']=='model_needed': self.assertIsNone(report['clauses'][0]['result'])

try:
    from streamlit.testing.v1 import AppTest
except ImportError:
    AppTest=None

@unittest.skipIf(AppTest is None,'Install requirements.txt for UI tests')
class UITests(unittest.TestCase):
    def test_demo_and_download_no_credits(self):
        app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py')).run()
        self.assertEqual(len(app.exception),0)
        app.radio(key='input_method').set_value('Built-in synthetic example').run()
        app.checkbox(key='synthetic').check(); app.checkbox(key='extraction_checked').check(); app.run()
        app.button(key='review').click().run()
        self.assertEqual(len(app.exception),0)
        self.assertTrue(any(c.value=='review_required' for c in app.code))
        self.assertEqual(app.session_state['report']['accounting']['api_calls'],0)
