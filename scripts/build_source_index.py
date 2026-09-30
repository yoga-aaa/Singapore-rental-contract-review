"""Extract registered CEA PDFs into a local page-level JSONL retrieval index."""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

from pypdf import PdfReader


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = REPO_ROOT / "data" / "source_registry.csv"
DEFAULT_DOCUMENT_DIR = REPO_ROOT / "data" / "source_documents"
DEFAULT_OUTPUT = REPO_ROOT / "data" / "derived" / "source_pages.jsonl"


def compact_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def page_section(text: str, page_number: int) -> str:
    """Use the physical PDF page, rather than an unreliable heading regex."""
    return f"Page {page_number}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--document-dir", type=Path, default=DEFAULT_DOCUMENT_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    with args.registry.open(encoding="utf-8", newline="") as file:
        sources = list(csv.DictReader(file))

    chunks: list[dict[str, object]] = []
    for source in sources:
        if source["use_in_mvp"].lower() != "true":
            continue
        document_path = args.document_dir / source["local_filename"]
        if not document_path.exists():
            raise FileNotFoundError(f"Missing registered source: {document_path}")

        for page_number, page in enumerate(PdfReader(document_path).pages, start=1):
            text = compact_text(page.extract_text() or "")
            if not text:
                continue
            chunks.append(
                {
                    "source_id": source["source_id"],
                    "housing_type": source["housing_type"],
                    "source_kind": source["source_kind"],
                    "title": source["title"],
                    "page_number": page_number,
                    "section": page_section(text, page_number),
                    "text": text,
                }
            )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as file:
        for chunk in chunks:
            file.write(json.dumps(chunk, ensure_ascii=False) + "\n")
    print(f"Built {len(chunks)} chunks from {len(sources)} registered sources: {args.output.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
