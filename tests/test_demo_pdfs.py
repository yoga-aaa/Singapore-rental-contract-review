import unittest
from pathlib import Path
from src.application import extract_pdf,run_document
ROOT=Path(__file__).resolve().parents[1]
class DemoPDFTests(unittest.TestCase):
    def test_five_readable_synthetic_inputs(self):
        for n in range(1,6):
            with self.subTest(pdf=n):
                clauses=extract_pdf((ROOT/f'data/demo_pdfs/demo_{n:02d}.pdf').read_bytes())
                self.assertEqual(len(clauses),1)
                self.assertEqual(clauses[0].pages,(1,))
                self.assertIn('Synthetic',clauses[0].text)
