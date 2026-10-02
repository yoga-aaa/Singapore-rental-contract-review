"""Build a local clause-level index from the registered CEA agreement templates."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from pypdf import PdfReader


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.schedule_sections import split_schedule_items  # noqa: E402
from src.source_sections import split_operative_sections  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=REPO_ROOT / "data" / "source_registry.csv")
    parser.add_argument("--document-dir", type=Path, default=REPO_ROOT / "data" / "source_documents")
    parser.add_argument("--output", type=Path, default=REPO_ROOT / "data" / "derived" / "source_sections.jsonl")
    args = parser.parse_args()

    with args.registry.open(encoding="utf-8", newline="") as file:
        sources = list(csv.DictReader(file))
    chunks: list[dict[str, object]] = []
    for source in sources:
        if source["use_in_mvp"].lower() != "true" or source["source_kind"] != "tenancy_agreement_template":
            continue
        path = args.document_dir / source["local_filename"]
        if not path.exists():
            raise FileNotFoundError(f"Missing registered source: {path}")
        pages = [(number, page.extract_text() or "") for number, page in enumerate(PdfReader(path).pages, start=1)]
        source_chunks = split_schedule_items(pages, source) + split_operative_sections(pages, source)
        if not source_chunks:
            raise ValueError(f"No operative clauses found in {path}")
        chunks.extend(source_chunks)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as file:
        for chunk in chunks:
            file.write(json.dumps(chunk, ensure_ascii=False) + "\n")
    print(f"Built {len(chunks)} clause excerpts from {len(sources)} registered sources: {args.output}")


if __name__ == "__main__":
    main()
