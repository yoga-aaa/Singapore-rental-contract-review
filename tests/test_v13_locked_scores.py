"""Reproduce frozen paid/replay scores and keep previous external scores intact."""

import unittest

from scripts.score_v13_development_check import summary
from scripts.score_external_evaluation import TRUTH, PREDICTIONS, REGISTRY, AUDIT, INDEX
from src.evaluate import evaluate


@unittest.skipUnless(INDEX.exists(), 'Historical legacy index is private; current bootstrap builds only the corrected v15 index')
class LockedDevelopmentScoreTests(unittest.TestCase):
    def test_live_and_replay_results_remain_separate_and_reproducible(self):
        result = summary()
        original = result["original_v13_live"]
        replay = result["v13_1_recorded_response_replay"]
        self.assertEqual(original["model_calls"], 10)
        self.assertEqual(original["total_tokens"], 21586)
        self.assertEqual(original["metrics"]["true_positive_risk_count"], 8)
        self.assertEqual(original["metrics"]["citation_supported_count"], 19)
        self.assertEqual(replay["new_model_calls"], 0)
        self.assertEqual(replay["new_api_tokens"], 0)
        self.assertEqual(replay["metrics"]["true_positive_risk_count"], 12)
        self.assertEqual(replay["metrics"]["citation_supported_count"], 22)
        self.assertEqual(replay["metrics"]["citation_audited_count"], 23)
        self.assertEqual(replay["metrics"]["citation_uncertain_count"], 1)
        self.assertEqual(replay["uncertain_citation_case_ids"], ["DEV_15"])
        self.assertEqual(replay["metrics"]["unsafe_non_abstention_count"], 0)

    def test_prior_external_scores_are_not_replaced_by_development_replay(self):
        metrics = evaluate(TRUTH, PREDICTIONS, REGISTRY, AUDIT, INDEX)
        self.assertEqual(metrics["citation_supported_count"], 5)
        self.assertEqual(metrics["citation_audited_count"], 13)
        self.assertEqual(metrics["review_required_recall"], 10 / 15)


if __name__ == "__main__":
    unittest.main()
