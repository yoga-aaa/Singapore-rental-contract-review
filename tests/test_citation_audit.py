import csv
import json
import tempfile
import unittest
from pathlib import Path

from src.citation_audit import score_citation_audit, sha256


class CitationAuditTests(unittest.TestCase):
    def test_hash_is_portable_across_line_endings_but_detects_content_change(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "sample.csv"
            target.write_bytes(b"case_id,label\r\nA,review_required\r\n")
            windows_hash = sha256(target)
            target.write_bytes(b"case_id,label\nA,review_required\n")
            self.assertEqual(sha256(target), windows_hash)
            target.write_bytes(b"case_id,label\nA,insufficient_evidence\n")
            self.assertNotEqual(sha256(target), windows_hash)

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        root = Path(self.directory.name)
        self.predictions = root / "predictions.csv"
        self.index = root / "source_pages.jsonl"
        self.audit = root / "audit.json"
        with self.predictions.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=["case_id", "predicted_label", "source_id", "source_section"])
            writer.writeheader()
            writer.writerows([
                {"case_id": "A", "predicted_label": "review_required", "source_id": "CEA", "source_section": "Page 3"},
                {"case_id": "B", "predicted_label": "insufficient_evidence", "source_id": "", "source_section": ""},
            ])
        self.index.write_text(
            json.dumps({"source_id": "CEA", "section": "Page 3", "text": "2.2 Security Deposit. Written notice first."}) + "\n",
            encoding="utf-8",
        )
        self.audit_data = {
            "predictions_sha256": sha256(self.predictions),
            "index_sha256": sha256(self.index),
            "visible_characters_per_chunk": 2200,
            "assessments": [{
                "case_id": "A", "source_id": "CEA", "source_section": "Page 3",
                "reference_anchor": "2.2 Security Deposit", "verdict": "supported", "note": "The cited page contains the process.",
            }],
        }

    def save_audit(self):
        self.audit.write_text(json.dumps(self.audit_data), encoding="utf-8")

    def test_scores_only_a_complete_matching_audit(self):
        self.save_audit()
        summary = score_citation_audit(self.predictions, self.index, self.audit)
        self.assertEqual(summary["citation_audited_count"], 1)
        self.assertEqual(summary["citation_validity"], 1.0)

    def test_prediction_hash_mismatch_is_rejected(self):
        self.audit_data["predictions_sha256"] = "0" * 64
        self.save_audit()
        with self.assertRaisesRegex(ValueError, "prediction CSV SHA-256"):
            score_citation_audit(self.predictions, self.index, self.audit)

    def test_anchor_must_be_on_the_cited_visible_page(self):
        self.audit_data["assessments"][0]["reference_anchor"] = "unrelated"
        self.save_audit()
        with self.assertRaisesRegex(ValueError, "anchor is absent"):
            score_citation_audit(self.predictions, self.index, self.audit)


if __name__ == "__main__":
    unittest.main()
