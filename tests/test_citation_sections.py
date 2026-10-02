import csv
import json
import tempfile
import unittest
from pathlib import Path

from src.citation_audit import score_citation_audit, sha256


class ClauseCitationAuditTests(unittest.TestCase):
    def test_audit_checks_every_selected_quote_and_accepts_clause_locator(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            predictions, index, audit = (root / name for name in ("predictions.csv", "index.jsonl", "audit.json"))
            sections = [
                {"source_id": "CEA", "section": "Schedule ITEM 10 / PDF page 3",
                 "text": "10. MINOR REPAIR: The cap is S$_____."},
                {"source_id": "CEA", "section": "Clause 4.2 / PDF page 7",
                 "text": "Excess cost shall be borne by the Landlord."},
            ]
            index.write_text("\n".join(json.dumps(item) for item in sections) + "\n", encoding="utf-8")
            evidence = [
                {"source_id": "CEA", "source_section": sections[0]["section"], "topic": "minor_repair",
                 "quote": "10. MINOR REPAIR: The cap is S$_____."},
                {"source_id": "CEA", "source_section": sections[1]["section"], "topic": "minor_repair",
                 "quote": "Excess cost shall be borne by the Landlord."},
            ]
            with predictions.open("w", encoding="utf-8", newline="") as file:
                writer = csv.DictWriter(file, fieldnames=["case_id", "predicted_label", "source_id",
                                                           "source_section", "evidence_json"])
                writer.writeheader()
                writer.writerow({"case_id": "A", "predicted_label": "review_required", "source_id": "CEA",
                                 "source_section": sections[0]["section"], "evidence_json": json.dumps(evidence)})
            audit_data = {"predictions_sha256": sha256(predictions), "index_sha256": sha256(index),
                          "visible_characters_per_chunk": 2200,
                          "assessments": [{"case_id": "A", "source_id": "CEA",
                                           "source_section": sections[0]["section"],
                                           "reference_anchor": "10. MINOR REPAIR:", "verdict": "supported",
                                           "note": "Both selected sections support the comparison."}]}
            audit.write_text(json.dumps(audit_data), encoding="utf-8")
            self.assertEqual(score_citation_audit(predictions, index, audit)["citation_validity"], 1.0)
            evidence[1]["quote"] = "Invented reference rule"
            with predictions.open("w", encoding="utf-8", newline="") as file:
                writer = csv.DictWriter(file, fieldnames=["case_id", "predicted_label", "source_id",
                                                           "source_section", "evidence_json"])
                writer.writeheader()
                writer.writerow({"case_id": "A", "predicted_label": "review_required", "source_id": "CEA",
                                 "source_section": sections[0]["section"], "evidence_json": json.dumps(evidence)})
            audit_data["predictions_sha256"] = sha256(predictions)
            audit.write_text(json.dumps(audit_data), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Cited quote is absent"):
                score_citation_audit(predictions, index, audit)


if __name__ == "__main__":
    unittest.main()
