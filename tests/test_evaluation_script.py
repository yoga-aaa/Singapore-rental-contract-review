import unittest
from pathlib import Path


class EvaluationScriptTests(unittest.TestCase):
    def test_script_is_restricted_to_development_cases(self):
        script = Path("scripts/run_rag_evaluation.py").read_text(encoding="utf-8")
        self.assertIn('args.cases.name != "development_cases.csv"', script)
        self.assertIn("development_rag_predictions_v10.csv", script)


if __name__ == "__main__":
    unittest.main()
