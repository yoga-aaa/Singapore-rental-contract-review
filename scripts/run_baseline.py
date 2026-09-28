"""Run the deterministic baseline against labelled development cases."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.baseline_rules import result_as_dict, review_clause  # noqa: E402
from src.evaluate import evaluate  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=REPO_ROOT / "data" / "development_cases.csv")
    parser.add_argument("--registry", type=Path, default=REPO_ROOT / "data" / "source_registry.csv")
    parser.add_argument("--output", type=Path, default=REPO_ROOT / "results" / "development_baseline_predictions.csv")
    args = parser.parse_args()

    with args.cases.open(encoding="utf-8", newline="") as file:
        cases = list(csv.DictReader(file))

    predictions = []
    for case in cases:
        prediction = result_as_dict(review_clause(case["housing_type"], case["clause_text"]))
        prediction["case_id"] = case["case_id"]
        predictions.append(prediction)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fields = ["case_id", "predicted_label", "clause_category", "source_id", "source_section", "reason", "abstained"]
    with args.output.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(predictions)

    print(json.dumps(evaluate(args.cases, args.output, args.registry), indent=2))


if __name__ == "__main__":
    main()
